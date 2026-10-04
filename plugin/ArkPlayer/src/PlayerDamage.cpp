#include "pch.h"
#include "PlayerDamage.h"
#include "DamageFormat.h"

#include <Timer.h>

#include <cmath>
#include <chrono>
#include <cstring>
#include <vector>

namespace ArkPlayer {
namespace Damage {
namespace {

constexpr auto kWindow = std::chrono::milliseconds(1000);

enum class Relation { Dealt, Received, AllyDealt, AllyReceived };

struct Bucket {
    uint64_t viewer = 0;
    AShooterPlayerController* pc = nullptr;
    uintptr_t victim = 0;
    Relation relation = Relation::Dealt;
    double sum = 0.0;
    FVector location{0.f, 0.f, 0.f};
    std::chrono::steady_clock::time_point start{};
};

std::vector<Bucket> g_buckets;
bool g_installed = false;
bool g_timer_on = false;
bool g_saved_flag = false;
bool g_prev_flag = false;
bool g_logged_arm = false;

struct HookSlot {
    const char* name = nullptr;
    LPVOID detour = nullptr;
};

std::vector<HookSlot> g_hooks;

// Você causa verde, você recebe vermelho, aliado causa azul claro,
// aliado recebe amarelo alaranjado. FColor é o que o texto flutuante usa.
FColor ColorFor(Relation relation) {
    switch (relation) {
    case Relation::Dealt:
        return FColor(51, 217, 64);
    case Relation::Received:
        return FColor(230, 38, 38);
    case Relation::AllyDealt:
        return FColor(115, 191, 255);
    case Relation::AllyReceived:
        return FColor(255, 158, 31);
    }
    return FColor(51, 217, 64);
}

FVector WorldLoc(AActor* actor) {
    if (!actor) return FVector{0.f, 0.f, 0.f};
    USceneComponent* root = actor->RootComponentField();
    if (!root) return FVector{0.f, 0.f, 0.f};
    float world_xyz[4] = {};
    std::memcpy(world_xyz, &root->ComponentToWorldField().Translation, sizeof(float) * 3);
    const FVector world{world_xyz[0], world_xyz[1], world_xyz[2]};
    const float mag = world.X * world.X + world.Y * world.Y + world.Z * world.Z;
    if (mag > 1.f) return world;
    return root->RelativeLocationField();
}

uint64_t SteamOf(AShooterPlayerController* pc) {
    if (!pc) return 0;
    return ArkApi::GetApiUtils().GetSteamIdFromController(pc);
}

AShooterPlayerController* AsPlayer(AController* controller) {
    if (!controller) return nullptr;
    if (!controller->IsA(AShooterPlayerController::GetPrivateStaticClass())) return nullptr;
    return static_cast<AShooterPlayerController*>(controller);
}

AShooterPlayerController* ControllerOf(AShooterCharacter* character) {
    if (!character) return nullptr;
    if (AShooterPlayerController* pc = AsPlayer(character->ControllerField())) return pc;
    return character->LastValidPlayerControllerField().Get();
}

AShooterPlayerController* PlayerFromPawn(APawn* pawn) {
    if (!pawn) return nullptr;
    if (AShooterPlayerController* pc = AsPlayer(pawn->ControllerField())) return pc;
    if (pawn->IsA(APrimalDinoCharacter::GetPrivateStaticClass())) {
        auto* dino = static_cast<APrimalDinoCharacter*>(pawn);
        if (AShooterCharacter* rider = dino->RiderField().Get())
            return ControllerOf(rider);
    }
    if (pawn->IsA(AShooterCharacter::GetPrivateStaticClass()))
        return ControllerOf(static_cast<AShooterCharacter*>(pawn));
    return nullptr;
}

AShooterPlayerController* FindDealer(AController* instigator, AActor* causer) {
    if (AShooterPlayerController* pc = AsPlayer(instigator)) return pc;
    if (instigator) {
        if (AShooterPlayerController* pc = PlayerFromPawn(instigator->PawnField()))
            return pc;
    }
    if (!causer) return nullptr;
    if (causer->IsA(APrimalDinoCharacter::GetPrivateStaticClass())
        || causer->IsA(AShooterCharacter::GetPrivateStaticClass())) {
        if (AShooterPlayerController* pc = PlayerFromPawn(static_cast<APawn*>(causer)))
            return pc;
    }
    if (APawn* instigated = causer->InstigatorField())
        return PlayerFromPawn(instigated);
    return nullptr;
}

AShooterPlayerController* FindVictimPlayer(APrimalCharacter* victim) {
    if (!victim || !victim->IsA(AShooterCharacter::GetPrivateStaticClass())) return nullptr;
    return ControllerOf(static_cast<AShooterCharacter*>(victim));
}

bool SameOrAllied(AShooterPlayerController* viewer, int other_team) {
    if (!viewer || other_team <= 0) return false;
    const int my_team = viewer->TargetingTeamField();
    if (my_team <= 0) return false;
    if (my_team == other_team) return true;

    if (AShooterCharacter* character = viewer->GetPlayerCharacter()) {
        if (character->IsAlliedWithOtherTeam(other_team)) return true;
    }
    APlayerState* state = viewer->PlayerStateField();
    if (!state) return false;
    static UClass* shooter_state = nullptr;
    if (!shooter_state)
        shooter_state = AShooterPlayerState::GetPrivateStaticClass(nullptr);
    if (!shooter_state || !state->IsA(shooter_state)) return false;
    return static_cast<AShooterPlayerState*>(state)->IsAlliedWith(other_team);
}

bool IsOnline(AShooterPlayerController* pc) {
    if (!pc) return false;
    UWorld* world = ArkApi::GetApiUtils().GetWorld();
    if (!world) return false;
    const auto& controllers = world->PlayerControllerListField();
    for (TWeakObjectPtr<APlayerController> weak : controllers) {
        if (weak.Get() == pc) return true;
    }
    return false;
}

void Emit(const Bucket& bucket) {
    const long long total = static_cast<long long>(std::llround(bucket.sum));
    if (total <= 0) return;
    const std::string text = FormatDamageAmount(total);
    if (text.empty() || text == "0") return;

    AShooterPlayerController* pc = IsOnline(bucket.pc) ? bucket.pc : nullptr;
    if (!pc) pc = ArkApi::GetApiUtils().FindPlayerFromSteamId(bucket.viewer);
    if (!pc) return;

    // O inteiro nativo vira "9,000" no cliente. Aqui a string já é "9k" e
    // entra na mesma lista do dano flutuante, com o widget ligado.
    ArkPlayer::Damage::ArmFloatingWidget();
    const std::wstring wide(text.begin(), text.end());
    FString line(wide.c_str());
    FVector at = bucket.location;
    at.Z += 60.f;
    pc->ClientAddFloatingText(
        FVector_NetQuantize(at),
        &line,
        ColorFor(bucket.relation),
        1.f,
        1.f,
        1.25f,
        FVector{0.f, 0.f, 140.f},
        0.6f,
        0.15f,
        0.4f);
}

void FlushExpired() {
    const auto now = std::chrono::steady_clock::now();
    std::vector<Bucket> due;
    std::vector<Bucket> keep;
    due.reserve(g_buckets.size());
    keep.reserve(g_buckets.size());
    for (auto& bucket : g_buckets) {
        if (now - bucket.start >= kWindow) due.push_back(bucket);
        else keep.push_back(std::move(bucket));
    }
    g_buckets.swap(keep);
    for (const Bucket& bucket : due) Emit(bucket);
}

void AddHit(AShooterPlayerController* pc, uint64_t viewer, uintptr_t victim,
            Relation relation, double amount, const FVector& location) {
    const auto now = std::chrono::steady_clock::now();
    for (Bucket& bucket : g_buckets) {
        if (bucket.viewer != viewer || bucket.victim != victim || bucket.relation != relation)
            continue;
        bucket.pc = pc;
        bucket.location = location;
        if (now - bucket.start >= kWindow) {
            Emit(bucket);
            bucket.sum = amount;
            bucket.start = now;
        } else {
            bucket.sum += amount;
        }
        return;
    }
    Bucket created;
    created.viewer = viewer;
    created.pc = pc;
    created.victim = victim;
    created.relation = relation;
    created.sum = amount;
    created.location = location;
    created.start = now;
    g_buckets.push_back(std::move(created));
}

int AttackerTeam(AShooterPlayerController* dealer, AController* instigator, AActor* causer) {
    if (dealer) {
        const int team = dealer->TargetingTeamField();
        if (team > 0) return team;
    }
    if (causer && causer->TargetingTeamField() > 0) return causer->TargetingTeamField();
    if (instigator && instigator->TargetingTeamField() > 0) return instigator->TargetingTeamField();
    return 0;
}

void OnFlushTimer() {
    if (!g_timer_on) return;
    FlushExpired();
    if (g_timer_on) API::Timer::Get().DelayExecute(OnFlushTimer, 1);
}

template <typename T>
void TryHook(const char* name, LPVOID detour, T** original) {
    if (ArkApi::GetHooks().SetHook(name, detour, original)) {
        g_hooks.push_back(HookSlot{name, detour});
        return;
    }
    Log::GetLog()->error("ArkPlayer: hook nao encaixou: {}", name);
}

}  // namespace

void ArmFloatingWidget() {
    AShooterGameMode* mode = ArkApi::GetApiUtils().GetShooterGameMode();
    if (!mode) return;
    bool& flag = mode->bShowFloatingDamageTextField();
    if (!g_saved_flag) {
        g_prev_flag = flag;
        g_saved_flag = true;
    }
    if (flag) return;
    flag = true;
    if (!g_logged_arm) {
        g_logged_arm = true;
        Log::GetLog()->info(
            "ArkPlayer: bShowFloatingDamageText ligado — o widget desenha só o número curto");
    }
}

void NoteApplied(APrimalCharacter* victim, float applied, AController* instigator, AActor* causer) {
    if (!victim || !(applied > 0.f)) return;
    UWorld* world = ArkApi::GetApiUtils().GetWorld();
    if (!world) return;

    AShooterPlayerController* dealer = FindDealer(instigator, causer);
    AShooterPlayerController* victim_player = FindVictimPlayer(victim);
    const uint64_t dealer_id = SteamOf(dealer);
    const uint64_t victim_id = SteamOf(victim_player);
    const int attacker_team = AttackerTeam(dealer, instigator, causer);
    const int victim_team = victim->TargetingTeamField();
    const uintptr_t victim_key = reinterpret_cast<uintptr_t>(victim);
    const double amount = static_cast<double>(applied);
    const FVector location = WorldLoc(victim);

    const auto& controllers = world->PlayerControllerListField();
    for (TWeakObjectPtr<APlayerController> weak : controllers) {
        auto* pc = AsPlayer(weak.Get());
        if (!pc) continue;
        const uint64_t viewer = SteamOf(pc);
        if (!viewer) continue;

        Relation relation;
        if (dealer_id && viewer == dealer_id) relation = Relation::Dealt;
        else if (victim_id && viewer == victim_id) relation = Relation::Received;
        else if (SameOrAllied(pc, attacker_team)) relation = Relation::AllyDealt;
        else if (SameOrAllied(pc, victim_team)) relation = Relation::AllyReceived;
        else continue;

        AddHit(pc, viewer, victim_key, relation, amount, location);
    }
}

}  // namespace Damage
}  // namespace ArkPlayer

namespace {

int g_damage_depth = 0;

void ObserveDamage(APrimalCharacter* victim, float applied, AController* instigator, AActor* causer, bool outer) {
    if (outer && victim && applied > 0.f)
        ArkPlayer::Damage::NoteApplied(victim, applied, instigator, causer);
}

}  // namespace

// O retorno é o dano que o jogo já aplicou. Este hook não altera esse valor.
DECLARE_HOOK(APrimalCharacter_TakeDamage, float, APrimalCharacter*, float, FDamageEvent*, AController*, AActor*);
float Hook_APrimalCharacter_TakeDamage(APrimalCharacter* victim,
                                      float damage,
                                      FDamageEvent* event,
                                      AController* instigator,
                                      AActor* causer) {
    const bool outer = (g_damage_depth++ == 0);
    if (outer) ArkPlayer::Damage::ArmFloatingWidget();
    const float applied = APrimalCharacter_TakeDamage_original(victim, damage, event, instigator, causer);
    --g_damage_depth;
    ObserveDamage(victim, applied, instigator, causer, outer);
    return applied;
}

DECLARE_HOOK(APrimalDinoCharacter_TakeDamage, float, APrimalDinoCharacter*, float, FDamageEvent*, AController*, AActor*);
float Hook_APrimalDinoCharacter_TakeDamage(APrimalDinoCharacter* victim,
                                          float damage,
                                          FDamageEvent* event,
                                          AController* instigator,
                                          AActor* causer) {
    const bool outer = (g_damage_depth++ == 0);
    if (outer) ArkPlayer::Damage::ArmFloatingWidget();
    const float applied = APrimalDinoCharacter_TakeDamage_original(victim, damage, event, instigator, causer);
    --g_damage_depth;
    ObserveDamage(victim, applied, instigator, causer, outer);
    return applied;
}

DECLARE_HOOK(AShooterGameMode_Tick, void, AShooterGameMode*, float);
void Hook_AShooterGameMode_Tick(AShooterGameMode* mode, float delta) {
    AShooterGameMode_Tick_original(mode, delta);
    ArkPlayer::Damage::FlushExpired();
}

// O cliente formata o inteiro como "9,000" / "27,000". Não encaminhar
// esse RPC: a string curta sai uma vez, pela mesma lista, depois da janela.
DECLARE_HOOK(AShooterGameState_AddFloatingDamageText, void, AShooterGameState*, FVector, int, int);
void Hook_AShooterGameState_AddFloatingDamageText(AShooterGameState*, FVector, int, int) {}

DECLARE_HOOK(AShooterGameState_NetAddFloatingDamageText, void, AShooterGameState*, FVector, int, int, int);
void Hook_AShooterGameState_NetAddFloatingDamageText(AShooterGameState*, FVector, int, int, int) {}

DECLARE_HOOK(AShooterPlayerController_ClientAddFloatingDamageText, void, AShooterPlayerController*, FVector_NetQuantize, int, int);
void Hook_AShooterPlayerController_ClientAddFloatingDamageText(AShooterPlayerController*, FVector_NetQuantize, int, int) {}

namespace ArkPlayer {
namespace Damage {

void Install() {
    if (g_installed) return;
    g_installed = true;

    TryHook("APrimalCharacter.TakeDamage(float,FDamageEvent*,AController*,AActor*)",
            Hook_APrimalCharacter_TakeDamage,
            &APrimalCharacter_TakeDamage_original);
    TryHook("APrimalDinoCharacter.TakeDamage(float,FDamageEvent*,AController*,AActor*)",
            Hook_APrimalDinoCharacter_TakeDamage,
            &APrimalDinoCharacter_TakeDamage_original);
    TryHook("AShooterGameMode.Tick(float)",
            Hook_AShooterGameMode_Tick,
            &AShooterGameMode_Tick_original);
    TryHook("AShooterGameState.AddFloatingDamageText(FVector,int,int)",
            Hook_AShooterGameState_AddFloatingDamageText,
            &AShooterGameState_AddFloatingDamageText_original);
    TryHook("AShooterGameState.NetAddFloatingDamageText(FVector,int,int,int)",
            Hook_AShooterGameState_NetAddFloatingDamageText,
            &AShooterGameState_NetAddFloatingDamageText_original);
    TryHook("AShooterPlayerController.ClientAddFloatingDamageText(FVector_NetQuantize,int,int)",
            Hook_AShooterPlayerController_ClientAddFloatingDamageText,
            &AShooterPlayerController_ClientAddFloatingDamageText_original);

    g_timer_on = true;
    API::Timer::Get().DelayExecute(OnFlushTimer, 1);
    ArmFloatingWidget();
    Log::GetLog()->info(
        "ArkPlayer: dano flutuante nativo substituido por 9k/27k ({} hooks, janela 1s, widget ligado)",
        g_hooks.size());
}

void Remove() {
    if (!g_installed) return;
    g_installed = false;
    g_timer_on = false;
    g_buckets.clear();

    for (const HookSlot& hook : g_hooks)
        ArkApi::GetHooks().DisableHook(hook.name, hook.detour);
    g_hooks.clear();

    if (g_saved_flag) {
        if (AShooterGameMode* mode = ArkApi::GetApiUtils().GetShooterGameMode())
            mode->bShowFloatingDamageTextField() = g_prev_flag;
        g_saved_flag = false;
    }
    Log::GetLog()->info("ArkPlayer: dano na tela removido");
}

}  // namespace Damage
}  // namespace ArkPlayer
