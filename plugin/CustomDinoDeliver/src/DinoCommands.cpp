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

void CmdPollImpl(AShooterPlayerController* controller, FString*, EChatSendMode::Type,
                 const char* commandLabel) {
    if (!controller) return;

    try {
        Log::GetLog()->info("CustomDinoDeliver: {} requested by steam_id={}",
                            commandLabel,
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
        Log::GetLog()->error("CustomDinoDeliver: {} failed — {}", commandLabel, e.what());
        SendMsg(controller, FColorList::Red, "Dino Lab: erro ao verificar fila.");
    } catch (...) {
        Log::GetLog()->error("CustomDinoDeliver: {} failed — unknown error", commandLabel);
        SendMsg(controller, FColorList::Red, "Dino Lab: erro ao verificar fila.");
    }
}

void CmdPollDinolab(AShooterPlayerController* controller, FString* args, EChatSendMode::Type mode) {
    CmdPollImpl(controller, args, mode, "/dinolab");
}

void CmdPollDinopoll(AShooterPlayerController* controller, FString* args, EChatSendMode::Type mode) {
    CmdPollImpl(controller, args, mode, "/dinopoll");
}

} // anonymous namespace

namespace CustomDinoDeliver {
namespace Commands {

void Register() {
    ArkApi::GetCommands().AddConsoleCommand("DinoDeliver.Reload", &CmdAdminReload);
    ArkApi::GetCommands().AddChatCommand("/dinolab", &CmdPollDinolab);
    ArkApi::GetCommands().AddChatCommand("/dinopoll", &CmdPollDinopoll);
    Log::GetLog()->info("CustomDinoDeliver: commands registered (/dinolab, /dinopoll)");
}

void Unregister() {
    ArkApi::GetCommands().RemoveConsoleCommand("DinoDeliver.Reload");
    ArkApi::GetCommands().RemoveChatCommand("/dinolab");
    ArkApi::GetCommands().RemoveChatCommand("/dinopoll");
}

} // namespace Commands
} // namespace CustomDinoDeliver
