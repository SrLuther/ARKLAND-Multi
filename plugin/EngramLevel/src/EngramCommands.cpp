#include "pch.h"
#include "EngramCommands.h"
#include "EngramConfig.h"

#include <mutex>

namespace {

std::mutex g_prefs_mu;
std::vector<std::string> g_opted_in;

std::string PrefsPath() {
    return ArkApi::Tools::GetCurrentDir() +
           "/ArkApi/Plugins/EngramLevel/autoengram.json";
}

std::string ToWinPath(std::string path) {
    for (char& ch : path) {
        if (ch == '/') ch = '\\';
    }
    return path;
}

bool EnsurePrefsDir() {
    std::string dir = ToWinPath(PrefsPath());
    const auto slash = dir.find_last_of('\\');
    if (slash == std::string::npos) return false;
    dir.resize(slash);
    for (size_t i = 0; i < dir.size(); ++i) {
        if (dir[i] != '\\' || i < 3) continue;
        CreateDirectoryA(dir.substr(0, i).c_str(), nullptr);
    }
    if (CreateDirectoryA(dir.c_str(), nullptr)) return true;
    return GetLastError() == ERROR_ALREADY_EXISTS;
}

bool WritePrefsAtomic(const std::string& path, const std::string& data) {
    if (!EnsurePrefsDir()) {
        Log::GetLog()->error("EngramLevel: não criou a pasta de {}", path);
        return false;
    }
    const std::string final_path = ToWinPath(path);
    const std::string tmp_path = final_path + ".tmp";
    HANDLE file = CreateFileA(
        tmp_path.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        Log::GetLog()->error(
            "EngramLevel: não gravou {} (erro {})", tmp_path, GetLastError());
        return false;
    }
    DWORD written = 0;
    const BOOL ok = data.empty() ||
        WriteFile(file, data.data(), static_cast<DWORD>(data.size()), &written, nullptr);
    if (!ok || written != data.size() || !FlushFileBuffers(file)) {
        CloseHandle(file);
        DeleteFileA(tmp_path.c_str());
        Log::GetLog()->error("EngramLevel: falhou a escrita de {}", tmp_path);
        return false;
    }
    CloseHandle(file);
    if (!MoveFileExA(tmp_path.c_str(), final_path.c_str(),
                     MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        DeleteFileA(tmp_path.c_str());
        Log::GetLog()->error(
            "EngramLevel: não trocou {} (erro {})", final_path, GetLastError());
        return false;
    }
    return true;
}

std::wstring Utf8ToWide(const std::string& text) {
    if (text.empty()) return L"";
    const int len = MultiByteToWideChar(CP_UTF8, 0, text.c_str(), -1, nullptr, 0);
    if (len <= 0) return std::wstring(text.begin(), text.end());
    std::wstring out(static_cast<size_t>(len - 1), L'\0');
    MultiByteToWideChar(CP_UTF8, 0, text.c_str(), -1, &out[0], len);
    return out;
}

void SendPlayer(AShooterPlayerController* controller, const std::string& message) {
    if (!controller || message.empty()) return;
    const std::wstring wmsg = Utf8ToWide(message);
    FChatMessage chat;
    chat.SenderName = FString(L"EngramLevel");
    chat.Message = FString(wmsg.c_str());
    chat.SenderSteamName = FString();
    chat.SenderTribeName = FString();
    chat.SenderId = 0;
    chat.SenderIcon = nullptr;
    chat.UserId = FString();
    controller->ClientChatMessage(chat);
}

void SaveUnlocked() {
    nlohmann::json doc;
    doc["OptedIn"] = g_opted_in;
    const std::string path = PrefsPath();
    const std::string body = doc.dump(2) + "\n";
    if (!WritePrefsAtomic(path, body))
        Log::GetLog()->error("EngramLevel: não gravou {}", path);
}

// Liga ou desliga só este SteamID. Não repõe níveis já gastos antes do comando.
void CmdAutoEngram(AShooterPlayerController* controller, FString*, EChatSendMode::Type) {
    if (!controller) return;
    if (!EngramLevel::Config::Get().Enabled()) {
        SendPlayer(controller, "Desbloqueio automático desligado no servidor.");
        return;
    }
    const uint64 steam = ArkApi::GetApiUtils().GetSteamIdFromController(controller);
    if (steam == 0) {
        SendPlayer(controller, "SteamID inválido.");
        return;
    }
    const bool on = EngramLevel::Prefs::Toggle(std::to_string(steam));
    SendPlayer(
        controller,
        on ? "Desbloqueio automático ligado" : "Desbloqueio automático desligado");
}

} // namespace

namespace EngramLevel {
namespace Prefs {

void Load() {
    std::lock_guard<std::mutex> lock(g_prefs_mu);
    EnsurePrefsDir();
    std::ifstream in(ToWinPath(PrefsPath()));
    if (!in) return;

    nlohmann::json doc;
    try {
        in >> doc;
    } catch (const std::exception& e) {
        Log::GetLog()->error(
            "EngramLevel: autoengram.json inválido — mantendo o último estado em memória — {}",
            e.what());
        return;
    }
    if (!doc.is_object() || !doc.contains("OptedIn") || !doc["OptedIn"].is_array()) {
        Log::GetLog()->error(
            "EngramLevel: autoengram.json inválido — mantendo o último estado em memória");
        return;
    }

    std::vector<std::string> loaded;
    for (const auto& item : doc["OptedIn"]) {
        std::string id;
        if (item.is_string())
            id = item.get<std::string>();
        else if (item.is_number_integer())
            id = std::to_string(item.get<int64_t>());
        if (!id.empty() && !IsAutoOn(loaded, id))
            loaded.push_back(id);
    }
    g_opted_in.swap(loaded);
}

bool IsAutoEnabled(const std::string& steam) {
    std::lock_guard<std::mutex> lock(g_prefs_mu);
    return IsAutoOn(g_opted_in, steam);
}

bool Toggle(const std::string& steam) {
    std::lock_guard<std::mutex> lock(g_prefs_mu);
    const bool on = ToggleAuto(g_opted_in, steam);
    SaveUnlocked();
    return on;
}

} // namespace Prefs

namespace Commands {

void Register() {
    ArkApi::GetCommands().AddChatCommand("/autoengram", &CmdAutoEngram);
    Log::GetLog()->info("EngramLevel: comando /autoengram (default desligado)");
}

void Unregister() {
    ArkApi::GetCommands().RemoveChatCommand("/autoengram");
}

} // namespace Commands
} // namespace EngramLevel
