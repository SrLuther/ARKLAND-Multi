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
#include "ShopPlayerMonitor.h"
#include "HttpClient.h"
#include "ShopDebug.h"
#include "ShopVitrine.h"
#include <Timer.h>
#include <atomic>

// ─────────────────────────────────────────────────────────────────
//  Plugin entry points required by ArkApi v3 (ASE).
// ─────────────────────────────────────────────────────────────────

namespace {

constexpr int kPendingPollSeconds = 60;
constexpr int kTribeSyncPollSeconds = 180;
constexpr int kTribeSyncRequestPollSeconds = 15;
constexpr int kPlayerMonitorHeartbeatSeconds = 90;
std::atomic<bool> g_player_monitor_heartbeat_scheduled{false};

void PollPendingForOnlinePlayers() {
    // Um DeliverPending por tick — N×(claim+deliver+release) no mesmo callback
    // bloqueava o game thread (HangWatcher) com vários jogadores online.
    const auto& pcs =
        ArkApi::GetApiUtils().GetWorld()->PlayerControllerListField();
    int scheduled = 0;
    for (TWeakObjectPtr<APlayerController> wpc : pcs) {
        auto* sc = static_cast<AShooterPlayerController*>(wpc.Get());
        if (!sc) continue;
        AShooterPlayerController* raw = sc;
        const int delay_sec = scheduled;
        ++scheduled;
        API::Timer::Get().DelayExecute([raw]() {
            if (!raw) return;
            CustomShop::HttpClient::DeliverPending(raw);
        }, delay_sec);
    }
}

// Vitrine de Recursos: conclui journals de envio interrompidos (crash/web fora) apos o mapa subir.
void ScheduleVitrineRecovery() {
    API::Timer::Get().DelayExecute([]() {
        CustomShop::Vitrine::RecoverAll();
    }, 45);
}

void SchedulePendingPoll() {
    API::Timer::Get().DelayExecute([]() {
        if (ArkApi::GetApiUtils().GetStatus() == ArkApi::ServerStatus::Ready)
            PollPendingForOnlinePlayers();
        SchedulePendingPoll();
    }, kPendingPollSeconds);
}

// Separado do DeliverPending: não empilhar N delivers + N TribeSync POSTs no mesmo tick.
void ScheduleTribeSyncPoll() {
    API::Timer::Get().DelayExecute([]() {
        if (ArkApi::GetApiUtils().GetStatus() == ArkApi::ServerStatus::Ready)
            CustomShop::TribeSync::SyncAllOnlinePlayers();
        ScheduleTribeSyncPoll();
    }, kTribeSyncPollSeconds);
}

// Pull «Verificar de novo»: tribe_sync_requests na MySQL → presença sem RCON.
void ScheduleTribeSyncRequestPoll() {
    API::Timer::Get().DelayExecute([]() {
        if (ArkApi::GetApiUtils().GetStatus() == ArkApi::ServerStatus::Ready)
            CustomShop::TribeSync::PollPendingSyncRequests();
        ScheduleTribeSyncRequestPoll();
    }, kTribeSyncRequestPollSeconds);
}

void SchedulePlayerMonitorHeartbeat() {
    bool expected = false;
    if (!g_player_monitor_heartbeat_scheduled.compare_exchange_strong(expected, true)) return;
    API::Timer::Get().DelayExecute([]() {
        g_player_monitor_heartbeat_scheduled.store(false);
        if (ArkApi::GetApiUtils().GetStatus() == ArkApi::ServerStatus::Ready)
            CustomShop::PlayerMonitor::HeartbeatOnlinePlayers();
        SchedulePlayerMonitorHeartbeat();
    }, kPlayerMonitorHeartbeatSeconds);
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
    ScheduleTribeSyncPoll();
    ScheduleTribeSyncRequestPoll();
    SchedulePlayerMonitorHeartbeat();
    ScheduleVitrineRecovery();
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

    // Vitrine: retoma envio interrompido (reenvia upload_id ou devolve itens). Por SteamID
    // (resolve o controller no momento da execucao; nao guarda ponteiro).
    API::Timer::Get().DelayExecute([steam_id]() {
        CustomShop::Vitrine::RecoverForSteamId(steam_id);
    }, 12);

    // TribeSync é independente de CrossChat.Enabled — presença Minha Tribo.
    Log::GetLog()->info(
        "HandleNewPlayer: TribeSync schedule steam_id='{}'", steam_id);
    CustomShop::TribeSync::ScheduleSyncAfterLogin(raw_ctrl);

    const std::string monitor_steam_id = steam_id;
    API::Timer::Get().DelayExecute([monitor_steam_id]() {
        if (auto* current = CustomShop::Bridge::FindPlayer(monitor_steam_id))
            CustomShop::PlayerMonitor::Record(current, "connect");
    }, 12);

    return result;
}

DECLARE_HOOK(AShooterGameMode_Logout, void, AShooterGameMode*, AController*);
void Hook_AShooterGameMode_Logout(AShooterGameMode* _this, AController* exiting) {
    CustomShop::PlayerMonitor::RecordDisconnect(exiting);
    AShooterGameMode_Logout_original(_this, exiting);
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
        CustomShop::Debug::SetDb(CustomShop::ShopPoints::Get().GetDb());
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

    CustomShop::PlayerMonitor::Start();

    ArkApi::GetHooks().SetHook(
        "AShooterGameMode.BeginPlay()",
        Hook_AShooterGameMode_BeginPlay,
        &AShooterGameMode_BeginPlay_original);

    ArkApi::GetHooks().SetHook(
        "AShooterGameMode.HandleNewPlayer_Implementation("
        "AShooterPlayerController*,UPrimalPlayerData*,AShooterCharacter*,bool)",
        Hook_AShooterGameMode_HandleNewPlayer,
        &AShooterGameMode_HandleNewPlayer_original);

    ArkApi::GetHooks().SetHook(
        "AShooterGameMode.Logout",
        Hook_AShooterGameMode_Logout,
        &AShooterGameMode_Logout_original);

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
        ScheduleTribeSyncPoll();
        ScheduleTribeSyncRequestPoll();
        SchedulePlayerMonitorHeartbeat();
        ScheduleVitrineRecovery();
    }

    {
        const auto& settings = CustomShop::ShopConfig::Get().Settings();
        const std::string settings_sid = settings.value("ServerId", "");
        const std::string cc_sid =
            CustomShop::ShopConfig::Get().CrossChat().value("ServerId", "");
        Log::GetLog()->info(
            "CustomShop v{} ready  (shop='{}', web='{}', cloud_cmds=/upload /download /nuvem, "
            "cross_chat={}, Settings.ServerId='{}', CrossChat.ServerId='{}', {})",
            ARKLAND_PLUGIN_VERSION,
            CustomShop::ShopConfig::Get().ShopName(),
            CustomShop::ShopConfig::Get().WebApiUrl(),
            CustomShop::ShopConfig::Get().CrossChat().value("Enabled", false) ? "on" : "off",
            settings_sid.empty() ? "(vazio)" : settings_sid,
            cc_sid.empty() ? "(vazio)" : cc_sid,
            CustomShop::Debug::StatusSummary());
    }
}

extern "C" __declspec(dllexport) void Plugin_Unload() {
    ArkApi::GetHooks().DisableHook(
        "AShooterGameMode.BeginPlay()",
        Hook_AShooterGameMode_BeginPlay);

    ArkApi::GetHooks().DisableHook(
        "AShooterGameMode.HandleNewPlayer_Implementation("
        "AShooterPlayerController*,UPrimalPlayerData*,AShooterCharacter*,bool)",
        Hook_AShooterGameMode_HandleNewPlayer);

    ArkApi::GetHooks().DisableHook(
        "AShooterGameMode.Logout",
        Hook_AShooterGameMode_Logout);

    CustomShop::Commands::Unregister();
    CustomShop::PlayerMonitor::Stop();
    CustomShop::CrossChat::Stop();
    CustomShop::HttpClient::Shutdown();
    CustomShop::Debug::Shutdown();
    Log::GetLog()->info("CustomShop: unloaded");
}
