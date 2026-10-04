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

bool g_logged_world_mode = false;

bool IsPlayerStatus(UPrimalCharacterStatusComponent* status) {
    if (!status) return false;
    AActor* owner = status->GetPrimalCharacter();
    if (!owner) return false;
    return owner->IsA(AShooterCharacter::GetPrivateStaticClass());
}

AShooterGameMode* AsShooterGameMode(AGameMode* mode) {
    if (!mode) return nullptr;
    if (!mode->IsA(AShooterGameMode::StaticClass())) return nullptr;
    return static_cast<AShooterGameMode*>(mode);
}

AShooterGameMode* ModeFromWorld(UWorld* world) {
    if (!world) return nullptr;
    if (AShooterGameMode* mode = AsShooterGameMode(world->AuthorityGameModeField()))
        return mode;
    return AsShooterGameMode(world->GetAuthGameMode());
}

bool IsWorldObject(UObject* object) {
    if (!object) return false;
    UClass* cls = object->ClassField();
    if (!cls) return false;
    return cls->NameField() == L"World";
}

// Outer do componente é o actor, o do actor é o level, o do level é o UWorld.
UWorld* WorldFromOuter(UObject* object) {
    UObject* cursor = object;
    for (int step = 0; cursor && step < 12; ++step) {
        if (IsWorldObject(cursor))
            return static_cast<UWorld*>(cursor);
        UObject* outer = cursor->OuterField();
        if (!outer || outer == cursor) break;
        cursor = outer;
    }
    return nullptr;
}

AShooterGameMode* TakeWorldMode(UWorld* world, bool* used_world) {
    AShooterGameMode* mode = ModeFromWorld(world);
    if (!mode) return nullptr;
    if (used_world) *used_world = true;
    return mode;
}

AShooterGameMode* ModeFromActor(AActor* actor, bool* used_world) {
    if (!actor) return nullptr;
    if (AShooterGameMode* mode = TakeWorldMode(actor->GetWorld(), used_world))
        return mode;
    return TakeWorldMode(WorldFromOuter(actor), used_world);
}

// O getter global é o ponteiro que o ArkApi grava só em InitGame.
// Num apply real, o mundo do status / dono / outer / controller ainda tem o modo.
AShooterGameMode* ResolveGameMode(UPrimalCharacterStatusComponent* status,
                                  AShooterPlayerController* by_pc,
                                  bool* used_world) {
    if (used_world) *used_world = false;
    if (AShooterGameMode* cached = ArkApi::GetApiUtils().GetShooterGameMode())
        return cached;

    if (status) {
        if (AShooterGameMode* mode = TakeWorldMode(status->WorldField(), used_world))
            return mode;
        if (AShooterGameMode* mode = TakeWorldMode(status->GetWorld(), used_world))
            return mode;
        if (AShooterGameMode* mode = ModeFromActor(status->GetOwner(), used_world))
            return mode;
        if (AShooterGameMode* mode = ModeFromActor(status->CachedOwnerField(), used_world))
            return mode;
        if (AShooterGameMode* mode = ModeFromActor(status->GetPrimalCharacter(), used_world))
            return mode;
        if (AShooterGameMode* mode = TakeWorldMode(WorldFromOuter(status), used_world))
            return mode;
    }
    if (by_pc) {
        if (AShooterGameMode* mode = ModeFromActor(by_pc, used_world))
            return mode;
    }
    return TakeWorldMode(ArkApi::GetApiUtils().GetWorld(), used_world);
}

bool IndexSaved(int index) {
    for (const auto& slot : g_saved_points) {
        if (slot.first == index) return true;
    }
    return false;
}

// Lê a flag e as linhas de buyout na primeira vez que o GameMode existe.
// Nas seguintes só reafirma false / 0. Não guarda o zero como se fosse o original.
bool ApplyCrashMask(UPrimalCharacterStatusComponent* status,
                    AShooterPlayerController* by_pc) {
    bool from_world = false;
    AShooterGameMode* game_mode = ResolveGameMode(status, by_pc, &from_world);
    if (!game_mode) return false;
    if (from_world && !g_logged_world_mode) {
        g_logged_world_mode = true;
        Log::GetLog()->info(
            "EngramLevel: GetShooterGameMode() nulo; GameMode lido pelo mundo do personagem");
    }

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
    AShooterGameMode* game_mode = ResolveGameMode(nullptr, nullptr, nullptr);
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

    if (cfg.SuppressAutoUnlock() && !ApplyCrashMask(status, by_pc)) {
        Log::GetLog()->error(
            "EngramLevel: ServerApplyLevelUp sem GameMode alcançável — original não foi chamado e a flag não foi reativada");
        return;
    }

    UPrimalCharacterStatusComponent_ServerApplyLevelUp_original(
        status, value_type, by_pc);

    // A fila não corre aqui. Quem ligou /autoengram só arma a releitura
    // (não tek até o nível atual) para daqui a 1 segundo.
    if (by_pc && cfg.UnlockOnlyAppliedLevel()) {
        const uint64 steam = ArkApi::GetApiUtils().GetSteamIdFromController(by_pc);
        const std::string sid = steam != 0 ? std::to_string(steam) : "";
        if (EngramLevel::Prefs::IsAutoEnabled(sid))
            EngramLevel::ScheduleOwnedReread(by_pc);
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
    // Plugin_Init e Reload correm antes de InitGame. Getter nulo aí é o arranque:
    // sem log. O primeiro ServerApplyLevelUp real é que mascara.
    ApplyCrashMask(nullptr, nullptr);
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
