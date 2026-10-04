#include "pch.h"
#include "PlayerPoints.h"

namespace {

// CustomShop exporta CustomShop_GetPoints / CustomShop_SpendPoints / CustomShop_PointsReady.
// ArkShop (se existir) usa GetPoints(uint64) e SpendPoints(int, uint64).
using FnReady = bool(__cdecl*)();
using FnGetPoints = int(__cdecl*)(unsigned __int64);
using FnSpendPoints = bool(__cdecl*)(int, unsigned __int64);

FnReady g_ready = nullptr;
FnGetPoints g_get = nullptr;
FnSpendPoints g_spend = nullptr;
bool g_logged_miss = false;

bool BindExports(HMODULE h, bool custom_shop) {
    if (!h) return false;

    if (custom_shop) {
        auto* get = reinterpret_cast<FnGetPoints>(
            GetProcAddress(h, "CustomShop_GetPoints"));
        auto* spend = reinterpret_cast<FnSpendPoints>(
            GetProcAddress(h, "CustomShop_SpendPoints"));
        if (get && spend) {
            g_get = get;
            g_spend = spend;
            g_ready = reinterpret_cast<FnReady>(
                GetProcAddress(h, "CustomShop_PointsReady"));
            return true;
        }
        return false;
    }

    static const char* kGetNames[] = {
        "GetPoints",
        "?GetPoints@Points@ArkShop@@YAH_K@Z",
        "?GetPoints@Points@ArkShop@@YAHAE_K@Z",
    };
    static const char* kSpendNames[] = {
        "SpendPoints",
        "?SpendPoints@Points@ArkShop@@YA_NH_K@Z",
        "?SpendPoints@Points@ArkShop@@YA_NHAE_K@Z",
    };

    FnGetPoints get = nullptr;
    FnSpendPoints spend = nullptr;
    for (const char* n : kGetNames) {
        get = reinterpret_cast<FnGetPoints>(GetProcAddress(h, n));
        if (get) break;
    }
    for (const char* n : kSpendNames) {
        spend = reinterpret_cast<FnSpendPoints>(GetProcAddress(h, n));
        if (spend) break;
    }
    if (!get || !spend) return false;
    g_get = get;
    g_spend = spend;
    g_ready = nullptr;
    return true;
}

bool TryKnownModules() {
    static const wchar_t* kCustom[] = {L"CustomShop.dll", L"CustomShop"};
    for (const wchar_t* name : kCustom) {
        if (BindExports(GetModuleHandleW(name), true)) return true;
    }
    static const wchar_t* kArk[] = {L"ArkShop.dll", L"ArkShop"};
    for (const wchar_t* name : kArk) {
        if (BindExports(GetModuleHandleW(name), false)) return true;
    }
    return false;
}

// O nome do módulo no processo nem sempre é "CustomShop.dll".
bool TryScanExports() {
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, 0);
    if (snap == INVALID_HANDLE_VALUE) return false;

    MODULEENTRY32W me{};
    me.dwSize = sizeof(me);
    bool found = false;
    for (BOOL ok = Module32FirstW(snap, &me); ok; ok = Module32NextW(snap, &me)) {
        HMODULE h = me.hModule;
        if (BindExports(h, true) || BindExports(h, false)) {
            found = true;
            break;
        }
    }
    CloseHandle(snap);
    return found;
}

void TryBind() {
    if (g_get && g_spend) return;

    const bool ok = TryKnownModules() || TryScanExports();
    if (ok) {
        g_logged_miss = false;
        Log::GetLog()->info(
            "ArkPlayer: pontos ligados (CustomShop/ArkShop). Cobrança ativa.");
        return;
    }
    if (!g_logged_miss) {
        g_logged_miss = true;
        Log::GetLog()->info(
            "ArkPlayer: API de pontos ainda não encontrada — "
            "o próximo comando tenta de novo. "
            "EverythingIsFREE ou preço 0 seguem sem cobrar.");
    }
}

} // namespace

namespace ArkPlayer {
namespace Points {

void Init() { TryBind(); }

bool Available() {
    TryBind();
    if (!g_get || !g_spend) return false;
    if (g_ready && !g_ready()) return false;
    return true;
}

int GetPoints(uint64_t steam_id) {
    if (!Available() || steam_id == 0) return -1;
    return g_get(steam_id);
}

bool SpendPoints(uint64_t steam_id, int amount) {
    if (amount <= 0) return true;
    if (!Available() || steam_id == 0) return false;
    const int balance = g_get(steam_id);
    if (balance < 0 || balance < amount) return false;
    return g_spend(amount, steam_id);
}

} // namespace Points
} // namespace ArkPlayer
