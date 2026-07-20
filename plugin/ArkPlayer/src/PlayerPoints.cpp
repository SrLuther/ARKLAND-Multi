#include "pch.h"
#include "PlayerPoints.h"

namespace {

// Assinaturas típicas do ArkShop (MSVC x64 mangling).
using FnGetPoints = int(__cdecl*)(unsigned __int64);
using FnSpendPoints = bool(__cdecl*)(int, unsigned __int64);

FnGetPoints g_get = nullptr;
FnSpendPoints g_spend = nullptr;
bool g_tried = false;

bool TryBindModule(HMODULE h) {
    if (!h) return false;

    // Prefer C exports se existirem.
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
    if (get && spend) {
        g_get = get;
        g_spend = spend;
        return true;
    }
    return false;
}

void TryBind() {
    if (g_tried) return;
    g_tried = true;

    static const wchar_t* kMods[] = {
        L"ArkShop.dll", L"ArkShop",
        L"CustomShop.dll", L"CustomShop",
    };
    for (const wchar_t* name : kMods) {
        if (TryBindModule(GetModuleHandleW(name))) {
            Log::GetLog()->info("ArkPlayer: pontos ligados via módulo shop.");
            return;
        }
    }
    Log::GetLog()->info(
        "ArkPlayer: ArkShop Points API indisponível — custos >0 serão recusados "
        "(EverythingIsFREE ou preço 0 ainda funcionam).");
}

} // namespace

namespace ArkPlayer {
namespace Points {

void Init() { TryBind(); }

bool Available() {
    TryBind();
    return g_get && g_spend;
}

int GetPoints(uint64_t steam_id) {
    TryBind();
    if (!g_get) return 0;
    return g_get(steam_id);
}

bool SpendPoints(uint64_t steam_id, int amount) {
    if (amount <= 0) return true;
    TryBind();
    if (!g_spend) return false;
    if (GetPoints(steam_id) < amount) return false;
    return g_spend(amount, steam_id);
}

} // namespace Points
} // namespace ArkPlayer
