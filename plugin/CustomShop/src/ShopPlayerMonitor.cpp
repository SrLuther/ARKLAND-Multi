#include "pch.h"
#include "ShopPlayerMonitor.h"
#include "HttpClient.h"
#include "ShopBridge.h"
#include "ShopConfig.h"

#include <condition_variable>
#include <deque>
#include <atomic>
#include <chrono>
#include <functional>
#include <fstream>
#include <sstream>
#include <thread>
#include <unordered_map>

namespace CustomShop::PlayerMonitor {
namespace {

struct PendingEvent {
    std::string event;
    std::string body;
};

std::mutex g_mutex;
std::condition_variable g_cv;
std::deque<PendingEvent> g_queue;
std::string g_inflight_body;
std::unordered_map<std::string, std::string> g_sessions;
std::thread g_worker;
bool g_running = false;
bool g_stopping = false;
constexpr size_t kMaxQueuedEvents = 2000;

std::string QueuePath() {
    const auto& config_path = ShopConfig::Get().LocalConfigPath();
    return config_path.empty() ? "CustomShop_PlayerMonitor.queue" : config_path + ".playermonitor.queue";
}

void PersistQueueLocked() {
    std::ofstream out(QueuePath(), std::ios::out | std::ios::trunc | std::ios::binary);
    if (!out) {
        Log::GetLog()->error("PlayerMonitor: nao foi possivel persistir a fila local");
        return;
    }
    if (!g_inflight_body.empty()) out << g_inflight_body << '\n';
    for (const auto& item : g_queue) out << item.body << '\n';
}

std::string ServerId() {
    try {
        const auto& settings = ShopConfig::Get().Settings();
        std::string id = settings.value("ServerId", "");
        if (!id.empty() && id != "unknown" && id != "server") return id;
        id = ShopConfig::Get().CrossChat().value("ServerId", "");
        if (!id.empty() && id != "unknown" && id != "server") return id;
    } catch (...) {
    }
    try {
        auto* gm = ArkApi::GetApiUtils().GetShooterGameMode();
        if (gm) {
            FString map_name;
            gm->GetMapName(&map_name);
            std::string id = map_name.ToString();
            for (char& ch : id) {
                const unsigned char c = static_cast<unsigned char>(ch);
                if (!(std::isalnum(c) || ch == '.' || ch == '_' || ch == '-')) ch = '_';
            }
            if (!id.empty()) return id.substr(0, 80);
        }
    } catch (...) {
    }
    return "unknown";
}

std::string NewSessionId(const std::string& steam_id) {
    static std::atomic<uint64_t> sequence{0};
    const auto server_hash = static_cast<uint32_t>(std::hash<std::string>{}(ServerId()));
    return steam_id + "-" + std::to_string(GetTickCount64()) + "-" +
           std::to_string(server_hash) + "-" + std::to_string(++sequence);
}

std::string CharacterId(AShooterPlayerController* player) {
    if (!player) return "";
    try {
        const uint64_t id = ArkApi::GetApiUtils().GetPlayerID(player);
        if (id && id != static_cast<uint64_t>(-1)) return std::to_string(id);
    } catch (...) {
    }
    try {
        const uint64_t id = player->GetLinkedPlayerID();
        if (id && id != static_cast<uint64_t>(-1)) return std::to_string(id);
    } catch (...) {
    }
    return "";
}

nlohmann::json BuildPayload(AShooterPlayerController* player,
                            const std::string& event,
                            const std::string& session_id) {
    const std::string steam_id = Bridge::GetSteamId(player);
    std::string player_name;
    std::string tribe_id;
    std::string tribe_name;
    try {
        if (player) {
            auto* character = player->GetPlayerCharacter();
            if (character) {
                player_name = character->PlayerNameField().ToString();
                tribe_name = character->TribeNameField().ToString();
            }
            auto* state = static_cast<AShooterPlayerState*>(player->PlayerStateField());
            if (state) {
                const int id = state->GetTribeId();
                if (id > 0) tribe_id = std::to_string(id);
                if (tribe_id.empty()) {
                    const int team = state->TargetingTeamField();
                    if (team > 0) tribe_id = std::to_string(team);
                }
            }
            if (tribe_id.empty()) {
                const int team = player->TargetingTeamField();
                if (team > 0) tribe_id = std::to_string(team);
            }
        }
    } catch (...) {
        // Partial profile data is valid; later heartbeats refresh it.
    }

    return {
        {"event", event},
        {"session_id", session_id},
        {"server_id", ServerId()},
        {"steam_id", steam_id},
        {"player_name", player_name},
        {"character_id", CharacterId(player)},
        {"tribe_id", tribe_id},
        {"tribe_name", tribe_name},
    };
}

bool ResponseOk(const std::string& response) {
    try {
        return nlohmann::json::parse(response).value("ok", false);
    } catch (...) {
        return false;
    }
}

void Enqueue(const std::string& event, const nlohmann::json& body) {
    if (HttpClient::g_web_url.empty() || HttpClient::g_api_key.empty()) return;
    std::lock_guard<std::mutex> lock(g_mutex);
    if (!g_running || g_stopping) return;
    if (g_queue.size() >= kMaxQueuedEvents) {
        Log::GetLog()->error("PlayerMonitor: fila persistente atingiu o limite; evento novo descartado");
        return;
    }
    g_queue.push_back({event, body.dump()});
    PersistQueueLocked();
    g_cv.notify_one();
}

void Worker() {
    for (;;) {
        PendingEvent item;
        {
            std::unique_lock<std::mutex> lock(g_mutex);
            g_cv.wait(lock, [] { return g_stopping || !g_queue.empty(); });
            if (g_stopping && g_queue.empty()) break;
            item = std::move(g_queue.front());
            g_queue.pop_front();
            g_inflight_body = item.body;
        }

        std::string response;
        for (int attempt = 0; attempt < 3; ++attempt) {
            response = HttpClient::PostJson("/api/moderation/player-session", item.body);
            if (ResponseOk(response)) break;
            if (attempt < 2) std::this_thread::sleep_for(std::chrono::seconds(1 << attempt));
        }
        if (!ResponseOk(response)) {
            std::unique_lock<std::mutex> lock(g_mutex);
            g_inflight_body.clear();
            g_queue.push_front(std::move(item));
            Log::GetLog()->warn("PlayerMonitor: envio de evento '{}' nao confirmado; mantido para nova tentativa", g_queue.front().event);
            PersistQueueLocked();
            g_cv.wait_for(lock, std::chrono::seconds(30), [] { return g_stopping; });
        } else {
            std::lock_guard<std::mutex> lock(g_mutex);
            g_inflight_body.clear();
            PersistQueueLocked();
        }
    }
}

} // namespace

void Start() {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_running) return;
    g_stopping = false;
    g_inflight_body.clear();
    {
        std::ifstream in(QueuePath(), std::ios::in | std::ios::binary);
        std::string line;
        while (g_queue.size() < kMaxQueuedEvents && std::getline(in, line)) {
            try {
                auto body = nlohmann::json::parse(line);
                g_queue.push_back({body.value("event", std::string("retry")), line});
            } catch (...) {
                Log::GetLog()->warn("PlayerMonitor: linha invalida ignorada na fila persistente");
            }
        }
    }
    g_running = true;
    g_worker = std::thread(Worker);
}

void Stop() {
    {
        std::lock_guard<std::mutex> lock(g_mutex);
        if (!g_running) return;
        g_stopping = true;
    }
    g_cv.notify_all();
    if (g_worker.joinable()) g_worker.join();
    std::lock_guard<std::mutex> lock(g_mutex);
    g_running = false;
    g_sessions.clear();
}

void Record(AShooterPlayerController* player, const std::string& event) {
    if (!player || (event != "connect" && event != "heartbeat" && event != "disconnect")) return;
    const std::string steam_id = Bridge::GetSteamId(player);
    if (steam_id.empty()) return;

    std::string session_id;
    bool started_here = false;
    {
        std::lock_guard<std::mutex> lock(g_mutex);
        auto found = g_sessions.find(steam_id);
        if (event == "connect" || found == g_sessions.end()) {
            session_id = NewSessionId(steam_id);
            g_sessions[steam_id] = session_id;
            started_here = true;
        } else {
            session_id = found->second;
        }
        if (event == "disconnect") g_sessions.erase(steam_id);
    }
    if (started_here && event != "connect")
        Enqueue("connect", BuildPayload(player, "connect", session_id));
    Enqueue(event, BuildPayload(player, event, session_id));
}

void RecordDisconnect(AController* controller) {
    if (!controller) return;
    auto* player = static_cast<AShooterPlayerController*>(controller);
    if (Bridge::GetSteamId(player).empty()) return;
    Record(player, "disconnect");
}

void HeartbeatOnlinePlayers() {
    try {
        if (ArkApi::GetApiUtils().GetStatus() != ArkApi::ServerStatus::Ready) return;
        const auto& controllers = ArkApi::GetApiUtils().GetWorld()->PlayerControllerListField();
        for (TWeakObjectPtr<APlayerController> weak : controllers) {
            auto* player = static_cast<AShooterPlayerController*>(weak.Get());
            if (player) Record(player, "heartbeat");
        }
    } catch (const std::exception& e) {
        Log::GetLog()->warn("PlayerMonitor: heartbeat falhou: {}", e.what());
    }
}

} // namespace CustomShop::PlayerMonitor
