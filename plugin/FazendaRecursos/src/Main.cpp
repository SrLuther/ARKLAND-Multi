#include "pch.h"
#include "FarmConfig.h"
#include "FarmState.h"
#include "FarmCommands.h"
#include "FarmPerms.h"
#include "FarmSync.h"
#include "plugin_version.h"
#include "../../ArklandPluginDebug.h"

extern "C" __declspec(dllexport) void Plugin_Init() {
    Log::Get().Init("FazendaRecursos");
    ArklandPluginDebug::ConfigureFromCustomShop("FazendaRecursos", ARKLAND_PLUGIN_VERSION);
    try {
        FazendaRecursos::FarmConfig::Get().Load();
        FazendaRecursos::FarmState::Get().Load();
    } catch (const std::exception& e) {
        Log::GetLog()->critical("FazendaRecursos: inicialização cancelada: {}", e.what());
        return;
    }
    FazendaRecursos::Perms::Init();
    FazendaRecursos::FarmSync::Start();
    FazendaRecursos::Commands::Register();
    Log::GetLog()->info("FazendaRecursos v{}-test iniciado; licença {}", ARKLAND_PLUGIN_VERSION, FazendaRecursos::FarmConfig::Get().LicenseGroup());
}

extern "C" __declspec(dllexport) void Plugin_Unload() {
    FazendaRecursos::FarmSync::Stop();
    FazendaRecursos::Commands::Unregister();
    if (!FazendaRecursos::FarmState::Get().Save())
        Log::GetLog()->error("FazendaRecursos: não foi possível persistir o estado no unload");
    Log::GetLog()->info("FazendaRecursos: descarregado");
    ArklandPluginDebug::Shutdown();
}
