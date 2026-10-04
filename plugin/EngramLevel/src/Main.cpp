#include "pch.h"
#include "plugin_version.h"
#include "EngramCommands.h"
#include "EngramConfig.h"
#include "EngramHooks.h"

namespace {

void CmdReload(APlayerController*, FString*, bool) {
    try {
        EngramLevel::Config::Get().Load();
        EngramLevel::Hooks::SyncCrashMask();
        Log::GetLog()->info("EngramLevel: config recarregado");
    } catch (const std::exception& e) {
        Log::GetLog()->error("EngramLevel reload: {}", e.what());
    }
}

} // namespace

extern "C" __declspec(dllexport) void Plugin_Init() {
    Log::Get().Init("EngramLevel");
    Log::GetLog()->info("EngramLevel: initialising...");

    try {
        EngramLevel::Config::Get().Load();
        EngramLevel::Prefs::Load();
        EngramLevel::Hooks::SyncCrashMask();
    } catch (const std::exception& e) {
        Log::GetLog()->critical("EngramLevel: init error — {}", e.what());
        return;
    }

    EngramLevel::Hooks::Register();
    EngramLevel::Commands::Register();
    ArkApi::GetCommands().AddConsoleCommand("EngramLevel.Reload", &CmdReload);

    Log::GetLog()->info(
        "EngramLevel v{} ready (level up e mindwipe: só os engramas daquele nível)",
        ARKLAND_PLUGIN_VERSION);
}

extern "C" __declspec(dllexport) void Plugin_Unload() {
    ArkApi::GetCommands().RemoveConsoleCommand("EngramLevel.Reload");
    EngramLevel::Commands::Unregister();
    EngramLevel::Hooks::Unregister();
    EngramLevel::Hooks::ReleaseCrashMask();
    Log::GetLog()->info("EngramLevel: unloaded");
}
