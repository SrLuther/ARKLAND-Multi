#include "pch.h"
#include "ShopCrossChat.h"
#include "ShopBridge.h"
#include "ShopConfig.h"
#include "HttpClient.h"

#include <Timer.h>
#include <chrono>
#include <mutex>
#include <unordered_map>
#include <vector>

namespace {

MYSQL* g_db = nullptr;
uint64_t g_last_id = 0;
int g_poll_ticks = 0;
std::mutex g_rate_mutex;
std::unordered_map<std::string, std::chrono::steady_clock::time_point> g_rate_limit;

std::string SanitizeAscii(std::string msg) {
    std::string out;
    out.reserve(msg.size());
    for (unsigned char ch : msg) {
        if (ch >= 32 && ch <= 126)
            out.push_back(static_cast<char>(ch));
        else if (ch == '\t')
            out.push_back(' ');
    }
    while (!out.empty() && out.front() == ' ')
        out.erase(out.begin());
    while (!out.empty() && out.back() == ' ')
        out.pop_back();
    return out;
}

bool Escape(const std::string& in, std::string& out) {
    if (!g_db) {
        out = in;
        return true;
    }
    if (in.empty()) {
        out.clear();
        return true;
    }
    std::vector<char> buf(in.size() * 2 + 1);
    const unsigned long len = mysql_real_escape_string(
        g_db, buf.data(), in.c_str(), static_cast<unsigned long>(in.size()));
    out.assign(buf.data(), len);
    return true;
}

bool Exec(const char* sql) {
    if (!g_db) return false;
    if (mysql_query(g_db, sql) != 0) {
        Log::GetLog()->error("CrossChat::Exec failed: {}", mysql_error(g_db));
        return false;
    }
    return true;
}

const nlohmann::json& Cfg() {
    return CustomShop::ShopConfig::Get().CrossChat();
}

bool Enabled() {
    return Cfg().value("Enabled", false);
}

std::string ServerId() {
    const std::string id = Cfg().value("ServerId", "");
    return id.empty() ? "Server" : id;
}

std::string CommandToken() {
    std::string cmd = Cfg().value("Command", "/c");
    if (cmd.empty()) cmd = "/c";
    return cmd;
}

int MaxMessageLength() {
    return std::max(1, std::min(500, Cfg().value("MaxMessageLength", 200)));
}

int RateLimitSeconds() {
    return std::max(0, Cfg().value("RateLimitSeconds", 2));
}

bool UseWebApi() {
    return Cfg().value("UseWebApi", false);
}

bool AutoCapture() {
    return Cfg().value("AutoCapture", true);
}

bool IgnoreCommands() {
    return Cfg().value("IgnoreCommands", true);
}

bool GlobalChatOnly() {
    return Cfg().value("GlobalChatOnly", true);
}

void SendLocal(AShooterPlayerController* player, const std::string& text) {
    if (!player || text.empty()) return;
    static const FString kSender(L"Cluster");
    ArkApi::GetApiUtils().SendChatMessage(player, kSender, text.c_str());
}

// Relay cluster chat without putting the player name in SenderName.
// ARK resolves SenderName to online players and applies native badges
// (gold star = server admin, blue gate = tribe admin) even for relayed text.
void BroadcastClusterChat(const FString& sender, const FString& body) {
    if (body.IsEmpty()) return;

    FChatMessage chat;
    chat.SenderName = sender;
    chat.Message = body;
    chat.SenderSteamName = FString();
    chat.SenderTribeName = FString();
    chat.SenderId = 0;
    chat.SenderIcon = nullptr;
    chat.UserId = FString();

    const auto& player_controllers = ArkApi::GetApiUtils().GetWorld()->PlayerControllerListField();
    for (TWeakObjectPtr<APlayerController> player_controller : player_controllers) {
        AShooterPlayerController* shooter_pc =
            static_cast<AShooterPlayerController*>(player_controller.Get());
        if (shooter_pc)
            shooter_pc->ClientChatMessage(chat);
    }
}

void BroadcastIncoming(const std::string& source_server,
                       const std::string& player_name,
                       const std::string& tribe_name,
                       const std::string& message) {
    if (message.empty()) return;
    const std::wstring wserver(source_server.begin(), source_server.end());
    const std::wstring wname(player_name.begin(), player_name.end());
    const std::wstring wtribe(tribe_name.begin(), tribe_name.end());
    const std::wstring wmsg(message.begin(), message.end());

    const FString sender = FString(L"[") + wserver.c_str() + L"]";
    FString body;
    if (!tribe_name.empty()) {
        body = FString(L"[") + wtribe.c_str() + L"] " + wname.c_str() + L": " + wmsg.c_str();
    } else {
        body = wname.c_str() + FString(L": ") + wmsg.c_str();
    }
    BroadcastClusterChat(sender, body);
}

std::string GetTribeName(AShooterPlayerController* player) {
    if (!player) return "";
    if (auto* ps = static_cast<AShooterPlayerState*>(player->PlayerStateField())) {
        if (FTribeData* tribe = ps->MyTribeDataField()) {
            const FString& tname = tribe->TribeNameField();
            if (!tname.IsEmpty()) {
                const std::string out = SanitizeAscii(tname.ToString());
                if (!out.empty()) return out;
            }
        }
    }
    if (AShooterCharacter* ch = player->GetPlayerCharacter()) {
        const FString& tname = ch->TribeNameField();
        if (!tname.IsEmpty()) {
            const std::string out = SanitizeAscii(tname.ToString());
            if (!out.empty()) return out;
        }
    }
    return "";
}

bool IsMuted(const std::string& steam_id) {
    if (!g_db || steam_id.empty()) return false;
    std::string esc_id;
    if (!Escape(steam_id, esc_id)) return false;
    const std::string sql =
        "SELECT 1 FROM cross_server_chat_mutes WHERE steam_id = '" + esc_id +
        "' AND (muted_until IS NULL OR muted_until > NOW()) LIMIT 1";
    if (mysql_query(g_db, sql.c_str()) != 0) return false;
    MYSQL_RES* res = mysql_store_result(g_db);
    if (!res) return false;
    const bool muted = mysql_fetch_row(res) != nullptr;
    mysql_free_result(res);
    return muted;
}

bool RateLimited(const std::string& steam_id) {
    const int secs = RateLimitSeconds();
    if (secs <= 0 || steam_id.empty()) return false;
    const auto now = std::chrono::steady_clock::now();
    std::lock_guard<std::mutex> lock(g_rate_mutex);
    const auto it = g_rate_limit.find(steam_id);
    if (it != g_rate_limit.end()) {
        const auto elapsed = std::chrono::duration_cast<std::chrono::seconds>(
            now - it->second).count();
        if (elapsed < secs) return true;
    }
    g_rate_limit[steam_id] = now;
    return false;
}

bool PublishDb(const std::string& steam_id,
               const std::string& player_name,
               const std::string& tribe_name,
               const std::string& message) {
    std::string esc_server, esc_sid, esc_name, esc_tribe, esc_msg;
    if (!Escape(ServerId(), esc_server) ||
        !Escape(steam_id, esc_sid) ||
        !Escape(player_name, esc_name) ||
        !Escape(tribe_name, esc_tribe) ||
        !Escape(message, esc_msg))
        return false;

    const std::string sql =
        "INSERT INTO cross_server_chat (channel, source_server, steam_id, player_name, tribe_name, message) "
        "VALUES ('cluster', '" + esc_server + "', '" + esc_sid + "', '" +
        esc_name + "', '" + esc_tribe + "', '" + esc_msg + "')";
    return Exec(sql.c_str());
}

bool PublishWeb(const std::string& steam_id,
                const std::string& player_name,
                const std::string& tribe_name,
                const std::string& message) {
    const nlohmann::json body = {
        {"source_server", ServerId()},
        {"steam_id", steam_id},
        {"player_name", player_name},
        {"tribe_name", tribe_name},
        {"message", message},
        {"channel", "cluster"},
    };
    const std::string resp =
        CustomShop::HttpClient::PostJson("/api/chat/publish", body.dump());
    try {
        const auto json = nlohmann::json::parse(resp);
        return json.value("ok", false);
    } catch (...) {
        return false;
    }
}

bool Publish(const std::string& steam_id,
             const std::string& player_name,
             const std::string& tribe_name,
             const std::string& message) {
    if (UseWebApi()) {
        if (PublishWeb(steam_id, player_name, tribe_name, message)) return true;
        Log::GetLog()->warn("CrossChat: Web API publish failed — fallback MySQL");
    }
    return PublishDb(steam_id, player_name, tribe_name, message);
}

void LoadCursor() {
    g_last_id = 0;
    if (!g_db) return;
    std::string esc_server;
    if (!Escape(ServerId(), esc_server)) return;
    const std::string sql =
        "SELECT last_id FROM cross_server_chat_cursor WHERE server_id = '" +
        esc_server + "' LIMIT 1";
    if (mysql_query(g_db, sql.c_str()) != 0) return;
    MYSQL_RES* res = mysql_store_result(g_db);
    if (!res) return;
    if (MYSQL_ROW row = mysql_fetch_row(res)) {
        if (row[0]) {
            try { g_last_id = std::stoull(row[0]); }
            catch (...) { g_last_id = 0; }
        }
    }
    mysql_free_result(res);
}

void SaveCursor(uint64_t last_id) {
    if (!g_db) return;
    std::string esc_server;
    if (!Escape(ServerId(), esc_server)) return;
    const std::string sql =
        "INSERT INTO cross_server_chat_cursor (server_id, last_id) VALUES ('" +
        esc_server + "', " + std::to_string(last_id) +
        ") ON DUPLICATE KEY UPDATE last_id = VALUES(last_id)";
    Exec(sql.c_str());
}

void PollDb() {
    if (!g_db) return;
    const std::string sql =
        "SELECT id, source_server, player_name, tribe_name, message FROM cross_server_chat "
        "WHERE id > " + std::to_string(g_last_id) +
        " ORDER BY id ASC LIMIT 50";
    if (mysql_query(g_db, sql.c_str()) != 0) {
        Log::GetLog()->warn("CrossChat: poll failed: {}", mysql_error(g_db));
        return;
    }
    MYSQL_RES* res = mysql_store_result(g_db);
    if (!res) return;

    const std::string self = ServerId();
    uint64_t max_id = g_last_id;
    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res))) {
        if (!row[0] || !row[1] || !row[2] || !row[4]) continue;
        uint64_t id = 0;
        try { id = std::stoull(row[0]); } catch (...) { continue; }
        if (id > max_id) max_id = id;
        const std::string source = row[1];
        if (source == self) continue;
        const std::string tribe = row[3] ? row[3] : "";
        BroadcastIncoming(source, row[2], tribe, row[4]);
    }
    mysql_free_result(res);
    if (max_id > g_last_id) {
        g_last_id = max_id;
        SaveCursor(g_last_id);
    }
}

void PollWeb() {
    const std::string path =
        "/api/chat/poll?server=" + ServerId() + "&since=" + std::to_string(g_last_id);
    const std::string resp = CustomShop::HttpClient::Get(path);
    try {
        const auto json = nlohmann::json::parse(resp);
        if (!json.value("ok", false)) return;
        const auto& msgs = json.value("messages", nlohmann::json::array());
        if (!msgs.is_array()) return;
        const std::string self = ServerId();
        uint64_t max_id = g_last_id;
        for (const auto& m : msgs) {
            const uint64_t id = m.value("id", static_cast<uint64_t>(0));
            if (id > max_id) max_id = id;
            const std::string source = m.value("source_server", "");
            if (source.empty() || source == self) continue;
            BroadcastIncoming(source,
                              m.value("player_name", ""),
                              m.value("tribe_name", ""),
                              m.value("message", ""));
        }
        if (max_id > g_last_id) {
            g_last_id = max_id;
            SaveCursor(g_last_id);
        }
    } catch (const std::exception& e) {
        Log::GetLog()->debug("CrossChat: poll web parse error: {}", e.what());
    }
}

void MaybePurgeOld() {
    if (!g_db) return;
    if (++g_poll_ticks % 300 != 0) return;  // ~10 min @ 2s interval
    Exec("DELETE FROM cross_server_chat WHERE created_at < (NOW() - INTERVAL 7 DAY)");
}

void PollTick() {
    if (!Enabled()) return;
    if (ArkApi::GetApiUtils().GetStatus() != ArkApi::ServerStatus::Ready) return;
    if (UseWebApi())
        PollWeb();
    else
        PollDb();
    MaybePurgeOld();
}

bool HandleMessage(AShooterPlayerController* player, const std::string& raw_msg) {
    if (!Enabled() || !player || raw_msg.empty()) return false;

    const bool auto_capture = AutoCapture();
    std::string payload;

    if (auto_capture) {
        if (IgnoreCommands() && raw_msg[0] == '/')
            return false;
        payload = SanitizeAscii(raw_msg);
        if (payload.empty())
            return false;
    } else {
        const std::string cmd = CommandToken();
        if (raw_msg == cmd) {
            SendLocal(player, "Uso: " + cmd + " sua mensagem");
            return true;
        }
        const std::string prefix = cmd + " ";
        if (raw_msg.size() <= prefix.size() ||
            raw_msg.compare(0, prefix.size(), prefix) != 0)
            return false;

        payload = SanitizeAscii(raw_msg.substr(prefix.size()));
        if (payload.empty()) {
            SendLocal(player, "Mensagem vazia.");
            return true;
        }
    }

    if (static_cast<int>(payload.size()) > MaxMessageLength()) {
        payload.resize(static_cast<size_t>(MaxMessageLength()));
    }

    const std::string steam_id = CustomShop::Bridge::GetSteamId(player);
    if (steam_id.empty()) {
        if (!auto_capture)
            SendLocal(player, "SteamID indisponivel.");
        return !auto_capture;
    }
    if (IsMuted(steam_id)) {
        if (!auto_capture)
            SendLocal(player, "Voce esta silenciado no chat cluster.");
        return !auto_capture;
    }
    if (RateLimited(steam_id)) {
        if (!auto_capture)
            SendLocal(player, "Aguarde antes de enviar outra mensagem.");
        return !auto_capture;
    }

    const FString fname = ArkApi::GetApiUtils().GetSteamName(player);
    const std::string player_name = SanitizeAscii(fname.ToString());
    const std::string tribe_name = GetTribeName(player);
    if (!Publish(steam_id,
                 player_name.empty() ? steam_id : player_name,
                 tribe_name,
                 payload)) {
        if (!auto_capture) {
            SendLocal(player, "Falha ao enviar mensagem cluster.");
            return true;
        }
        return false;
    }

    if (!auto_capture) {
        SendLocal(player, "[Cluster] Voce: " + payload);
        return true;
    }
    return false;
}

bool OnChatMessage(AShooterPlayerController* player, FString* message,
                   EChatSendMode::Type mode, bool /*spam_check*/,
                   bool command_executed) {
    if (command_executed || !player || !message) return false;
    if (GlobalChatOnly() && mode != EChatSendMode::GlobalChat) return false;
    return HandleMessage(player, message->ToString());
}

void CmdCrossChat(APlayerController* pc, FString* cmd_str, bool) {
    auto* player = static_cast<AShooterPlayerController*>(pc);
    if (!player || !cmd_str) return;
    HandleMessage(player, cmd_str->ToString());
}

} // anonymous namespace

namespace CustomShop {
namespace CrossChat {

void SetDb(MYSQL* db) {
    g_db = db;
}

void Start() {
    if (!Enabled()) {
        Log::GetLog()->info("CrossChat: disabled in config.");
        return;
    }
    if (!g_db && !UseWebApi()) {
        Log::GetLog()->warn("CrossChat: enabled but MySQL unavailable.");
        return;
    }

    LoadCursor();

    const int interval = std::max(1, Cfg().value("PollIntervalSeconds", 2));
    ArkApi::GetCommands().AddOnChatMessageCallback("CustomShopCrossChat", &OnChatMessage);
    if (!AutoCapture())
        ArkApi::GetCommands().AddChatCommand(CommandToken().c_str(), &CmdCrossChat);

    API::Timer::Get().RecurringExecute(PollTick, interval, -1, false);

    Log::GetLog()->info(
        "CrossChat: started server='{}' auto={} cmd='{}' poll={}s web_api={}",
        ServerId(), AutoCapture() ? "yes" : "no", CommandToken(), interval,
        UseWebApi() ? "yes" : "no");
}

void Stop() {
    if (!Enabled()) return;
    ArkApi::GetCommands().RemoveOnChatMessageCallback("CustomShopCrossChat");
    if (!AutoCapture())
        ArkApi::GetCommands().RemoveChatCommand(CommandToken().c_str());
}

void OnConfigReload() {
    if (!Enabled()) return;
    LoadCursor();
    Log::GetLog()->info("CrossChat: config reloaded server='{}'", ServerId());
}

} // namespace CrossChat
} // namespace CustomShop
