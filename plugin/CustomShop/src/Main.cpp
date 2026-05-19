#include "pch.h"
#include "Commands.h"
#include "ShopConfig.h"
#include "ShopData.h"
#include "ShopPoints.h"
#include "ShopVip.h"
#include "ShopPerms.h"
#include "TimedPoints.h"

// ─────────────────────────────────────────────────────────────────
//  Plugin entry points required by ArkApi v3 (ASE).
// ─────────────────────────────────────────────────────────────────

// ── Hooks ─────────────────────────────────────────────────────────

DECLARE_HOOK(AShooterGameMode_BeginPlay, void, AShooterGameMode*);
void Hook_AShooterGameMode_BeginPlay(AShooterGameMode* _this) {
    AShooterGameMode_BeginPlay_original(_this);

    // Server is ready — apply shop buff to any already-connected players.
    const auto& pcs =
        ArkApi::GetApiUtils().GetWorld()->PlayerControllerListField();
    for (TWeakObjectPtr<APlayerController> wpc : pcs) {
        auto* sc = static_cast<AShooterPlayerController*>(wpc.Get());
        CustomShop::Data::InitPlayer(sc);
    }
}

DECLARE_HOOK(AShooterGameMode_HandleNewPlayer, bool,
             AShooterGameMode*,
             AShooterPlayerController*,
             UPrimalPlayerData*,
             AShooterCharacter*,
             bool);
bool Hook_AShooterGameMode_HandleNewPlayer(AShooterGameMode* _this,
                                           AShooterPlayerController* player,
                                           UPrimalPlayerData* data,
                                           AShooterCharacter* character,
                                           bool from_login) {
    const bool result = AShooterGameMode_HandleNewPlayer_original(
        _this, player, data, character, from_login);

    // Initialise UI data for the joining player.
    // If the character isn't fully spawned yet, InitPlayer fails gracefully;
    // the mod will pull its data when the player presses the hotkey.
    CustomShop::Data::InitPlayer(player);

    return result;
}

// ── Plugin lifecycle ───────────────────────────────────────────────

extern "C" __declspec(dllexport) void Plugin_Init() {
    Log::Get().Init("CustomShop");
    Log::GetLog()->info("CustomShop: initialising…");

    // Load config + open database — bail out on failure so the server
    // doesn't crash silently with a half-initialised plugin.
    try {
        CustomShop::ShopConfig::Get().Load();
        if (!CustomShop::ShopPoints::Get().Open()) {
            Log::GetLog()->critical(
                "CustomShop: database failed to open — plugin aborted");
            return;
        }
        // Give ShopVip the same connection.
        CustomShop::ShopVip::Get().SetDb(
            CustomShop::ShopPoints::Get().GetDb());
        CustomShop::ShopVip::Get().PruneExpired();
    }
    catch (const std::exception& e) {
        Log::GetLog()->critical("CustomShop: init error — {}", e.what());
        return;
    }

    // Register hooks
    ArkApi::GetHooks().SetHook(
        "AShooterGameMode.BeginPlay()",
        Hook_AShooterGameMode_BeginPlay,
        &AShooterGameMode_BeginPlay_original);

    ArkApi::GetHooks().SetHook(
        "AShooterGameMode.HandleNewPlayer_Implementation("
        "AShooterPlayerController*,UPrimalPlayerData*,AShooterCharacter*,bool)",
        Hook_AShooterGameMode_HandleNewPlayer,
        &AShooterGameMode_HandleNewPlayer_original);

    // Register console commands (mod-facing + admin)
    CustomShop::Commands::Register();

    // Bind Permissions plugin (optional — graceful if absent).
    CustomShop::Perms::Init();

    // Start timed-points reward timer.
    CustomShop::TimedPoints::Start();

    // If the server was already running (hot-reload scenario), initialise now.
    if (ArkApi::GetApiUtils().GetStatus() == ArkApi::ServerStatus::Ready) {
        const auto& pcs =
            ArkApi::GetApiUtils().GetWorld()->PlayerControllerListField();
        for (TWeakObjectPtr<APlayerController> wpc : pcs) {
            auto* sc = static_cast<AShooterPlayerController*>(wpc.Get());
            CustomShop::Data::InitPlayer(sc);
        }
    }

    Log::GetLog()->info("CustomShop: ready  (shop='{}',  key='{}')",
                        CustomShop::ShopConfig::Get().ShopName(),
                        CustomShop::ShopConfig::Get().UiKey());
}

extern "C" __declspec(dllexport) void Plugin_Unload() {
    ArkApi::GetHooks().DisableHook(
        "AShooterGameMode.BeginPlay()",
        Hook_AShooterGameMode_BeginPlay);

    ArkApi::GetHooks().DisableHook(
        "AShooterGameMode.HandleNewPlayer_Implementation("
        "AShooterPlayerController*,UPrimalPlayerData*,AShooterCharacter*,bool)",
        Hook_AShooterGameMode_HandleNewPlayer);

    CustomShop::Commands::Unregister();
    Log::GetLog()->info("CustomShop: unloaded");
}
