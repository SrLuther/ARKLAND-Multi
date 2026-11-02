#include "pch.h"
#include "FarmConfig.h"
#include "FarmState.h"
#include "FarmCommands.h"
#include "FarmPerms.h"

extern "C" __declspec(dllexport) void Plugin_Init() {
    Log::Get().Init("FazendaRecursos");
    try {
        FazendaRecursos::FarmConfig::Get().Load();
        FazendaRecursos::FarmState::Get().Load();
    } catch (const std::exception& e) {
        Log::GetLog()->critical("FazendaRecursos: inicialização cancelada: {}", e.what());
        return;
    }
    FazendaRecursos::Perms::Init();
    FazendaRecursos::Commands::Register();
    Log::GetLog()->info("FazendaRecursos v0.1.3-test iniciado; licença {}", FazendaRecursos::FarmConfig::Get().LicenseGroup());
}

extern "C" __declspec(dllexport) void Plugin_Unload() {
    FazendaRecursos::Commands::Unregister();
    if (!FazendaRecursos::FarmState::Get().Save())
        Log::GetLog()->error("FazendaRecursos: não foi possível persistir o estado no unload");
    Log::GetLog()->info("FazendaRecursos: descarregado");
}
