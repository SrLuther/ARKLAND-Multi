#include "pch.h"
#include "plugin_version.h"
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
#include "ShopCrossChat.h"
#include "ShopTribeSync.h"
#include "HttpClient.h"
#include <Timer.h>

// ─────────────────────────────────────────────────────────────────
//  Plugin entry points required by ArkApi v3 (ASE).
// ─────────────────────────────────────────────────────────────────

namespace {

constexpr int kPendingPollSeconds = 60;

int g_tribe_sync_poll_ticks = 0;

void PollPendingForOnlinePlayers() {
    const auto& pcs =
        ArkApi::GetApiUtils().GetWorld()->PlayerControllerListField();
    for (TWeakObjectPtr<APlayerController> wpc : pcs) {
        auto* sc = static_cast<AShooterPlayerController*>(wpc.Get());
        if (sc) CustomShop::HttpClient::DeliverPending(sc);
    }
    // A cada ~3 min: reenvia presença (jogadores já online / tribo atrasada).
    ++g_tribe_sync_poll_ticks;
    if (g_tribe_sync_poll_ticks >= 3) {
        g_tribe_sync_poll_ticks = 0;
        CustomShop::TribeSync::SyncAllOnlinePlayers();
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
    CustomShop::ShopEntitlements::Get().SyncPlayerOnJoin(steam_id);
    CustomShop::ShopCloudInventory::ClearOperationInProgress(steam_id);

    AShooterPlayerController* raw_ctrl = player;
    API::Timer::Get().DelayExecute([raw_ctrl]() {
        if (!raw_ctrl) return;
        CustomShop::HttpClient::DeliverPending(raw_ctrl);
    }, 8);

    // Tribe data pode ainda não estar pronto no tick do login — várias tentativas.
    CustomShop::TribeSync::ScheduleSyncAfterLogin(raw_ctrl);

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
        CustomShop::CrossChat::SetDb(
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
    CustomShop::CrossChat::Start();

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
        "CustomShop v{} ready  (shop='{}', web='{}', cloud_cmds=/upload /download /nuvem, cross_chat={})",
        ARKLAND_PLUGIN_VERSION,
        CustomShop::ShopConfig::Get().ShopName(),
        CustomShop::ShopConfig::Get().WebApiUrl(),
        CustomShop::ShopConfig::Get().CrossChat().value("Enabled", false) ? "on" : "off");
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
    CustomShop::CrossChat::Stop();
    CustomShop::HttpClient::Shutdown();
    Log::GetLog()->info("CustomShop: unloaded");
}
