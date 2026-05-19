#include "pch.h"
#include "ShopPerms.h"

namespace {

// Two possible export signatures for the Permissions plugin.
using FnIsInGroupW = bool(*)(unsigned __int64, const wchar_t*);
using FnIsInGroupA = bool(*)(unsigned __int64, const char*);

static FnIsInGroupW g_fnW     = nullptr;
static FnIsInGroupA g_fnA     = nullptr;
static bool         g_ready   = false;

} // namespace

namespace CustomShop {
namespace Perms {

void Init() {
    if (g_ready) return;
    g_ready = true;

    // The Permissions plugin loads before other plugins; by Plugin_Init
    // time its DLL is already mapped into the process.
    HMODULE hMod = GetModuleHandleW(L"Permissions");
    if (!hMod)
        hMod = GetModuleHandleW(L"Permissions.dll");

    if (!hMod) {
        Log::GetLog()->warn(
            "ShopPerms: Permissions plugin not found — "
            "kit access-control and group points are disabled.");
        return;
    }

    // Try wide-char export first (most common in modern builds).
    g_fnW = reinterpret_cast<FnIsInGroupW>(
        GetProcAddress(hMod, "IsPlayerInGroup"));

    if (!g_fnW) {
        // Fallback: narrow-char export.
        g_fnA = reinterpret_cast<FnIsInGroupA>(
            GetProcAddress(hMod, "IsPlayerInGroup"));
    }

    if (g_fnW || g_fnA) {
        Log::GetLog()->info(
            "ShopPerms: bound to Permissions plugin ({}).",
            g_fnW ? "wide" : "narrow");
    } else {
        Log::GetLog()->warn(
            "ShopPerms: Permissions.dll found but IsPlayerInGroup "
            "export not resolved — group checks disabled.");
    }
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
