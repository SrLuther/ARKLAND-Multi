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

void CmdPoll(AShooterPlayerController* controller, FString*, EChatSendMode::Type) {
    if (!controller) return;

    try {
        Log::GetLog()->info("CustomDinoDeliver: /dinolab requested by steam_id={}",
                            CustomDinoDeliver::Bridge::GetSteamId(controller));
        const CustomDinoDeliver::HttpClient::DeliverResult result =
            CustomDinoDeliver::HttpClient::DeliverPending(controller);

        if (result.already_in_progress) {
            SendMsg(controller, FColorList::Yellow,
                    "Dino Lab: entrega em andamento, aguarde.");
        } else if (!result.api_ok) {
            SendMsg(controller, FColorList::Red,
                    "Dino Lab: falha ao contactar a API web.");
        } else if (result.delivered > 0) {
            SendMsg(controller, FColorList::Green,
                    "Dino Lab: " + std::to_string(result.delivered)
                    + " dino(s) entregue(s) com sucesso.");
        } else if (result.failed > 0) {
            SendMsg(controller, FColorList::Red,
                    "Dino Lab: falha ao entregar dino customizado. Contate um admin.");
        } else {
            SendMsg(controller, FColorList::Yellow,
                    "Dino Lab: nada pendente na fila.");
        }
    } catch (const std::exception& e) {
        Log::GetLog()->error("CustomDinoDeliver: /dinolab failed — {}", e.what());
        SendMsg(controller, FColorList::Red, "Dino Lab: erro ao verificar fila.");
    } catch (...) {
        Log::GetLog()->error("CustomDinoDeliver: /dinolab failed — unknown error");
        SendMsg(controller, FColorList::Red, "Dino Lab: erro ao verificar fila.");
    }
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
