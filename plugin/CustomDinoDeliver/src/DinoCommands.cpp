#include "pch.h"
#include "DinoCommands.h"
#include "DinoBridge.h"
#include "DinoConfig.h"
#include "DinoHttpClient.h"

namespace {

void SendMsg(AShooterPlayerController* c, const FLinearColor& color, const std::string& msg) {
    if (!c || msg.empty()) return;
    ArkApi::GetApiUtils().SendServerMessage(c, color, msg.c_str());
}

void CmdAdminReload(APlayerController* pc, FString*, bool) {
    auto* admin = static_cast<AShooterPlayerController*>(pc);
    try {
        CustomDinoDeliver::DinoConfig::Get().Load();
        CustomDinoDeliver::HttpClient::Configure(
            CustomDinoDeliver::DinoConfig::Get().WebApiUrl(),
            CustomDinoDeliver::DinoConfig::Get().WebApiKey());
        if (admin)
            SendMsg(admin, FColorList::Green, "CustomDinoDeliver reloaded");
        Log::GetLog()->info("CustomDinoDeliver: config reloaded by admin command");
    } catch (const std::exception& e) {
        const std::string err = std::string("Reload failed: ") + e.what();
        Log::GetLog()->error("{}", err);
        if (admin) SendMsg(admin, FColorList::Red, err);
    }
}

void CmdPoll(APlayerController* pc, FString*, bool) {
    auto* controller = static_cast<AShooterPlayerController*>(pc);
    if (!controller) return;
    const bool ok = CustomDinoDeliver::HttpClient::DeliverPending(controller);
    SendMsg(controller, ok ? FColorList::Green : FColorList::Yellow,
            ok ? "Dino Lab: entrega verificada." : "Dino Lab: nada pendente ou falha na API.");
}

} // anonymous namespace

namespace CustomDinoDeliver {
namespace Commands {

void Register() {
    ArkApi::GetCommands().AddConsoleCommand("DinoDeliver.Reload", &CmdAdminReload);
    ArkApi::GetCommands().AddChatCommand("/dinolab", &CmdPoll);
    Log::GetLog()->info("CustomDinoDeliver: commands registered");
}

void Unregister() {
    ArkApi::GetCommands().RemoveConsoleCommand("DinoDeliver.Reload");
    ArkApi::GetCommands().RemoveChatCommand("/dinolab");
}

} // namespace Commands
} // namespace CustomDinoDeliver
