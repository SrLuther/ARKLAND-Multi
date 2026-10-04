#include "pch.h"
#include "EngramConfig.h"
#include "EngramGrant.h"

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

bool EntryLooksTek(UPrimalEngramEntry* entry) {
    if (!entry) return false;
    FString name;
    entry->NameField().ToString(&name);
    if (name.Contains(L"Tek", ESearchCase::IgnoreCase)) return true;
    FString pretty;
    entry->GetEngramName(&pretty);
    return pretty.Contains(L"Tek", ESearchCase::IgnoreCase);
}

std::string EntryInternalName(UPrimalEngramEntry* entry) {
    FString name;
    entry->NameField().ToString(&name);
    return name.ToString();
}

std::string EntryShownName(UPrimalEngramEntry* entry) {
    FString pretty;
    entry->GetEngramName(&pretty);
    return pretty.ToString();
}

int RequiredLevelOf(UPrimalEngramEntry* entry) {
    int required = entry->GetRequiredLevel();
    if (required <= 0)
        required = entry->RequiredCharacterLevelField();
    return required;
}

bool EntryAllowed(UPrimalEngramEntry* entry, const EngramLevel::Config& cfg) {
    const std::string internal = EntryInternalName(entry);
    const std::string shown = EntryShownName(entry);
    if (EngramLevel::EngramListHits(internal, shown, cfg.RemovedEngrams()))
        return false;
    if (!cfg.UseConfiguredEngramList()) return true;
    return EngramLevel::EngramListHits(internal, shown, cfg.Engrams()) ||
           EngramLevel::EngramListHits(internal, shown, cfg.ExtraEngrams());
}

struct PointsGuard {
    AShooterPlayerState* player_state = nullptr;
    int saved_free = 0;
    int saved_total = 0;

    explicit PointsGuard(AShooterPlayerState* state) : player_state(state) {
        if (!player_state) return;
        saved_free = player_state->FreeEngramPointsField();
        saved_total = player_state->TotalEngramPointsField();
    }

    ~PointsGuard() {
        if (!player_state) return;
        player_state->FreeEngramPointsField() = saved_free;
        player_state->TotalEngramPointsField() = saved_total;
    }
};

int GrantExactTier(AShooterPlayerState* player_state,
                   const TArray<UPrimalEngramEntry*>& entries,
                   int level,
                   EngramLevel::GrantTier tier) {
    if (!player_state || level <= 0 || tier == EngramLevel::GrantTier::None)
        return 0;
    const bool want_tek = tier == EngramLevel::GrantTier::Tek;
    const EngramLevel::Config& cfg = EngramLevel::Config::Get();
    int unlocked = 0;
    for (int i = 0; i < entries.Num(); ++i) {
        if (!entries.IsValidIndex(i)) continue;
        UPrimalEngramEntry* entry = entries[i];
        if (!entry || !EntryAllowed(entry, cfg)) continue;
        if (EntryLooksTek(entry) != want_tek) continue;
        const int required = RequiredLevelOf(entry);
        if (required != level) continue;

        const auto engram_class = entry->BluePrintEntryField();
        if (!engram_class.uClass) continue;
        if (player_state->HasEngram(engram_class)) continue;

        player_state->ServerUnlockEngram(engram_class, true, true);
        ++unlocked;
    }
    return unlocked;
}

bool AnyLockedNonTek(AShooterPlayerState* player_state,
                     const TArray<UPrimalEngramEntry*>& entries,
                     int level) {
    const EngramLevel::Config& cfg = EngramLevel::Config::Get();
    for (int i = 0; i < entries.Num(); ++i) {
        if (!entries.IsValidIndex(i)) continue;
        UPrimalEngramEntry* entry = entries[i];
        if (!entry || EntryLooksTek(entry) || !EntryAllowed(entry, cfg)) continue;
        const int required = RequiredLevelOf(entry);
        if (required != level) continue;
        const auto engram_class = entry->BluePrintEntryField();
        if (!engram_class.uClass) continue;
        if (!player_state->HasEngram(engram_class)) return true;
    }
    return false;
}

struct GrantContext {
    AShooterPlayerController* controller = nullptr;
    AShooterPlayerState* player_state = nullptr;
    UPrimalGameData* game_data = nullptr;
    TArray<UPrimalEngramEntry*> entries;
};

bool OpenGrant(AShooterPlayerController* controller, GrantContext& ctx) {
    if (!controller) return false;
    ctx.controller = controller;
    ctx.player_state = controller->GetShooterPlayerState();
    if (!ctx.player_state) return false;
    if (ArkApi::IApiUtils::IsPlayerDead(controller)) return false;
    ctx.game_data = GetPrimalGameData();
    if (!ctx.game_data) {
        Log::GetLog()->warn("EngramLevel: PrimalGameData indisponível");
        return false;
    }
    ctx.entries = ctx.game_data->EngramBlueprintEntriesField();
    return true;
}

} // namespace

namespace EngramLevel {

int UnlockExactLevel(AShooterPlayerController* controller, int level,
                     int character_level) {
    if (!controller || level <= 0) return 0;
    (void)character_level;

    GrantContext ctx;
    if (!OpenGrant(controller, ctx)) return 0;

    const Config& cfg = Config::Get();
    const bool any_locked_non_tek =
        cfg.UnlockTotal() && AnyLockedNonTek(ctx.player_state, ctx.entries, level);
    const GrantTier tier = ChooseGrantTier(
        cfg.UnlockNonTek(), cfg.UnlockTotal(), any_locked_non_tek);
    if (tier == GrantTier::None) return 0;

    PointsGuard points(ctx.player_state);
    return GrantExactTier(ctx.player_state, ctx.entries, level, tier);
}

int UnlockSpentLevels(AShooterPlayerController* controller,
                      const std::vector<int>& levels) {
    if (!controller || levels.size() <= 1) return 0;

    GrantContext ctx;
    if (!OpenGrant(controller, ctx)) return 0;

    const Config& cfg = Config::Get();
    const auto batches = GrantBatchesForSpentLevels(
        levels, cfg.UnlockNonTek(), cfg.UnlockTotal());
    PointsGuard points(ctx.player_state);
    int unlocked = 0;
    for (const auto& batch : batches) {
        const GrantTier tier = batch.second ? GrantTier::Tek : GrantTier::NonTek;
        unlocked += GrantExactTier(ctx.player_state, ctx.entries, batch.first, tier);
    }
    return unlocked;
}

} // namespace EngramLevel
