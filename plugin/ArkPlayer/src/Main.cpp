#include "pch.h"
#include "plugin_version.h"
#include "PlayerCommands.h"
#include "PlayerConfig.h"
#include "PlayerPerms.h"
#include "PlayerPoints.h"

namespace {

bool g_runtime_ready = false;

void OnWorldReady() {
    if (g_runtime_ready) return;
    g_runtime_ready = true;

    // Bindings que podem tocar no mundo só depois de Ready.
    ArkPlayer::Perms::Init();
    ArkPlayer::Points::Init();

    Log::GetLog()->info("ArkPlayer: world ready — Permissions/Points resolvidos");
}

} // anonymous namespace

DECLARE_HOOK(AShooterGameMode_BeginPlay, void, AShooterGameMode*);
void Hook_AShooterGameMode_BeginPlay(AShooterGameMode* _this) {
    AShooterGameMode_BeginPlay_original(_this);
    OnWorldReady();
}

extern "C" __declspec(dllexport) void Plugin_Init() {
    Log::Get().Init("ArkPlayer");
    Log::GetLog()->info("ArkPlayer: initialising...");

    try {
        // Seguro no boot: só JSON em disco — sem GetMapName / mundo.
        ArkPlayer::PlayerConfig::Get().Load();
    } catch (const std::exception& e) {
        Log::GetLog()->critical("ArkPlayer: init error — {}", e.what());
        return;
    }

    ArkApi::GetHooks().SetHook(
        "AShooterGameMode.BeginPlay()",
        Hook_AShooterGameMode_BeginPlay,
        &AShooterGameMode_BeginPlay_original);

    ArkPlayer::Commands::Register();

    // Hot-reload: se o plugin carregar com o servidor já Ready.
    if (ArkApi::GetApiUtils().GetStatus() == ArkApi::ServerStatus::Ready)
        OnWorldReady();

    Log::GetLog()->info("ArkPlayer v{} ready (MVP: /mindwipe /missao /loot /nome /kill)",
                        ARKLAND_PLUGIN_VERSION);
}

extern "C" __declspec(dllexport) void Plugin_Unload() {
    ArkApi::GetHooks().DisableHook(
        "AShooterGameMode.BeginPlay()",
        Hook_AShooterGameMode_BeginPlay);

    ArkPlayer::Commands::Unregister();
    Log::GetLog()->info("ArkPlayer: unloaded");
}
