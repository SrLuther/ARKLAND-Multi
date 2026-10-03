#include "pch.h"
#include "HuntPerms.h"

#include <tlhelp32.h>
#include <filesystem>

// Resolução da Permissions (ArkServerApi) — LAZY.
//
// O ArkApi carrega plugins um a um (ordem do directório: "ArkEventHunt" vem
// ANTES de "Permissions"), por isso em Plugin_Init a Permissions.dll ainda NÃO
// está no processo. A ligação é por isso feita (1) uma tentativa tolerante no
// Init, (2) na primeira vez que alguém precisa de checar um grupo (/eveadm) e
// (3) numa tentativa agendada após o arranque.
//
// A Permissions oficial exporta C++ mangled:
//   ?IsPlayerInGroup@Permissions@@YA_N_KAEBVFString@@@Z
//   bool Permissions::IsPlayerInGroup(uint64 steam_id, const FString& group)
// pelo que GetProcAddress(h, "IsPlayerInGroup") NUNCA acha o símbolo. Por isso
// percorremos a tabela de exports do PE e aceitamos nome mangled ou plain.

namespace {

enum class Sig { None, FStringRef, WideCStr, NarrowCStr };

using FnIsInGroupFStr = bool(*)(unsigned __int64, const FString&);
using FnIsInGroupW = bool(*)(unsigned __int64, const wchar_t*);
using FnIsInGroupA = bool(*)(unsigned __int64, const char*);

std::mutex g_mu;
Sig g_sig = Sig::None;
FARPROC g_fn = nullptr;
std::string g_bound_desc;          // "<módulo> :: <export>"
bool g_logged_missing = false;     // evita spam
bool g_logged_no_export = false;
int64_t g_last_try_ms = 0;         // throttle de scans completos

constexpr int64_t kRetryThrottleMs = 5000;

int64_t NowMs() {
    return std::chrono::duration_cast<std::chrono::milliseconds>(
               std::chrono::steady_clock::now().time_since_epoch())
        .count();
}

std::string WideToUtf8(const wchar_t* w) {
    if (!w || !*w) return {};
    const int n = WideCharToMultiByte(CP_UTF8, 0, w, -1, nullptr, 0, nullptr,
                                      nullptr);
    if (n <= 1) return {};
    std::string out(static_cast<size_t>(n - 1), '\0');
    WideCharToMultiByte(CP_UTF8, 0, w, -1, out.data(), n, nullptr, nullptr);
    return out;
}

std::string ModulePath(HMODULE h) {
    wchar_t buf[MAX_PATH * 2] = {};
    if (!GetModuleFileNameW(h, buf, static_cast<DWORD>(std::size(buf))))
        return {};
    return WideToUtf8(buf);
}

std::string ExpectedPermsPath() {
    return ArkApi::Tools::GetCurrentDir() +
           "/ArkApi/Plugins/Permissions/Permissions.dll";
}

bool ExpectedPermsFileExists() {
    std::error_code ec;
    return std::filesystem::exists(
        std::filesystem::path(ExpectedPermsPath()), ec);
}

struct ExportHit {
    FARPROC fn = nullptr;
    Sig sig = Sig::None;
    std::string name;
};

// Percorre a tabela de exports do módulo. Preenche `hit` se achar
// IsPlayerInGroup; `related` recebe (até 24) exports com "Group"/"Player"
// para diagnóstico quando nada compatível é achado.
void ScanExports(HMODULE h, ExportHit& hit, std::vector<std::string>* related) {
    if (!h) return;
    const auto* base = reinterpret_cast<const BYTE*>(h);
    const auto* dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(base);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) return;
    const auto* nt =
        reinterpret_cast<const IMAGE_NT_HEADERS*>(base + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE) return;

    const auto& dir =
        nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_EXPORT];
    const DWORD img_size = nt->OptionalHeader.SizeOfImage;
    if (!dir.VirtualAddress || !dir.Size || dir.VirtualAddress >= img_size)
        return;

    const auto* exp = reinterpret_cast<const IMAGE_EXPORT_DIRECTORY*>(
        base + dir.VirtualAddress);
    if (!exp->NumberOfNames || exp->AddressOfNames >= img_size) return;
    const auto* names =
        reinterpret_cast<const DWORD*>(base + exp->AddressOfNames);

    for (DWORD i = 0; i < exp->NumberOfNames; ++i) {
        const DWORD rva = names[i];
        if (rva == 0 || rva >= img_size) continue;
        const char* n = reinterpret_cast<const char*>(base + rva);
        if (!std::strstr(n, "IsPlayerInGroup")) {
            if (related && related->size() < 24 &&
                (std::strstr(n, "Group") || std::strstr(n, "Player")))
                related->emplace_back(n);
            continue;
        }

        Sig s = Sig::None;
        if (std::strcmp(n, "IsPlayerInGroup") == 0)
            s = Sig::WideCStr;  // export plain (builds antigas): wchar_t*
        else if (std::strstr(n, "FString"))
            s = Sig::FStringRef;  // ?IsPlayerInGroup@Permissions@@YA_N_KAEBVFString@@@Z
        else {
            if (related && related->size() < 24) related->emplace_back(n);
            continue;  // assinatura desconhecida (std::string etc.)
        }

        FARPROC fn = GetProcAddress(h, n);
        if (!fn) continue;
        // FString (Permissions oficial) tem prioridade sobre plain.
        if (!hit.fn || s == Sig::FStringRef) {
            hit.fn = fn;
            hit.sig = s;
            hit.name = n;
        }
    }
}

// Tenta achar a Permissions. Retorna true se ligou.
// Chamar com g_mu detido.
bool TryBindLocked(bool log_failure) {
    if (g_fn) return true;

    ExportHit hit;
    HMODULE hit_mod = nullptr;
    HMODULE perms_mod = nullptr;   // módulo "Permissions" (mesmo sem export)
    std::vector<std::string> related;

    // 1) Nomes conhecidos (caminho rápido).
    static const wchar_t* kKnownNames[] = {
        L"Permissions.dll", L"Permissions",
        L"ArkPermissions.dll", L"ArkPerms.dll",
        L"PermissionsPlugin.dll", L"ASEPermissions.dll",
    };
    for (const wchar_t* name : kKnownNames) {
        HMODULE h = GetModuleHandleW(name);
        if (!h) continue;
        if (!perms_mod) perms_mod = h;
        ExportHit tmp;
        ScanExports(h, tmp, &related);
        if (tmp.fn) {
            hit = tmp;
            hit_mod = h;
            break;
        }
    }

    // 2) Varredura de todos os módulos (nome do DLL diferente do esperado).
    if (!hit.fn) {
        HANDLE snap = CreateToolhelp32Snapshot(
            TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, GetCurrentProcessId());
        if (snap != INVALID_HANDLE_VALUE) {
            MODULEENTRY32W me{};
            me.dwSize = sizeof(me);
            for (BOOL ok = Module32FirstW(snap, &me); ok;
                 ok = Module32NextW(snap, &me)) {
                HMODULE h = me.hModule;
                if (!h || h == hit_mod) continue;
                ExportHit tmp;
                ScanExports(h, tmp, nullptr);
                if (tmp.fn) {
                    hit = tmp;
                    hit_mod = h;
                    break;
                }
            }
            CloseHandle(snap);
        }
    }

    if (hit.fn) {
        g_fn = hit.fn;
        g_sig = hit.sig;
        g_bound_desc = ModulePath(hit_mod) + " :: " + hit.name;
        g_logged_missing = false;
        g_logged_no_export = false;
        Log::GetLog()->info(
            "ArkEventHunt: Permissions ligado — {} (assinatura={})",
            g_bound_desc,
            g_sig == Sig::FStringRef ? "FString const&" : "plain wchar_t*");
        return true;
    }

    if (!log_failure) return false;

    if (perms_mod) {
        // DLL carregada, mas sem export compatível: bug real de versão/ABI.
        if (!g_logged_no_export) {
            g_logged_no_export = true;
            std::string rel;
            for (const auto& r : related) rel += "\n    " + r;
            Log::GetLog()->warn(
                "ArkEventHunt: Permissions carregada ({}) mas SEM export "
                "IsPlayerInGroup compatível — grupos desligados; /eveadm só "
                "para bIsAdmin. Exports relacionados:{}",
                ModulePath(perms_mod), rel.empty() ? " (nenhum)" : rel);
        }
    } else if (!g_logged_missing) {
        g_logged_missing = true;
        Log::GetLog()->warn(
            "ArkEventHunt: Permissions não está carregada neste momento "
            "(procurado: módulo 'Permissions.dll' no processo; ficheiro "
            "esperado '{}' {}). /eveadm usa bIsAdmin() até a Permissions "
            "carregar; nova tentativa ao usar /eveadm.",
            ExpectedPermsPath(),
            ExpectedPermsFileExists()
                ? "EXISTE no disco — apenas ainda não carregou (ordem de carga) "
                  "ou falhou ao iniciar (ver log da Permissions/MySQL)"
                : "NÃO existe no disco");
    }
    return false;
}

}  // anonymous

namespace ArkEventHunt {
namespace Perms {

void Init() {
    // Plugin_Init: a Permissions normalmente ainda não carregou — tentativa
    // silenciosa (sem warning falso). A ligação definitiva é lazy.
    std::lock_guard<std::mutex> lock(g_mu);
    if (TryBindLocked(/*log_failure=*/false)) return;
    Log::GetLog()->info(
        "ArkEventHunt: Permissions ainda não carregada (ordem de carga do "
        "ArkApi) — ligação tardia ao primeiro uso / após o arranque.");
}

bool Resolve(bool log_failure) {
    std::lock_guard<std::mutex> lock(g_mu);
    return TryBindLocked(log_failure);
}

bool IsAvailable() {
    std::lock_guard<std::mutex> lock(g_mu);
    return g_fn != nullptr;
}

bool IsInGroup(uint64_t steam_id, const std::string& group) {
    if (group == "Default") return true;
    if (group.empty()) return false;

    FARPROC fn = nullptr;
    Sig sig = Sig::None;
    {
        std::lock_guard<std::mutex> lock(g_mu);
        if (!g_fn) {
            // Lazy: re-tenta (com throttle) — Permissions pode ter carregado
            // depois de nós.
            const int64_t now = NowMs();
            if (now - g_last_try_ms >= kRetryThrottleMs) {
                g_last_try_ms = now;
                TryBindLocked(/*log_failure=*/true);
            }
        }
        fn = g_fn;
        sig = g_sig;
    }
    if (!fn) return false;

    try {
        switch (sig) {
        case Sig::FStringRef: {
            FString fg(group.c_str());
            return reinterpret_cast<FnIsInGroupFStr>(fn)(
                static_cast<unsigned __int64>(steam_id), fg);
        }
        case Sig::WideCStr: {
            const std::wstring wg(group.begin(), group.end());
            return reinterpret_cast<FnIsInGroupW>(fn)(
                static_cast<unsigned __int64>(steam_id), wg.c_str());
        }
        case Sig::NarrowCStr:
            return reinterpret_cast<FnIsInGroupA>(fn)(
                static_cast<unsigned __int64>(steam_id), group.c_str());
        default:
            return false;
        }
    } catch (...) {
        Log::GetLog()->error(
            "ArkEventHunt: excepção em Permissions::IsPlayerInGroup "
            "(steam={} group={})",
            steam_id, group);
        return false;
    }
}

bool IsInAnyGroup(uint64_t steam_id, const std::vector<std::string>& groups) {
    if (groups.empty()) return false;
    for (const auto& g : groups) {
        if (IsInGroup(steam_id, g)) return true;
    }
    return false;
}

}  // namespace Perms
}  // namespace ArkEventHunt
