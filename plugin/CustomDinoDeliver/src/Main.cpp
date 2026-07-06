#include "pch.h"
#include "DinoCommands.h"
#include "DinoConfig.h"
#include "DinoHttpClient.h"
#include <Timer.h>

namespace {

void PollPendingForOnlinePlayers() {
    const auto& pcs =
        ArkApi::GetApiUtils().GetWorld()->PlayerControllerListField();
    for (TWeakObjectPtr<APlayerController> wpc : pcs) {
        auto* sc = static_cast<AShooterPlayerController*>(wpc.Get());
        if (sc) CustomDinoDeliver::HttpClient::DeliverPending(sc);
    }
}

void SchedulePendingPoll() {
    const int interval = CustomDinoDeliver::DinoConfig::Get().PollIntervalSeconds();
    API::Timer::Get().DelayExecute([interval]() {
        if (ArkApi::GetApiUtils().GetStatus() == ArkApi::ServerStatus::Ready)
            PollPendingForOnlinePlayers();
        SchedulePendingPoll();
    }, interval);
}

} // anonymous namespace

DECLARE_HOOK(AShooterGameMode_BeginPlay, void, AShooterGameMode*);
void Hook_AShooterGameMode_BeginPlay(AShooterGameMode* _this) {
    AShooterGameMode_BeginPlay_original(_this);
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

    AShooterPlayerController* raw_ctrl = player;
    API::Timer::Get().DelayExecute([raw_ctrl]() {
        if (!raw_ctrl) return;
        CustomDinoDeliver::HttpClient::DeliverPending(raw_ctrl);
    }, 8);

    return result;
}

extern "C" __declspec(dllexport) void Plugin_Init() {
    Log::Get().Init("CustomDinoDeliver");
    Log::GetLog()->info("CustomDinoDeliver: initialising...");

    try {
        CustomDinoDeliver::DinoConfig::Get().Load();
        CustomDinoDeliver::HttpClient::Configure(
            CustomDinoDeliver::DinoConfig::Get().WebApiUrl(),
            CustomDinoDeliver::DinoConfig::Get().WebApiKey());
    } catch (const std::exception& e) {
        Log::GetLog()->critical("CustomDinoDeliver: init error — {}", e.what());
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

    CustomDinoDeliver::Commands::Register();

    if (ArkApi::GetApiUtils().GetStatus() == ArkApi::ServerStatus::Ready)
        SchedulePendingPoll();

    Log::GetLog()->info(
        "CustomDinoDeliver: ready (web='{}', poll={}s)",
        CustomDinoDeliver::DinoConfig::Get().WebApiUrl(),
        CustomDinoDeliver::DinoConfig::Get().PollIntervalSeconds());
}

extern "C" __declspec(dllexport) void Plugin_Unload() {
    ArkApi::GetHooks().DisableHook(
        "AShooterGameMode.BeginPlay()",
        Hook_AShooterGameMode_BeginPlay);

    ArkApi::GetHooks().DisableHook(
        "AShooterGameMode.HandleNewPlayer_Implementation("
        "AShooterPlayerController*,UPrimalPlayerData*,AShooterCharacter*,bool)",
        Hook_AShooterGameMode_HandleNewPlayer);

    CustomDinoDeliver::Commands::Unregister();
    CustomDinoDeliver::HttpClient::Shutdown();
    Log::GetLog()->info("CustomDinoDeliver: unloaded");
}
