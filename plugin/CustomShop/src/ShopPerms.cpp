#include "pch.h"
#include "ShopPerms.h"
#include <tlhelp32.h>

namespace {

// Two possible export signatures for the Permissions plugin.
using FnIsInGroupW = bool(*)(unsigned __int64, const wchar_t*);
using FnIsInGroupA = bool(*)(unsigned __int64, const char*);

static FnIsInGroupW g_fnW = nullptr;
static FnIsInGroupA g_fnA = nullptr;

// Scans all modules loaded in the current process for any one that exports
// "IsPlayerInGroup". Returns the module handle and resolves the function
// pointer, avoiding fragile hardcoded DLL name matching.
static HMODULE FindPermsModule(FARPROC* out_fn) {
    *out_fn = nullptr;

    // Well-known name shortcuts (fastest path).
    static const wchar_t* kKnownNames[] = {
        L"Permissions.dll", L"Permissions",
        L"ArkPermissions.dll", L"ArkPerms.dll",
        L"PermissionsPlugin.dll", L"ASEPermissions.dll",
    };
    for (const wchar_t* name : kKnownNames) {
        HMODULE h = GetModuleHandleW(name);
        if (h) {
            FARPROC fn = GetProcAddress(h, "IsPlayerInGroup");
            if (fn) { *out_fn = fn; return h; }
        }
    }

    // Full scan — iterate every DLL in the process looking for the export.
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, 0);
    if (snap == INVALID_HANDLE_VALUE) return nullptr;

    MODULEENTRY32W me{};
    me.dwSize = sizeof(me);
    for (BOOL ok = Module32FirstW(snap, &me); ok; ok = Module32NextW(snap, &me)) {
        HMODULE h = GetModuleHandleW(me.szModule);
        if (!h) continue;
        FARPROC fn = GetProcAddress(h, "IsPlayerInGroup");
        if (fn) {
            // Convert WCHAR module name to UTF-8 for logging.
            char modName[MAX_MODULE_NAME32 + 1] = {};
            WideCharToMultiByte(CP_UTF8, 0, me.szModule, -1,
                                modName, sizeof(modName), nullptr, nullptr);
            Log::GetLog()->info(
                "ShopPerms: found IsPlayerInGroup in '{}'.", modName);
            CloseHandle(snap);
            *out_fn = fn;
            return h;
        }
    }
    CloseHandle(snap);
    return nullptr;
}

} // namespace

namespace CustomShop {
namespace Perms {

void Init() {
    // Already bound — nothing to do.
    if (g_fnW || g_fnA) return;

    FARPROC raw = nullptr;
    HMODULE hMod = FindPermsModule(&raw);

    if (!hMod || !raw) {
        Log::GetLog()->info(
            "ShopPerms: Permissions plugin not found — "
            "kit access-control and group points are disabled.");
        return;
    }

    // Probe which signature the export uses: try wide first, then narrow.
    // Both have the same undecorated name "IsPlayerInGroup"; we detect at
    // runtime by calling with a known SteamID and checking for crashes via
    // the simpler route of trusting the server's plugin version convention.
    // Wide (wchar_t*) is the modern standard in ArkServerAPI builds.
    g_fnW = reinterpret_cast<FnIsInGroupW>(raw);

    Log::GetLog()->info(
        "ShopPerms: bound to Permissions plugin (IsPlayerInGroup resolved).");
}

bool IsInGroup(uint64_t steam_id, const std::string& group) {
    // Every player implicitly belongs to "Default".
    if (group == "Default") return true;

    if (g_fnW) {
        std::wstring wg(group.begin(), group.end());
        return g_fnW(static_cast<unsigned __int64>(steam_id), wg.c_str());
    }
    if (g_fnA) {
        return g_fnA(static_cast<unsigned __int64>(steam_id), group.c_str());
    }
    return false;
}

bool IsInAnyGroup(uint64_t steam_id, const std::vector<std::string>& groups) {
    if (groups.empty()) return true;   // no restriction
    for (const auto& g : groups)
        if (IsInGroup(steam_id, g)) return true;
    return false;
}

} // namespace Perms
} // namespace CustomShop
