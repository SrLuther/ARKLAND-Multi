#include "pch.h"
#include "Commands.h"
#include "ShopBridge.h"
#include "ShopConfig.h"
#include "ShopData.h"
#include "ShopPoints.h"
#include "ShopVip.h"
#include "ShopEntitlements.h"
#include "ShopCloudInventory.h"
#include "ShopPerms.h"
#include "TimedPoints.h"
#include "HttpClient.h"
#include <Timer.h>

// ─────────────────────────────────────────────────────────────────
//  Plugin entry points required by ArkApi v3 (ASE).
// ─────────────────────────────────────────────────────────────────

namespace {

constexpr int kPendingPollSeconds = 60;

void PollPendingForOnlinePlayers() {
    const auto& pcs =
        ArkApi::GetApiUtils().GetWorld()->PlayerControllerListField();
    for (TWeakObjectPtr<APlayerController> wpc : pcs) {
        auto* sc = static_cast<AShooterPlayerController*>(wpc.Get());
        if (sc) CustomShop::HttpClient::DeliverPending(sc);
    }
}

void SchedulePendingPoll() {
    API::Timer::Get().DelayExecute([]() {
        if (ArkApi::GetApiUtils().GetStatus() == ArkApi::ServerStatus::Ready)
            PollPendingForOnlinePlayers();
        SchedulePendingPoll();
    }, kPendingPollSeconds);
}

} // anonymous namespace

// ── Hooks ─────────────────────────────────────────────────────────

DECLARE_HOOK(AShooterGameMode_BeginPlay, void, AShooterGameMode*);
void Hook_AShooterGameMode_BeginPlay(AShooterGameMode* _this) {
    AShooterGameMode_BeginPlay_original(_this);

    CustomShop::Perms::Init();

    const auto& pcs =
        ArkApi::GetApiUtils().GetWorld()->PlayerControllerListField();
    for (TWeakObjectPtr<APlayerController> wpc : pcs) {
        auto* sc = static_cast<AShooterPlayerController*>(wpc.Get());
        CustomShop::Data::InitPlayer(sc);
    }

    SchedulePendingPoll();
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

    CustomShop::Data::InitPlayer(player);

    const std::string steam_id = CustomShop::Bridge::GetSteamId(player);
    Log::GetLog()->info("HandleNewPlayer: steam_id='{}'", steam_id);

    AShooterPlayerController* raw_ctrl = player;
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
        CustomShop::ShopVip::Get().SetDb(
            CustomShop::ShopPoints::Get().GetDb());
        CustomShop::ShopEntitlements::Get().SetDb(
            CustomShop::ShopPoints::Get().GetDb());
        CustomShop::ShopCloudInventory::Get().SetDb(
            CustomShop::ShopPoints::Get().GetDb());
        CustomShop::ShopVip::Get().PruneExpired();
        CustomShop::ShopEntitlements::Get().PruneExpired();
    }
    catch (const std::exception& e) {
        Log::GetLog()->critical("CustomShop: init error — {}", e.what());
        return;
    }

    ArkApi::GetHooks().SetHook(
        "AShooterGameMode.BeginPlay()",
        Hook_AShooterGameMode_BeginPlay,
        &AShooterGameMode_BeginPlay_original);

    ArkApi::GetHooks().SetHook(
        "AShooterGameMode.HandleNewPlayer_Implementation("
        "AShooterPlayerController*,UPrimalPlayerData*,AShooterCharacter*,bool)",
        Hook_AShooterGameMode_HandleNewPlayer,
        &AShooterGameMode_HandleNewPlayer_original);

    CustomShop::Commands::Register();
    CustomShop::TimedPoints::Start();

    if (ArkApi::GetApiUtils().GetStatus() == ArkApi::ServerStatus::Ready) {
        CustomShop::Perms::Init();

        const auto& pcs =
            ArkApi::GetApiUtils().GetWorld()->PlayerControllerListField();
        for (TWeakObjectPtr<APlayerController> wpc : pcs) {
            auto* sc = static_cast<AShooterPlayerController*>(wpc.Get());
            CustomShop::Data::InitPlayer(sc);
        }
        SchedulePendingPoll();
    }

    Log::GetLog()->info(
        "CustomShop: ready  (shop='{}', web='{}', cloud_cmds=/upload /download /nuvem)",
        CustomShop::ShopConfig::Get().ShopName(),
        CustomShop::ShopConfig::Get().WebApiUrl());
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
    CustomShop::HttpClient::Shutdown();
    Log::GetLog()->info("CustomShop: unloaded");
}
