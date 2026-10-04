#include "pch.h"
#include "EngramCommands.h"
#include "EngramConfig.h"
#include "EngramGrant.h"

#include <Timer.h>

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
    // A tela agrupa pelo campo. GetRequiredLevel só entra se o campo vier 0.
    const int field = entry->RequiredCharacterLevelField();
    if (field > 0) return field;
    return entry->GetRequiredLevel();
}

// A tela de engramas lê EngramItemBlueprints. HasEngram lê o set do servidor,
// que o mindwipe pode deixar cheio depois de esvaziar a lista replicada.
// ServerUnlockEngram então sai sem efeito e sem crash.
bool ShowsLearned(AShooterPlayerState* player_state, UClass* engram_class) {
    if (!player_state || !engram_class) return false;
    TArray<TSubclassOf<UPrimalItem>>& learned =
        player_state->EngramItemBlueprintsField();
    for (int i = 0; i < learned.Num(); ++i) {
        if (!learned.IsValidIndex(i)) continue;
        if (learned[i].uClass == engram_class) return true;
    }
    return false;
}

struct GrantStats {
    int unlocked = 0;
    int known = 0;
    int eligible = 0;
};

void UnlockBlueprint(AShooterPlayerController* controller,
                     AShooterPlayerState* player_state,
                     TSubclassOf<UPrimalItem> engram_class,
                     bool tek,
                     GrantStats& stats) {
    if (ShowsLearned(player_state, engram_class.uClass)) {
        ++stats.known;
        ++stats.eligible;
        return;
    }
    ++stats.eligible;
    player_state->ServerUnlockEngram(engram_class, true, true);
    if (!ShowsLearned(player_state, engram_class.uClass)) {
        player_state->EngramItemBlueprintsField().Add(engram_class);
        player_state->ForceNetUpdate(false, true, false);
        if (controller)
            controller->ClientNotifyUnlockedEngram(engram_class, tek);
    }
    ++stats.unlocked;
}

bool EntryAllowed(UPrimalEngramEntry* entry, const EngramLevel::Config& cfg) {
    const std::string internal = EntryInternalName(entry);
    const std::string shown = EntryShownName(entry);
    if (EngramLevel::EngramIdRejected(internal)) return false;
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

GrantStats GrantEntries(AShooterPlayerController* controller,
                       AShooterPlayerState* player_state,
                       const TArray<UPrimalEngramEntry*>& entries,
                       int level,
                       bool up_to,
                       EngramLevel::GrantTier tier) {
    GrantStats stats;
    if (!player_state || level <= 0 || tier == EngramLevel::GrantTier::None)
        return stats;
    const bool want_tek = tier == EngramLevel::GrantTier::Tek;
    if (up_to && want_tek) return stats;
    const EngramLevel::Config& cfg = EngramLevel::Config::Get();
    for (int i = 0; i < entries.Num(); ++i) {
        if (!entries.IsValidIndex(i)) continue;
        UPrimalEngramEntry* entry = entries[i];
        if (!entry || !EntryAllowed(entry, cfg)) continue;
        if (EntryLooksTek(entry) != want_tek) continue;
        const int required = RequiredLevelOf(entry);
        if (up_to) {
            if (!EngramLevel::OwnedNonTekFits(required, level)) continue;
        } else if (required != level) {
            continue;
        }

        const auto engram_class = entry->BluePrintEntryField();
        if (!engram_class.uClass) continue;
        UnlockBlueprint(controller, player_state, engram_class, want_tek, stats);
    }
    return stats;
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
        if (!ShowsLearned(player_state, engram_class.uClass)) return true;
    }
    return false;
}

struct GrantContext {
    AShooterPlayerController* controller = nullptr;
    AShooterPlayerState* player_state = nullptr;
    UPrimalGameData* game_data = nullptr;
    TArray<UPrimalEngramEntry*> entries;
};

bool OpenGrant(AShooterPlayerController* controller, GrantContext& ctx,
               EngramLevel::UnlockMiss& miss) {
    miss = EngramLevel::UnlockMiss::NoPlayer;
    if (!controller) return false;
    ctx.controller = controller;
    ctx.player_state = controller->GetShooterPlayerState();
    if (!ctx.player_state || ArkApi::IApiUtils::IsPlayerDead(controller))
        return false;
    ctx.game_data = GetPrimalGameData();
    if (!ctx.game_data) {
        miss = EngramLevel::UnlockMiss::EmptyList;
        Log::GetLog()->warn("EngramLevel: PrimalGameData indisponível");
        return false;
    }
    ctx.entries = ctx.game_data->EngramBlueprintEntriesField();
    if (ctx.entries.Num() <= 0) {
        miss = EngramLevel::UnlockMiss::EmptyList;
        return false;
    }
    miss = EngramLevel::UnlockMiss::None;
    return true;
}

EngramLevel::UnlockMiss MissFor(const GrantStats& stats) {
    if (stats.unlocked > 0) return EngramLevel::UnlockMiss::None;
    if (stats.eligible > 0 && stats.known == stats.eligible)
        return EngramLevel::UnlockMiss::AlreadyKnown;
    return EngramLevel::UnlockMiss::NoneAtLevel;
}

struct Scan {
    EngramLevel::UnlockReport report;
    std::vector<UClass*> classes;
};

// A mesma releitura do /autoengram que já soltou engrama no jogo:
// não tek, RequiredCharacterLevel <= nível atual, fora de EngramItemBlueprints.
Scan ScanOwnedNonTek(AShooterPlayerController* controller) {
    Scan scan;
    if (!controller) {
        scan.report.miss = EngramLevel::UnlockMiss::NoPlayer;
        return scan;
    }

    GrantContext ctx;
    if (!OpenGrant(controller, ctx, scan.report.miss)) return scan;

    const EngramLevel::Config& cfg = EngramLevel::Config::Get();
    if (!cfg.UnlockNonTek() && !cfg.UnlockTotal()) {
        scan.report.miss = EngramLevel::UnlockMiss::NoneAtLevel;
        return scan;
    }

    int character_level = 0;
    if (AShooterCharacter* character = controller->GetPlayerCharacter()) {
        if (UPrimalCharacterStatusComponent* status =
                character->MyCharacterStatusComponentField())
            character_level = status->GetCharacterLevel();
    }
    if (character_level <= 0)
        character_level = ctx.player_state->GetCharacterLevel();
    scan.report.character_level = character_level;
    scan.report.target_level = character_level;
    if (character_level <= 0) {
        scan.report.miss = EngramLevel::UnlockMiss::LevelZero;
        return scan;
    }

    GrantStats stats;
    for (int i = 0; i < ctx.entries.Num(); ++i) {
        if (!ctx.entries.IsValidIndex(i)) continue;
        UPrimalEngramEntry* entry = ctx.entries[i];
        if (!entry || !EntryAllowed(entry, cfg)) continue;
        if (EntryLooksTek(entry)) continue;
        const int required = RequiredLevelOf(entry);
        if (!EngramLevel::OwnedNonTekFits(required, character_level)) continue;
        const auto engram_class = entry->BluePrintEntryField();
        if (!engram_class.uClass) continue;
        ++stats.eligible;
        if (ShowsLearned(ctx.player_state, engram_class.uClass)) {
            ++stats.known;
            continue;
        }
        bool seen = false;
        for (UClass* have : scan.classes) {
            if (have == engram_class.uClass) {
                seen = true;
                break;
            }
        }
        if (seen) continue;
        scan.classes.push_back(engram_class.uClass);
        ++stats.unlocked;
    }
    scan.report.unlocked = static_cast<int>(scan.classes.size());
    scan.report.miss = MissFor(stats);
    return scan;
}

struct Wave {
    int generation = 0;
    bool block_sent = false;
    bool timer_armed = false;
    bool arm_next = false;
    bool need_reread = false;
    int unlocked = 0;
    int level = 0;
    std::vector<UClass*> pending;
};

std::mutex g_wave_mu;
std::unordered_map<uint64, Wave> g_waves;
bool g_queue_timer = false;

bool Listed(const std::vector<UClass*>& pending, UClass* cls) {
    for (UClass* have : pending) {
        if (have == cls) return true;
    }
    return false;
}

std::unordered_map<uint64, Wave>::iterator WaveAt(uint64 steam) {
    for (auto it = g_waves.begin(); it != g_waves.end(); ++it) {
        if (it->first == steam) return it;
    }
    return g_waves.end();
}

void QueueTick(uint64 steam, int generation);

void ScheduleTick(uint64 steam, int generation) {
    API::Timer::Get().DelayExecute(
        &QueueTick, EngramLevel::kQueueDelaySeconds, steam, generation);
}

int SendBatch(AShooterPlayerController* controller, const std::vector<UClass*>& batch) {
    if (!controller || batch.empty()) return 0;
    AShooterPlayerState* player_state = controller->GetShooterPlayerState();
    if (!player_state || ArkApi::IApiUtils::IsPlayerDead(controller)) return 0;
    PointsGuard points(player_state);
    int sent = 0;
    for (UClass* cls : batch) {
        if (!cls || ShowsLearned(player_state, cls)) continue;
        GrantStats stats;
        UnlockBlueprint(controller, player_state, TSubclassOf<UPrimalItem>(cls), false, stats);
        sent += stats.unlocked;
    }
    return sent;
}

void RememberScan(Wave& wave, Scan& scan, bool replace) {
    if (scan.report.character_level > 0)
        wave.level = scan.report.character_level;
    if (replace) {
        wave.pending = std::move(scan.classes);
        return;
    }
    for (UClass* cls : scan.classes) {
        if (!Listed(wave.pending, cls))
            wave.pending.push_back(cls);
    }
    wave.need_reread = false;
}

void QueueTick(uint64 steam, int generation) {
    AShooterPlayerController* controller = nullptr;
    bool first = false;
    bool reread = false;
    {
        std::lock_guard<std::mutex> lock(g_wave_mu);
        const auto it = WaveAt(steam);
        if (it == g_waves.end() || it->second.generation != generation) return;
        Wave& wave = it->second;
        wave.timer_armed = false;
        if (!EngramLevel::Prefs::IsAutoEnabled(std::to_string(steam))) {
            wave.pending.clear();
            wave.block_sent = false;
            wave.arm_next = false;
            wave.need_reread = false;
            return;
        }
        controller = ArkApi::GetApiUtils().FindPlayerFromSteamId(steam);
        if (!controller) {
            wave.pending.clear();
            wave.block_sent = false;
            wave.arm_next = false;
            wave.need_reread = false;
            wave.unlocked = 0;
            return;
        }
        if (ArkApi::IApiUtils::IsPlayerDead(controller)) {
            wave.arm_next = true;
            return;
        }
        first = !wave.block_sent;
        reread = wave.block_sent && wave.need_reread;
    }

    if (first || reread) {
        Scan scan = ScanOwnedNonTek(controller);
        std::lock_guard<std::mutex> lock(g_wave_mu);
        const auto it = WaveAt(steam);
        if (it == g_waves.end() || it->second.generation != generation) return;
        Wave& wave = it->second;
        const bool hard_miss =
            scan.report.miss == EngramLevel::UnlockMiss::NoPlayer ||
            scan.report.miss == EngramLevel::UnlockMiss::EmptyList ||
            scan.report.miss == EngramLevel::UnlockMiss::LevelZero;
        if (hard_miss && first) {
            wave.pending.clear();
            wave.block_sent = false;
            wave.arm_next = false;
            return;
        }
        if (!hard_miss)
            RememberScan(wave, scan, first);
    }

    std::vector<UClass*> batch;
    {
        std::lock_guard<std::mutex> lock(g_wave_mu);
        const auto it = WaveAt(steam);
        if (it == g_waves.end() || it->second.generation != generation) return;
        Wave& wave = it->second;
        while (static_cast<int>(batch.size()) < EngramLevel::kQueueBlock &&
               !wave.pending.empty()) {
            UClass* cls = wave.pending.front();
            wave.pending.erase(wave.pending.begin());
            if (cls) batch.push_back(cls);
        }
    }

    const int sent = SendBatch(controller, batch);

    int finished = 0;
    int level = 0;
    bool tell = false;
    {
        std::lock_guard<std::mutex> lock(g_wave_mu);
        const auto it = WaveAt(steam);
        if (it == g_waves.end() || it->second.generation != generation) return;
        Wave& wave = it->second;
        wave.unlocked += sent;
        wave.block_sent = sent > 0 || wave.block_sent;
        if (!wave.pending.empty()) {
            wave.block_sent = true;
            wave.arm_next = true;
            return;
        }
        finished = wave.unlocked;
        level = wave.level;
        tell = finished > 0;
        wave.unlocked = 0;
        wave.block_sent = false;
        wave.timer_armed = false;
        wave.arm_next = false;
        wave.need_reread = false;
    }
    if (!tell || !controller) return;
    EngramLevel::UnlockReport report;
    report.unlocked = finished;
    report.character_level = level;
    EngramLevel::TellPlayer(controller, EngramLevel::FinishChat(report));
    Log::GetLog()->info(
        "EngramLevel: fila — {} engrama(s) não tek até o nível {}",
        finished, level);
}

// Corre depois do TimerUpdate, no mesmo segundo do ArkApi. Agenda o bloco
// seguinte fora do callback do DelayExecute.
void FollowUp() {
    std::vector<std::pair<uint64, int>> jobs;
    {
        std::lock_guard<std::mutex> lock(g_wave_mu);
        for (auto& entry : g_waves) {
            Wave& wave = entry.second;
            if (!wave.arm_next) continue;
            wave.arm_next = false;
            wave.timer_armed = true;
            jobs.emplace_back(entry.first, wave.generation);
        }
    }
    for (const auto& job : jobs)
        ScheduleTick(job.first, job.second);
}

} // namespace

namespace EngramLevel {

UnlockReport UnlockExactLevel(AShooterPlayerController* controller, int level,
                              int character_level) {
    (void)character_level;
    UnlockReport report;
    report.target_level = level;
    if (!controller) {
        report.miss = UnlockMiss::NoPlayer;
        return report;
    }
    if (level <= 0) {
        report.miss = UnlockMiss::LevelZero;
        return report;
    }

    GrantContext ctx;
    if (!OpenGrant(controller, ctx, report.miss)) return report;

    const Config& cfg = Config::Get();
    const bool any_locked_non_tek =
        cfg.UnlockTotal() && AnyLockedNonTek(ctx.player_state, ctx.entries, level);
    const GrantTier tier = ChooseGrantTier(
        cfg.UnlockNonTek(), cfg.UnlockTotal(), any_locked_non_tek);
    if (tier == GrantTier::None) {
        report.miss = UnlockMiss::NoneAtLevel;
        return report;
    }

    PointsGuard points(ctx.player_state);
    const GrantStats stats = GrantEntries(
        ctx.controller, ctx.player_state, ctx.entries, level, false, tier);
    report.unlocked = stats.unlocked;
    report.miss = MissFor(stats);
    return report;
}

UnlockReport UnlockSpentLevels(AShooterPlayerController* controller,
                               const std::vector<int>& levels) {
    UnlockReport report;
    if (!levels.empty()) report.target_level = levels.front();
    if (!controller) {
        report.miss = UnlockMiss::NoPlayer;
        return report;
    }
    if (levels.size() <= 1) {
        report.miss = UnlockMiss::NoneAtLevel;
        return report;
    }

    GrantContext ctx;
    if (!OpenGrant(controller, ctx, report.miss)) return report;

    const Config& cfg = Config::Get();
    const auto batches = GrantBatchesForSpentLevels(
        levels, cfg.UnlockNonTek(), cfg.UnlockTotal());
    PointsGuard points(ctx.player_state);
    GrantStats stats;
    for (const auto& batch : batches) {
        const GrantTier tier = batch.second ? GrantTier::Tek : GrantTier::NonTek;
        const GrantStats part = GrantEntries(
            ctx.controller, ctx.player_state, ctx.entries, batch.first, false, tier);
        stats.unlocked += part.unlocked;
        stats.known += part.known;
        stats.eligible += part.eligible;
    }
    report.unlocked = stats.unlocked;
    report.miss = MissFor(stats);
    return report;
}

UnlockReport UnlockOwnedNonTek(AShooterPlayerController* controller) {
    const GrantTier tier = GrantTier::NonTek;
    if (tier != GrantTier::NonTek) {
        UnlockReport blocked;
        blocked.miss = UnlockMiss::NoneAtLevel;
        return blocked;
    }
    return ScanOwnedNonTek(controller).report;
}

UnlockReport BeginOwnedQueue(AShooterPlayerController* controller) {
    Scan scan = ScanOwnedNonTek(controller);
    if (!controller) return scan.report;
    const uint64 steam = ArkApi::GetApiUtils().GetSteamIdFromController(controller);
    if (steam == 0) {
        scan.report.miss = UnlockMiss::NoPlayer;
        scan.report.unlocked = 0;
        return scan.report;
    }
    if (scan.report.unlocked <= 0) {
        CancelPlayerQueue(steam);
        return scan.report;
    }

    int generation = 0;
    {
        std::lock_guard<std::mutex> lock(g_wave_mu);
        Wave& wave = g_waves[steam];
        wave.generation += 1;
        generation = wave.generation;
        wave.pending = std::move(scan.classes);
        wave.unlocked = 0;
        wave.level = scan.report.character_level;
        wave.block_sent = false;
        wave.need_reread = false;
        wave.arm_next = false;
        wave.timer_armed = true;
    }
    ScheduleTick(steam, generation);
    return scan.report;
}

UnlockReport RefreshOwnedQueue(AShooterPlayerController* controller) {
    Scan scan = ScanOwnedNonTek(controller);
    if (scan.report.miss == UnlockMiss::NoPlayer ||
        scan.report.miss == UnlockMiss::EmptyList ||
        scan.report.miss == UnlockMiss::LevelZero) {
        scan.report.unlocked = 0;
        return scan.report;
    }
    if (!controller) {
        scan.report.miss = UnlockMiss::NoPlayer;
        scan.report.unlocked = 0;
        return scan.report;
    }
    const uint64 steam = ArkApi::GetApiUtils().GetSteamIdFromController(controller);
    if (steam == 0) {
        scan.report.miss = UnlockMiss::NoPlayer;
        scan.report.unlocked = 0;
        return scan.report;
    }

    int added = 0;
    int generation = 0;
    bool arm = false;
    {
        std::lock_guard<std::mutex> lock(g_wave_mu);
        Wave& wave = g_waves[steam];
        if (scan.report.character_level > 0)
            wave.level = scan.report.character_level;
        for (UClass* cls : scan.classes) {
            if (Listed(wave.pending, cls)) continue;
            wave.pending.push_back(cls);
            ++added;
        }
        if (wave.block_sent) {
            wave.need_reread = false;
        } else if (!wave.timer_armed && !wave.pending.empty()) {
            wave.generation += 1;
            generation = wave.generation;
            wave.timer_armed = true;
            wave.arm_next = false;
            wave.block_sent = false;
            arm = true;
        }
    }
    if (arm) ScheduleTick(steam, generation);
    scan.report.unlocked = added;
    if (added > 0) scan.report.miss = UnlockMiss::None;
    return scan.report;
}

void ScheduleOwnedReread(AShooterPlayerController* controller) {
    if (!controller) return;
    const uint64 steam = ArkApi::GetApiUtils().GetSteamIdFromController(controller);
    if (steam == 0) return;
    if (!Prefs::IsAutoEnabled(std::to_string(steam))) return;

    int generation = 0;
    {
        std::lock_guard<std::mutex> lock(g_wave_mu);
        Wave& wave = g_waves[steam];
        if (!LevelUpRestartsWait(wave.block_sent)) {
            wave.need_reread = true;
            return;
        }
        wave.generation += 1;
        generation = wave.generation;
        wave.timer_armed = true;
        wave.arm_next = false;
        wave.need_reread = false;
    }
    ScheduleTick(steam, generation);
}

void CancelPlayerQueue(uint64 steam) {
    if (steam == 0) return;
    std::lock_guard<std::mutex> lock(g_wave_mu);
    const auto it = WaveAt(steam);
    if (it == g_waves.end()) return;
    Wave& wave = it->second;
    wave.generation += 1;
    wave.pending.clear();
    wave.block_sent = false;
    wave.timer_armed = false;
    wave.arm_next = false;
    wave.need_reread = false;
    wave.unlocked = 0;
}

void StartUnlockQueue() {
    if (g_queue_timer) return;
    // TimerUpdate entra na lista antes deste callback. O FollowUp corre
    // no mesmo segundo, depois do bloco, e só então marca o próximo.
    API::Timer::Get();
    ArkApi::GetCommands().AddOnTimerCallback("EngramLevel.Queue", &FollowUp);
    g_queue_timer = true;
}

void StopUnlockQueue() {
    if (g_queue_timer) {
        ArkApi::GetCommands().RemoveOnTimerCallback("EngramLevel.Queue");
        g_queue_timer = false;
    }
    std::lock_guard<std::mutex> lock(g_wave_mu);
    for (auto& entry : g_waves) {
        Wave& wave = entry.second;
        wave.generation += 1;
        wave.pending.clear();
        wave.block_sent = false;
        wave.timer_armed = false;
        wave.arm_next = false;
        wave.need_reread = false;
        wave.unlocked = 0;
    }
}

} // namespace EngramLevel
