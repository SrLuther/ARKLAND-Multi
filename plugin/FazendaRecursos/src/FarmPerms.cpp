#include "FarmPerms.h"
#include <tlhelp32.h>

namespace FazendaRecursos::Perms {
namespace {
using FnFString = bool(*)(unsigned __int64, const FString&);
using FnWide = bool(*)(unsigned __int64, const wchar_t*);
FARPROC fn = nullptr;
bool wide = false;
std::mutex mu;

void Scan(HMODULE module) {
    if (!module) return;
    auto* base = reinterpret_cast<const BYTE*>(module);
    auto* dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(base);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) return;
    auto* nt = reinterpret_cast<const IMAGE_NT_HEADERS*>(base + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE) return;
    const auto& dir = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_EXPORT];
    if (!dir.VirtualAddress || dir.VirtualAddress >= nt->OptionalHeader.SizeOfImage) return;
    auto* exp = reinterpret_cast<const IMAGE_EXPORT_DIRECTORY*>(base + dir.VirtualAddress);
    auto* names = reinterpret_cast<const DWORD*>(base + exp->AddressOfNames);
    for (DWORD i = 0; i < exp->NumberOfNames; ++i) {
        const char* name = reinterpret_cast<const char*>(base + names[i]);
        if (!std::strstr(name, "IsPlayerInGroup")) continue;
        const bool is_fstring = std::strstr(name, "FString") != nullptr;
        if (!is_fstring && std::strcmp(name, "IsPlayerInGroup") != 0) continue;
        FARPROC candidate = GetProcAddress(module, name);
        if (!candidate) continue;
        fn = candidate;
        wide = !is_fstring;
        return;
    }
}

bool Resolve() {
    std::lock_guard<std::mutex> lock(mu);
    if (fn) return true;
    if (HMODULE h = GetModuleHandleW(L"Permissions.dll")) Scan(h);
    if (!fn) {
        HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, GetCurrentProcessId());
        if (snap != INVALID_HANDLE_VALUE) {
            MODULEENTRY32W entry{}; entry.dwSize = sizeof(entry);
            for (BOOL ok = Module32FirstW(snap, &entry); ok && !fn; ok = Module32NextW(snap, &entry)) Scan(entry.hModule);
            CloseHandle(snap);
        }
    }
    return fn != nullptr;
}
}

void Init() { Resolve(); }
bool IsAvailable() { return Resolve(); }
bool IsInGroup(uint64_t steam_id, const std::string& group) {
    if (!Resolve() || !steam_id || group.empty()) return false;
    FARPROC target = nullptr; bool use_wide = false;
    { std::lock_guard<std::mutex> lock(mu); target = fn; use_wide = wide; }
    try {
        if (use_wide) {
            std::wstring w(group.begin(), group.end());
            return reinterpret_cast<FnWide>(target)(steam_id, w.c_str());
        }
        FString value(group.c_str());
        return reinterpret_cast<FnFString>(target)(steam_id, value);
    } catch (...) { return false; }
}
}
