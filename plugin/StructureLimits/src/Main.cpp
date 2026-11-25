#include <API/ARK/Ark.h>

#include "StructureLimitsConfig.h"
#include "DurableOutbox.h"
#include "LocalSnapshotStore.h"

#include <memory>
#include <string>
#include <immintrin.h>

#pragma comment(lib, "ArkApi.lib")

namespace {

bool g_probeHookInstalled = false;
bool g_beginPlayHookInstalled = false;
bool g_destroyedHookInstalled = false;
bool g_demolishHookInstalled = false;
bool g_pickupHookInstalled = false;
bool g_multiUseHookInstalled = false;
UClass* g_supplyCrateBaseClass = nullptr;
std::unique_ptr<StructureLimits::LimitEngine> g_limitEngine;
std::unique_ptr<StructureLimits::LocalSnapshotStore> g_snapshotStore;
std::unique_ptr<StructureLimits::DurableOutbox> g_outbox;

std::string GetConfigPath() {
    return ArkApi::Tools::GetCurrentDir() +
        "/ArkApi/Plugins/StructureLimits/config.json";
}

} // namespace

DECLARE_HOOK(APrimalStructure_IsAllowedToBuild, int, APrimalStructure*,
    APlayerController*, FVector, FRotator, FPlacementData*, bool, FRotator, bool);
DECLARE_HOOK(APrimalStructure_BeginPlay, void, APrimalStructure*);
DECLARE_HOOK(APrimalStructure_Destroyed, void, APrimalStructure*);
DECLARE_HOOK(APrimalStructure_Demolish, void, APrimalStructure*,
    APlayerController*, AActor*);
DECLARE_HOOK(APrimalStructure_BPOnStructurePickup, void, APrimalStructure*,
    APlayerController*, TSubclassOf<UPrimalItem>, UPrimalItem*, bool);
DECLARE_HOOK(APrimalStructure_TryMultiUse, bool, APrimalStructure*,
    APlayerController*, int);

namespace {

bool LogStructureLifecycle(const char* eventName, APrimalStructure* structure) {
    if (structure == nullptr || structure->ClassField() == nullptr) return false;
    // Supply crates derive from a dedicated base class. Their StructureID and
    // owner/team fields may be populated, so those values alone are not proof
    // that a player built the actor. Exclude the base class and its subclasses.
    if (g_supplyCrateBaseClass != nullptr && structure->IsA(g_supplyCrateBaseClass))
        return false;

    std::string blueprint = "<unknown>";
    if (auto* defaultObject = structure->ClassField()->GetDefaultObject(true)) {
        FString fullName;
        defaultObject->GetFullName(&fullName, nullptr);
        blueprint = fullName.ToString();
    }

    const int targetingTeam = structure->TargetingTeamField();
    const int owningPlayerId = structure->OwningPlayerIDField();
    const std::string ownerName = structure->OwnerNameField().ToString();
    const std::string owningPlayerName = structure->OwningPlayerNameField().ToString();

    // Map actors and supply crates also reach APrimalStructure lifecycle hooks.
    // Only emit lifecycle candidates carrying player/tribe ownership metadata.
    if (targetingTeam == 0 && owningPlayerId == 0 && ownerName.empty() && owningPlayerName.empty())
        return false;

    float xyz[4]{};
    if (auto* root = structure->RootComponentField())
        _mm_storeu_ps(xyz, root->ComponentToWorldField().Translation);

    Log::GetLog()->info(
        "StructureLimits probe: lifecycle={} structure_id={} blueprint={} targeting_team={} owning_player_id={} owner_name={} owning_player_name={} world_xyz={:.1f},{:.1f},{:.1f}",
        eventName, structure->StructureIDField(), blueprint, targetingTeam,
        owningPlayerId, ownerName, owningPlayerName, xyz[0], xyz[1], xyz[2]);
    return true;
}

} // namespace

void __fastcall Hook_APrimalStructure_BeginPlay(APrimalStructure* structure) {
    APrimalStructure_BeginPlay_original(structure);
    // BeginPlay also fires for structures loaded from a save. This is evidence
    // of actor lifecycle only; it must never be counted as a new placement.
    LogStructureLifecycle("begin_play", structure);
}

void __fastcall Hook_APrimalStructure_Destroyed(APrimalStructure* structure) {
    // Capture identity before the original teardown can invalidate actor data.
    LogStructureLifecycle("destroyed_callback", structure);
    APrimalStructure_Destroyed_original(structure);
}

void __fastcall Hook_APrimalStructure_Demolish(
    APrimalStructure* structure, APlayerController* playerController,
    AActor* damageCauser) {
    // Demolish is an action-specific path. Pair this intent with Destroyed
    // using StructureID; Destroyed alone cannot tell demolish from pickup,
    // decay, streaming, or other teardown.
    if (LogStructureLifecycle("demolish_called", structure)) {
        unsigned __int64 steamId = 0;
        if (playerController != nullptr &&
            playerController->IsA(AShooterPlayerController::GetPrivateStaticClass()))
            steamId = static_cast<AShooterPlayerController*>(
                playerController)->GetUniqueNetIdAsUINT64();
        Log::GetLog()->info(
            "StructureLimits probe: removal_action=demolish_called structure_id={} steam_id={} damage_causer_present={}",
            structure->StructureIDField(), steamId, damageCauser != nullptr);
    }
    APrimalStructure_Demolish_original(structure, playerController, damageCauser);
}

void __fastcall Hook_APrimalStructure_BPOnStructurePickup(
    APrimalStructure* structure, APlayerController* playerController,
    TSubclassOf<UPrimalItem> itemType, UPrimalItem* newlyPickedUpItem,
    bool isQuickPickup) {
    // This callback is a stronger pickup candidate than generic Destroyed.
    // A non-null item is evidence of an item result, but this remains
    // observational until verified against vanilla and mod pickup flows.
    if (LogStructureLifecycle("pickup_callback", structure)) {
        unsigned __int64 steamId = 0;
        if (playerController != nullptr &&
            playerController->IsA(AShooterPlayerController::GetPrivateStaticClass()))
            steamId = static_cast<AShooterPlayerController*>(
                playerController)->GetUniqueNetIdAsUINT64();
        Log::GetLog()->info(
            "StructureLimits probe: removal_action=pickup_callback structure_id={} steam_id={} item_created={} quick_pickup={}",
            structure->StructureIDField(), steamId,
            newlyPickedUpItem != nullptr, isQuickPickup);
    }
    APrimalStructure_BPOnStructurePickup_original(
        structure, playerController, itemType, newlyPickedUpItem, isQuickPickup);
}

bool __fastcall Hook_APrimalStructure_TryMultiUse(
    APrimalStructure* structure, APlayerController* playerController,
    int useIndex) {
    // Pickup may be routed through the structure's server-side multi-use path
    // without invoking BPOnStructurePickup (as observed for an S+ foundation).
    // Capture identity before calling the game because this action may destroy
    // the actor; correlate the return with Destroyed using the saved ID.
    const bool hasStructure = LogStructureLifecycle("multi_use_called", structure);
    const unsigned int structureId = hasStructure
        ? structure->StructureIDField() : 0;
    unsigned __int64 steamId = 0;
    if (playerController != nullptr &&
        playerController->IsA(AShooterPlayerController::GetPrivateStaticClass()))
        steamId = static_cast<AShooterPlayerController*>(
            playerController)->GetUniqueNetIdAsUINT64();

    const bool handled = APrimalStructure_TryMultiUse_original(
        structure, playerController, useIndex);
    if (hasStructure) {
        Log::GetLog()->info(
            "StructureLimits probe: interaction_action=try_multi_use structure_id={} steam_id={} use_index={} handled={}",
            structureId, steamId, useIndex, handled);
    }
    return handled;
}

int __fastcall Hook_APrimalStructure_IsAllowedToBuild(
    APrimalStructure* structure, APlayerController* controller,
    FVector atLocation, FRotator atRotation, FPlacementData* placementData,
    bool dontAdjustForMaxRange, FRotator playerViewRotation, bool finalPlacement) {
    const int originalResult = APrimalStructure_IsAllowedToBuild_original(
        structure, controller, atLocation, atRotation, placementData,
        dontAdjustForMaxRange, playerViewRotation, finalPlacement);

    // Diagnostic only: observe final checks after the game's decision. Never
    // veto, reserve capacity, consume items, or claim that placement succeeded.
    if (finalPlacement && structure != nullptr) {
        std::string blueprint = "<unknown>";
        if (structure->ClassField() != nullptr) {
            if (auto* defaultObject = structure->ClassField()->GetDefaultObject(true)) {
                FString fullName;
                defaultObject->GetFullName(&fullName, nullptr);
                blueprint = fullName.ToString();
            }
        }
        const auto blueprintKey =
            StructureLimits::NormalizeBlueprintKey(blueprint);
        unsigned __int64 steamId = 0;
        if (controller != nullptr && controller->IsA(AShooterPlayerController::GetPrivateStaticClass()))
            steamId = static_cast<AShooterPlayerController*>(controller)->GetUniqueNetIdAsUINT64();

        Log::GetLog()->info(
            "StructureLimits probe: final-check result={} structure_id={} steam_id={} targeting_team={} blueprint={} blueprint_key={} requested_xyz={:.1f},{:.1f},{:.1f}",
            originalResult, structure->StructureIDField(), steamId,
            structure->TargetingTeamField(), blueprint, blueprintKey,
            atLocation.X, atLocation.Y, atLocation.Z);
    }
    return originalResult;
}

namespace {
void DisableInstalledHooks() {
    if (g_probeHookInstalled) {
        ArkApi::GetHooks().DisableHook(
            "APrimalStructure.IsAllowedToBuild",
            Hook_APrimalStructure_IsAllowedToBuild);
        g_probeHookInstalled = false;
    }
    if (g_beginPlayHookInstalled) {
        ArkApi::GetHooks().DisableHook(
            "APrimalStructure.BeginPlay", Hook_APrimalStructure_BeginPlay);
        g_beginPlayHookInstalled = false;
    }
    if (g_destroyedHookInstalled) {
        ArkApi::GetHooks().DisableHook(
            "APrimalStructure.Destroyed", Hook_APrimalStructure_Destroyed);
        g_destroyedHookInstalled = false;
    }
    if (g_demolishHookInstalled) {
        ArkApi::GetHooks().DisableHook(
            "APrimalStructure.Demolish", Hook_APrimalStructure_Demolish);
        g_demolishHookInstalled = false;
    }
    if (g_pickupHookInstalled) {
        ArkApi::GetHooks().DisableHook(
            "APrimalStructure.BPOnStructurePickup",
            Hook_APrimalStructure_BPOnStructurePickup);
        g_pickupHookInstalled = false;
    }
    if (g_multiUseHookInstalled) {
        ArkApi::GetHooks().DisableHook(
            "APrimalStructure.TryMultiUse",
            Hook_APrimalStructure_TryMultiUse);
        g_multiUseHookInstalled = false;
    }
}
} // namespace

extern "C" __declspec(dllexport) void Plugin_Init() {
    Log::Get().Init("StructureLimits");
    Log::GetLog()->info("StructureLimits: initializing runtime (enforcement remains fail-open)");
    try {
        const auto path = GetConfigPath();
        const auto config = StructureLimits::LoadPluginConfiguration(path);
        if (!config.enabled) {
            Log::GetLog()->info("StructureLimits: disabled by configuration");
            return;
        }

        const auto identity = config.Identity();
        g_supplyCrateBaseClass =
            APrimalStructureItemContainer_SupplyCrate::GetPrivateStaticClass(nullptr);
        g_limitEngine = std::make_unique<StructureLimits::LimitEngine>(
            config.limits, identity);
        g_snapshotStore = std::make_unique<StructureLimits::LocalSnapshotStore>(
            config.localSnapshotFile, identity);
        g_outbox = std::make_unique<StructureLimits::DurableOutbox>(
            config.localOutboxDirectory);
        g_outbox->Initialize();

        const auto snapshot = g_snapshotStore->LoadCandidate();
        if (snapshot.usable) {
            Log::GetLog()->info(
                "StructureLimits: found recovery candidate with {} structures; "
                "candidate is not trusted for enforcement and requires a fresh live scan",
                snapshot.candidate.structures.size());
        } else if (!snapshot.error.empty()) {
            Log::GetLog()->warn("StructureLimits: snapshot unavailable: {}", snapshot.error);
        } else {
            Log::GetLog()->info("StructureLimits: no prior complete snapshot; enforcement stays suspended");
        }

        std::string outboxError;
        const auto pendingEvents = g_outbox->Pending(&outboxError);
        Log::GetLog()->info(
            "StructureLimits: instance={} path={} LPG={} LPE={} specific_blueprints={} pending_events={}",
            identity.displayId, identity.canonicalInstancePath,
            config.limits.globalPrimary, config.limits.GlobalExtra(),
            config.limits.specificPrimary.size(), pendingEvents.size());
        if (!outboxError.empty())
            Log::GetLog()->warn("StructureLimits: outbox needs attention: {}", outboxError);

        const bool observePlacement = config.observationProbeEnabled;
        const bool observeLifecycle = config.lifecycleObservationEnabled;
        const bool observeBeginPlay = observeLifecycle &&
            config.lifecycleBeginPlayObservationEnabled;
        if (!observePlacement && !observeLifecycle) {
            Log::GetLog()->warn("StructureLimits: observers are disabled; no game hooks installed");
            Log::GetLog()->warn("StructureLimits: enforcement suspended; complete live inventory and validated placement hook are unavailable");
            return;
        }

        if (observePlacement) {
            ArkApi::GetHooks().SetHook(
                "APrimalStructure.IsAllowedToBuild",
                Hook_APrimalStructure_IsAllowedToBuild,
                &APrimalStructure_IsAllowedToBuild_original);
            g_probeHookInstalled = true;
        }
        if (observeBeginPlay) {
            ArkApi::GetHooks().SetHook(
                "APrimalStructure.BeginPlay",
                Hook_APrimalStructure_BeginPlay,
                &APrimalStructure_BeginPlay_original);
            g_beginPlayHookInstalled = true;
        }
        if (observeLifecycle) {
            ArkApi::GetHooks().SetHook(
                "APrimalStructure.Destroyed",
                Hook_APrimalStructure_Destroyed,
                &APrimalStructure_Destroyed_original);
            g_destroyedHookInstalled = true;
            ArkApi::GetHooks().SetHook(
                "APrimalStructure.Demolish",
                Hook_APrimalStructure_Demolish,
                &APrimalStructure_Demolish_original);
            g_demolishHookInstalled = true;
            ArkApi::GetHooks().SetHook(
                "APrimalStructure.BPOnStructurePickup",
                Hook_APrimalStructure_BPOnStructurePickup,
                &APrimalStructure_BPOnStructurePickup_original);
            g_pickupHookInstalled = true;
            ArkApi::GetHooks().SetHook(
                "APrimalStructure.TryMultiUse",
                Hook_APrimalStructure_TryMultiUse,
                &APrimalStructure_TryMultiUse_original);
            g_multiUseHookInstalled = true;
        }
        Log::GetLog()->warn(
            "StructureLimits: observer hooks only; enforcement suspended; removal action hooks (Demolish/BPOnStructurePickup/TryMultiUse) are diagnostic candidates and require validation before counting");
    } catch (const std::exception& e) {
        DisableInstalledHooks();
        g_limitEngine.reset();
        g_snapshotStore.reset();
        g_outbox.reset();
        g_supplyCrateBaseClass = nullptr;
        Log::GetLog()->critical("StructureLimits: init error: {}", e.what());
    }
}

extern "C" __declspec(dllexport) void Plugin_Unload() {
    DisableInstalledHooks();
    g_limitEngine.reset();
    g_snapshotStore.reset();
    g_outbox.reset();
    g_supplyCrateBaseClass = nullptr;
    Log::GetLog()->info("StructureLimits: unloaded");
}
