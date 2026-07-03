#include "pch.h"
#include "ShopEngrams.h"
#include "ShopBridge.h"

#include <chrono>
#include <cctype>
#include <mutex>
#include <unordered_map>

namespace {

UPrimalGameData* GetPrimalGameData() {
    UEngine* engine = Globals::GEngine().Get();
    if (!engine) return nullptr;

    auto* singleton = static_cast<UPrimalGlobals*>(engine->GameSingletonField());
    if (!singleton) return nullptr;

    if (singleton->PrimalGameDataOverrideField())
        return singleton->PrimalGameDataOverrideField();
    return singleton->PrimalGameDataField();
}

bool LooksLikeTekEngram(UPrimalEngramEntry* entry) {
    if (!entry) return false;

    FString name;
    entry->NameField().ToString(&name);
    return name.Contains(L"Tek", ESearchCase::IgnoreCase);
}

void ForceUnlockEntry(AShooterPlayerState* player_state,
                      TSubclassOf<UPrimalItem> engram_class) {
    if (!player_state || !engram_class.uClass) return;
    if (player_state->HasEngram(engram_class)) return;
    player_state->ServerUnlockEngram(engram_class, true, true);
}

struct PendingEngramUnlock {
    std::chrono::steady_clock::time_point expires;
};

std::mutex g_engram_pending_mutex;
std::unordered_map<std::string, PendingEngramUnlock> g_engram_pending;

std::string NormalizeCommandToken(std::string cmd) {
    while (!cmd.empty() && std::isspace(static_cast<unsigned char>(cmd.front())))
        cmd.erase(cmd.begin());
    while (!cmd.empty() && std::isspace(static_cast<unsigned char>(cmd.back())))
        cmd.pop_back();
    for (char& ch : cmd)
        ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
    return cmd;
}

} // anonymous namespace

namespace CustomShop {
namespace Engrams {

bool UnlockAll(AShooterPlayerController* controller, bool tek_only, int* out_unlocked) {
    if (out_unlocked) *out_unlocked = 0;
    if (!controller) return false;

    auto* player_state = controller->GetShooterPlayerState();
    if (!player_state) {
        Log::GetLog()->warn("ShopEngrams: player has no ShooterPlayerState");
        return false;
    }

    if (ArkApi::IApiUtils::IsPlayerDead(controller)) {
        Log::GetLog()->warn("ShopEngrams: cannot unlock engrams for dead player");
        return false;
    }

    const int saved_free_points = player_state->FreeEngramPointsField();
    const int saved_total_points = player_state->TotalEngramPointsField();

    if (tek_only)
        controller->GiveEngrams(true, true);

    auto* game_data = GetPrimalGameData();
    if (!game_data) {
        if (tek_only) {
            player_state->FreeEngramPointsField() = saved_free_points;
            player_state->TotalEngramPointsField() = saved_total_points;
            Log::GetLog()->info("ShopEngrams: GiveEngrams tek-only — PrimalGameData unavailable");
            return true;
        }
        Log::GetLog()->warn("ShopEngrams: PrimalGameData unavailable");
        return false;
    }

    int unlocked = 0;
    const TArray<UPrimalEngramEntry*>& entries =
        game_data->EngramBlueprintEntriesField();

    for (UPrimalEngramEntry* entry : entries) {
        if (!entry) continue;
        if (tek_only && !LooksLikeTekEngram(entry)) continue;

        const auto engram_class = entry->BluePrintEntryField();
        if (!engram_class.uClass) continue;

        if (!player_state->HasEngram(engram_class)) {
            ForceUnlockEntry(player_state, engram_class);
            ++unlocked;
        }
    }

    player_state->FreeEngramPointsField() = saved_free_points;
    player_state->TotalEngramPointsField() = saved_total_points;

    if (out_unlocked) *out_unlocked = unlocked;

    Log::GetLog()->info(
        "ShopEngrams: unlocked {} engram(s) from {} registered (tek_only={})",
        unlocked, entries.Num(), tek_only);
    return true;
}

bool RequestUnlockAll(AShooterPlayerController* controller) {
    if (!controller) return false;

    if (ArkApi::IApiUtils::IsPlayerDead(controller)) {
        Log::GetLog()->warn("ShopEngrams: cannot request unlock for dead player");
        return false;
    }

    const std::string sid = Bridge::GetSteamId(controller);
    if (sid.empty()) return false;

    PendingEngramUnlock pending;
    pending.expires = std::chrono::steady_clock::now() + std::chrono::minutes(2);
    {
        std::lock_guard<std::mutex> lock(g_engram_pending_mutex);
        g_engram_pending[sid] = pending;
    }
    return true;
}

bool HasPendingUnlock(const std::string& steam_id) {
    std::lock_guard<std::mutex> lock(g_engram_pending_mutex);
    const auto it = g_engram_pending.find(steam_id);
    if (it == g_engram_pending.end()) return false;
    return std::chrono::steady_clock::now() <= it->second.expires;
}

bool ConfirmUnlockAll(const std::string& steam_id, AShooterPlayerController* controller,
                      int* out_unlocked) {
    if (!controller || steam_id.empty()) return false;

    {
        std::lock_guard<std::mutex> lock(g_engram_pending_mutex);
        const auto it = g_engram_pending.find(steam_id);
        if (it == g_engram_pending.end()) return false;
        if (std::chrono::steady_clock::now() > it->second.expires) {
            g_engram_pending.erase(it);
            return false;
        }
        g_engram_pending.erase(it);
    }

    return UnlockAll(controller, false, out_unlocked);
}

bool IsUnlockAllCommand(const std::string& cmd) {
    const std::string n = NormalizeCommandToken(cmd);
    if (n == "shop.unlockallengrams" || n == "shop.learnallengrams")
        return true;
    if (n.rfind("shop.unlockallengrams ", 0) == 0) return true;
    if (n.rfind("shop.learnallengrams ", 0) == 0) return true;
    return false;
}

bool ParseTekOnlyFlag(const std::string& cmd) {
    const auto pos = cmd.find(' ');
    if (pos == std::string::npos) return false;
    std::string arg = cmd.substr(pos + 1);
    for (char& ch : arg)
        ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
    return arg == "tekonly" || arg == "tek";
}

} // namespace Engrams
} // namespace CustomShop
