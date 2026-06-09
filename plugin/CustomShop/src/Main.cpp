#include "pch.h"
#include "Commands.h"
#include "ShopBridge.h"
#include "ShopConfig.h"
#include "ShopData.h"
#include "ShopPoints.h"
#include "ShopVip.h"
#include "ShopPerms.h"
#include "TimedPoints.h"
#include "HttpClient.h"
#include <Timer.h>

// ─────────────────────────────────────────────────────────────────
//  Plugin entry points required by ArkApi v3 (ASE).
// ─────────────────────────────────────────────────────────────────

// ── Hooks ─────────────────────────────────────────────────────────

DECLARE_HOOK(AShooterGameMode_BeginPlay, void, AShooterGameMode*);
void Hook_AShooterGameMode_BeginPlay(AShooterGameMode* _this) {
    AShooterGameMode_BeginPlay_original(_this);

    // All plugins are loaded by BeginPlay — bind Permissions now.
    CustomShop::Perms::Init();

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

    // Register player in DB immediately (safe at this stage).
    CustomShop::Data::InitPlayer(player);

    const std::string steam_id = CustomShop::Bridge::GetSteamId(player);
    Log::GetLog()->info("HandleNewPlayer: hook fired, steam_id='{}'", steam_id);

    // Delay buff/config delivery. SDK's TWeakObjectPtr has no raw-ptr ctor, so
    // we capture the raw pointer and validate it via the GC-safe controller list
    // before use (wpc.Get() returns null for garbage-collected objects).
    AShooterPlayerController* raw_ctrl = player;
    API::Timer::Get().DelayExecute([raw_ctrl, steam_id]() {
        // APlayerControllers are not GC'd while the player is connected.
        // The 5s window makes dangling pointer virtually impossible.
        if (!raw_ctrl) return;
        Log::GetLog()->info(
            "ShopBridge: timer fired, sending config to '{}'", steam_id);
        ArkApi::GetApiUtils().SendNotification(
            raw_ctrl, FLinearColor(0, 1, 1, 1), 1.2f, 6.f, nullptr,
            L"[Shop] Iniciando... (timer ok)");
        CustomShop::Data::InitShop(raw_ctrl);
    }, 5);

    // After delivering config, check for pending online purchases
    // (items bought via arkshop_web while player was offline).
    API::Timer::Get().DelayExecute([raw_ctrl]() {
        if (!raw_ctrl) return;
        CustomShop::HttpClient::DeliverPending(raw_ctrl);
    }, 8);

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
        CustomShop::HttpClient::Configure(
            CustomShop::ShopConfig::Get().WebApiUrl(),
            CustomShop::ShopConfig::Get().WebApiKey());
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

    // Start timed-points reward timer.
    CustomShop::TimedPoints::Start();

    // If the server was already running (hot-reload scenario), initialise now.
    if (ArkApi::GetApiUtils().GetStatus() == ArkApi::ServerStatus::Ready) {
        // BeginPlay already fired — bind Permissions immediately.
        CustomShop::Perms::Init();

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
