#include "pch.h"
#include "plugin_version.h"
#include "HuntCommands.h"
#include "HuntConfig.h"
#include "HuntHooks.h"
#include "HuntHttpClient.h"
#include "HuntLifecycle.h"
#include "HuntPerms.h"
#include "HuntRegistry.h"

extern "C" __declspec(dllexport) void Plugin_Init() {
    Log::Get().Init("ArkEventHunt");
    Log::GetLog()->info("ArkEventHunt: initialising...");

    try {
        ArkEventHunt::HuntConfig::Get().Load();
    } catch (const std::exception& e) {
        Log::GetLog()->critical("ArkEventHunt: init error — {}", e.what());
        return;
    }

    ArkEventHunt::Perms::Init();
    ArkEventHunt::Registry::Clear();
    ArkEventHunt::Hooks::Register();
    ArkEventHunt::Commands::Register();
    ArkEventHunt::Lifecycle::Start();

    Log::GetLog()->info(
        "ArkEventHunt v{} ready (Mode A=/eve; Mode B=/eveadm; spike=/evespike)",
        ARKLAND_PLUGIN_VERSION);
}

extern "C" __declspec(dllexport) void Plugin_Unload() {
    ArkEventHunt::Lifecycle::Stop();
    ArkEventHunt::Commands::Unregister();
    ArkEventHunt::Hooks::Unregister();
    ArkEventHunt::Registry::Clear();
    ArkEventHunt::HttpClient::Shutdown();
    Log::GetLog()->info("ArkEventHunt: unloaded");
}
