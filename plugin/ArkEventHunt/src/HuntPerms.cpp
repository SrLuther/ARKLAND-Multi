#include "pch.h"
#include "HuntPerms.h"

#include <tlhelp32.h>

namespace {

using FnIsInGroupW = bool(*)(unsigned __int64, const wchar_t*);
using FnIsInGroupA = bool(*)(unsigned __int64, const char*);

FnIsInGroupW g_fnW = nullptr;
FnIsInGroupA g_fnA = nullptr;

HMODULE FindPermsModule(FARPROC* out_fn) {
    *out_fn = nullptr;
    static const wchar_t* kKnownNames[] = {
        L"Permissions.dll", L"Permissions",
        L"ArkPermissions.dll", L"ArkPerms.dll",
        L"PermissionsPlugin.dll", L"ASEPermissions.dll",
    };
    for (const wchar_t* name : kKnownNames) {
        HMODULE h = GetModuleHandleW(name);
        if (!h) continue;
        FARPROC fn = GetProcAddress(h, "IsPlayerInGroup");
        if (fn) {
            *out_fn = fn;
            return h;
        }
    }

    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, 0);
    if (snap == INVALID_HANDLE_VALUE) return nullptr;

    MODULEENTRY32W me{};
    me.dwSize = sizeof(me);
    for (BOOL ok = Module32FirstW(snap, &me); ok; ok = Module32NextW(snap, &me)) {
        HMODULE h = GetModuleHandleW(me.szModule);
        if (!h) continue;
        FARPROC fn = GetProcAddress(h, "IsPlayerInGroup");
        if (fn) {
            *out_fn = fn;
            CloseHandle(snap);
            return h;
        }
    }
    CloseHandle(snap);
    return nullptr;
}

} // anonymous

namespace ArkEventHunt {
namespace Perms {

void Init() {
    if (g_fnW || g_fnA) return;
    FARPROC raw = nullptr;
    HMODULE h = FindPermsModule(&raw);
    if (!h || !raw) {
        Log::GetLog()->warn(
            "ArkEventHunt: Permissions.dll não encontrado — "
            "/eveadm exige bIsAdmin() se AdminGroups estiver vazio.");
        return;
    }
    g_fnW = reinterpret_cast<FnIsInGroupW>(raw);
    Log::GetLog()->info("ArkEventHunt: Permissions ligado (IsPlayerInGroup).");
}

bool IsInGroup(uint64_t steam_id, const std::string& group) {
    if (group == "Default") return true;
    if (g_fnW) {
        std::wstring wg(group.begin(), group.end());
        return g_fnW(static_cast<unsigned __int64>(steam_id), wg.c_str());
    }
    if (g_fnA)
        return g_fnA(static_cast<unsigned __int64>(steam_id), group.c_str());
    return false;
}

bool IsInAnyGroup(uint64_t steam_id, const std::vector<std::string>& groups) {
    if (groups.empty()) return false;
    for (const auto& g : groups) {
        if (IsInGroup(steam_id, g)) return true;
    }
    return false;
}

} // namespace Perms
} // namespace ArkEventHunt
