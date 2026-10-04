#include "pch.h"
#include "EngramCommands.h"
#include "EngramConfig.h"
#include "EngramGrant.h"
#include "EngramHooks.h"

#include <utility>
#include <vector>

namespace {

bool g_in_level_up = false;

bool g_mask_captured = false;
bool g_saved_auto_unlock = false;
std::vector<std::pair<int, int>> g_saved_points;

bool IsPlayerStatus(UPrimalCharacterStatusComponent* status) {
    if (!status) return false;
    AActor* owner = status->GetPrimalCharacter();
    if (!owner) return false;
    return owner->IsA(AShooterCharacter::GetPrivateStaticClass());
}

bool IndexSaved(int index) {
    for (const auto& slot : g_saved_points) {
        if (slot.first == index) return true;
    }
    return false;
}

// Lê a flag e as linhas de buyout na primeira vez que o GameMode existe.
// Nas seguintes só reafirma false / 0. Não guarda o zero como se fosse o original.
bool ApplyCrashMask() {
    AShooterGameMode* game_mode = ArkApi::GetApiUtils().GetShooterGameMode();
    if (!game_mode) return false;

    const int buyout = EngramLevel::Config::Get().CatalogBuyoutPoints();
    TArray<int>& points = game_mode->OverridePlayerLevelEngramPointsField();
    if (!g_mask_captured) {
        g_saved_auto_unlock = game_mode->bAutoUnlockAllEngramsField();
        g_saved_points.clear();
        for (int i = 0; i < points.Num(); ++i) {
            if (!points.IsValidIndex(i)) continue;
            if (!EngramLevel::IsCatalogBuyout(points[i], buyout)) continue;
            g_saved_points.emplace_back(i, points[i]);
        }
        g_mask_captured = true;
        Log::GetLog()->info(
            "EngramLevel: bAutoUnlockAllEngrams fica false e {} linha(s) >= {} ficam em 0 enquanto o plugin estiver ligado",
            g_saved_points.size(), buyout);
    }

    game_mode->bAutoUnlockAllEngramsField() = false;
    for (int i = 0; i < points.Num(); ++i) {
        if (!points.IsValidIndex(i)) continue;
        if (!EngramLevel::IsCatalogBuyout(points[i], buyout)) continue;
        if (!IndexSaved(i))
            g_saved_points.emplace_back(i, points[i]);
        points[i] = 0;
    }
    return true;
}

void RestoreCrashMask() {
    if (!g_mask_captured) return;
    AShooterGameMode* game_mode = ArkApi::GetApiUtils().GetShooterGameMode();
    if (!game_mode) {
        Log::GetLog()->error(
            "EngramLevel: GetShooterGameMode() nulo — não restaurou bAutoUnlockAllEngrams lido no load; a flag não foi reativada");
        return;
    }

    TArray<int>& points = game_mode->OverridePlayerLevelEngramPointsField();
    for (const auto& slot : g_saved_points) {
        if (points.IsValidIndex(slot.first))
            points[slot.first] = slot.second;
    }
    game_mode->bAutoUnlockAllEngramsField() = g_saved_auto_unlock;
    g_saved_points.clear();
    g_mask_captured = false;
    Log::GetLog()->info(
        "EngramLevel: restaurou bAutoUnlockAllEngrams e os OverridePlayerLevelEngramPoints lidos no load");
}

DECLARE_HOOK(UPrimalCharacterStatusComponent_ServerApplyLevelUp, void,
             UPrimalCharacterStatusComponent*, EPrimalCharacterStatusValue::Type,
             AShooterPlayerController*);

void Hook_UPrimalCharacterStatusComponent_ServerApplyLevelUp(
    UPrimalCharacterStatusComponent* status,
    EPrimalCharacterStatusValue::Type value_type,
    AShooterPlayerController* by_pc) {
    const auto& cfg = EngramLevel::Config::Get();
    if (!status || !cfg.Enabled() || !IsPlayerStatus(status) || g_in_level_up) {
        UPrimalCharacterStatusComponent_ServerApplyLevelUp_original(
            status, value_type, by_pc);
        return;
    }

    g_in_level_up = true;
    struct ClearInLevelUp {
        ~ClearInLevelUp() { g_in_level_up = false; }
    } clear_in_level_up;

    if (cfg.SuppressAutoUnlock() && !ApplyCrashMask()) {
        Log::GetLog()->error(
            "EngramLevel: GetShooterGameMode() nulo — ServerApplyLevelUp original não foi chamado e a flag não foi reativada");
        return;
    }

    const int before_base = status->GetBaseLevelFromLevelUpPoints(true);
    const int before_char = status->GetCharacterLevel();
    const int available_before = status->GetNumLevelUpsAvailable();

    UPrimalCharacterStatusComponent_ServerApplyLevelUp_original(
        status, value_type, by_pc);

    const int after_base = status->GetBaseLevelFromLevelUpPoints(true);
    const int after_char = status->GetCharacterLevel();
    const int available_after = status->GetNumLevelUpsAvailable();
    const std::vector<int> levels = EngramLevel::AppliedLevelSpan(
        before_base, after_base, before_char, after_char,
        available_before, available_after);

    int unlocked = 0;
    if (by_pc && cfg.UnlockOnlyAppliedLevel() && !levels.empty()) {
        const uint64 steam = ArkApi::GetApiUtils().GetSteamIdFromController(by_pc);
        const std::string sid = steam != 0 ? std::to_string(steam) : "";
        if (EngramLevel::Prefs::IsAutoEnabled(sid)) {
            if (levels.size() > 1)
                unlocked = EngramLevel::UnlockSpentLevels(by_pc, levels);
            else
                unlocked = EngramLevel::UnlockExactLevel(by_pc, levels.front(), after_char);
        }
    }

    if (unlocked > 0) {
        Log::GetLog()->info(
            "EngramLevel: {} nível(is) — {} engrama(s) (auto-unlock continua suprimido)",
            levels.size(), unlocked);
    }
}

} // namespace

namespace EngramLevel {
namespace Hooks {

void SyncCrashMask() {
    const auto& cfg = Config::Get();
    if (!cfg.Enabled() || !cfg.SuppressAutoUnlock()) {
        RestoreCrashMask();
        return;
    }
    if (!ApplyCrashMask()) {
        Log::GetLog()->error(
            "EngramLevel: GetShooterGameMode() nulo — não mascarou bAutoUnlockAllEngrams; a flag não foi reativada");
    }
}

void ReleaseCrashMask() {
    RestoreCrashMask();
}

void Register() {
    ArkApi::GetHooks().SetHook(
        "UPrimalCharacterStatusComponent.ServerApplyLevelUp(EPrimalCharacterStatusValue::Type,AShooterPlayerController*)",
        Hook_UPrimalCharacterStatusComponent_ServerApplyLevelUp,
        &UPrimalCharacterStatusComponent_ServerApplyLevelUp_original);
    Log::GetLog()->info(
        "EngramLevel: hook ServerApplyLevelUp (máscara fica enquanto Enabled; sem buyout)");
}

void Unregister() {
    ArkApi::GetHooks().DisableHook(
        "UPrimalCharacterStatusComponent.ServerApplyLevelUp(EPrimalCharacterStatusValue::Type,AShooterPlayerController*)",
        Hook_UPrimalCharacterStatusComponent_ServerApplyLevelUp);
}

} // namespace Hooks
} // namespace EngramLevel
