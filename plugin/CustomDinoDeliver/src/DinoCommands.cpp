#include "pch.h"
#include "DinoCommands.h"
#include "DinoBridge.h"
#include "DinoConfig.h"
#include "DinoHttpClient.h"
#include "DinoDebug.h"

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
            SendMsg(admin, FColorList::Green,
                    "CustomDinoDeliver reloaded — " +
                        CustomDinoDeliver::Debug::StatusSummary());
        Log::GetLog()->info("CustomDinoDeliver: config reloaded by admin command");
    } catch (const std::exception& e) {
        const std::string err = std::string("Reload failed: ") + e.what();
        Log::GetLog()->error("{}", err);
        if (admin) SendMsg(admin, FColorList::Red, err);
    }
}

std::vector<std::string> SplitCmd(FString* cmd_str) {
    std::vector<std::string> parts;
    if (!cmd_str) return parts;
    const std::string s = cmd_str->ToString();
    std::istringstream ss(s);
    std::string token;
    while (ss >> token)
        parts.push_back(token);
    return parts;
}

void CmdAdminDebugLevel(APlayerController* pc, FString* cmd, bool) {
    auto* admin = static_cast<AShooterPlayerController*>(pc);
    const auto parts = SplitCmd(cmd);
    if (parts.size() >= 2) {
        const std::string arg = parts[1];
        if (arg == "on" || arg == "1" || arg == "true") {
            CustomDinoDeliver::Debug::SetEnabledRuntime(true);
            CustomDinoDeliver::Debug::SetLevelRuntime(
                CustomDinoDeliver::Debug::Level::Debug);
        } else if (arg == "off" || arg == "0" || arg == "false") {
            CustomDinoDeliver::Debug::SetEnabledRuntime(false);
        } else {
            const auto lvl = CustomDinoDeliver::Debug::ParseLevel(arg);
            CustomDinoDeliver::Debug::SetEnabledRuntime(
                lvl != CustomDinoDeliver::Debug::Level::Off);
            CustomDinoDeliver::Debug::SetLevelRuntime(lvl);
        }
    }
    const std::string status = CustomDinoDeliver::Debug::StatusSummary();
    Log::GetLog()->info("{}", status);
    if (admin) SendMsg(admin, FColorList::Green, status);
}

void CmdDinoDebugLog(AShooterPlayerController* controller, FString*, EChatSendMode::Type) {
    if (!controller) return;
    SendMsg(controller, FColorList::Cyan, CustomDinoDeliver::Debug::StatusSummary());
    const auto lines = CustomDinoDeliver::Debug::RecentLines(8);
    if (lines.empty()) {
        SendMsg(controller, FColorList::Yellow,
                "Ring buffer vazio — ligue Debug.Enabled=true e DinoDeliver.Reload.");
        return;
    }
    for (const auto& line : lines) {
        std::string short_line = line;
        if (short_line.size() > 220)
            short_line = short_line.substr(0, 217) + "...";
        SendMsg(controller, FColorList::White, short_line);
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
    ArkApi::GetCommands().AddConsoleCommand("DinoDeliver.DebugLevel", &CmdAdminDebugLevel);
    ArkApi::GetCommands().AddChatCommand("/dinolab", &CmdPollDinolab);
    ArkApi::GetCommands().AddChatCommand("/dinopoll", &CmdPollDinopoll);
    ArkApi::GetCommands().AddChatCommand("/dinodebug", &CmdDinoDebugLog);
    Log::GetLog()->info(
        "CustomDinoDeliver: commands registered (/dinolab, /dinopoll, /dinodebug)");
}

void Unregister() {
    ArkApi::GetCommands().RemoveConsoleCommand("DinoDeliver.Reload");
    ArkApi::GetCommands().RemoveConsoleCommand("DinoDeliver.DebugLevel");
    ArkApi::GetCommands().RemoveChatCommand("/dinolab");
    ArkApi::GetCommands().RemoveChatCommand("/dinopoll");
    ArkApi::GetCommands().RemoveChatCommand("/dinodebug");
}

} // namespace Commands
} // namespace CustomDinoDeliver
