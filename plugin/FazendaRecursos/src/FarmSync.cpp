#include "FarmSync.h"
#include "FarmConfig.h"
#include "FarmState.h"

namespace {
struct WebSettings {
    std::string url;
    std::string api_key;
};

class SyncWorker {
public:
    static SyncWorker& Get() { static SyncWorker worker; return worker; }

    void Start() {
        std::lock_guard<std::mutex> lock(mutex_);
        if (thread_.joinable()) return;
        stop_ = false;
        thread_ = std::thread([this] { Run(); });
    }

    void Stop() {
        {
            std::lock_guard<std::mutex> lock(mutex_);
            stop_ = true;
        }
        wake_.notify_all();
        if (thread_.joinable()) thread_.join();
    }

    void Queue(std::string steam_id) {
        if (steam_id.empty()) return;
        {
            std::lock_guard<std::mutex> lock(mutex_);
            queued_.insert(std::move(steam_id));
        }
        wake_.notify_one();
    }

private:
    std::mutex mutex_;
    std::condition_variable wake_;
    std::set<std::string> queued_;
    std::thread thread_;
    bool stop_ = false;

    static WebSettings ReadWebSettings() {
        const std::string path = ArkApi::Tools::GetCurrentDir() +
            "/ArkApi/Plugins/CustomShop/config.json";
        std::ifstream in(path);
        if (!in) throw std::runtime_error("CustomShop/config.json não encontrado");
        nlohmann::json config;
        in >> config;
        const auto settings = config.value("Settings", nlohmann::json::object());
        WebSettings result;
        result.url = FRJsonString(settings, "WebApiUrl");
        result.api_key = FRJsonString(settings, "WebApiKey");
        if (result.url.empty() || result.api_key.empty())
            throw std::runtime_error("Settings.WebApiUrl/WebApiKey não configurados no CustomShop");
        return result;
    }

    static std::wstring Utf8Wide(const std::string& value) {
        if (value.empty()) return {};
        const int size = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS,
            value.data(), static_cast<int>(value.size()), nullptr, 0);
        if (size <= 0) return {};
        std::wstring out(static_cast<size_t>(size), L'\0');
        if (!MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, value.data(),
                static_cast<int>(value.size()), out.data(), size)) return {};
        return out;
    }

    static bool PostJson(const WebSettings& settings, const std::string& path,
                         const std::string& body, DWORD& status) {
        auto url = Utf8Wide(settings.url);
        auto api_key = Utf8Wide(settings.api_key);
        if (url.empty() || api_key.empty()) return false;
        URL_COMPONENTS parts{};
        parts.dwStructSize = sizeof(parts);
        parts.dwSchemeLength = static_cast<DWORD>(-1);
        parts.dwHostNameLength = static_cast<DWORD>(-1);
        parts.dwUrlPathLength = static_cast<DWORD>(-1);
        parts.dwExtraInfoLength = static_cast<DWORD>(-1);
        if (!WinHttpCrackUrl(url.c_str(), 0, 0, &parts)) return false;
        const std::wstring host(parts.lpszHostName, parts.dwHostNameLength);
        std::wstring base_path(parts.lpszUrlPath, parts.dwUrlPathLength);
        if (!base_path.empty() && base_path.back() == L'/') base_path.pop_back();
        const auto wpath = Utf8Wide(path);
        if (wpath.empty()) return false;
        const std::wstring full_path = base_path + wpath;
        HINTERNET session = WinHttpOpen(L"FazendaRecursos/0.1.5",
            WINHTTP_ACCESS_TYPE_DEFAULT_PROXY, WINHTTP_NO_PROXY_NAME,
            WINHTTP_NO_PROXY_BYPASS, 0);
        if (!session) return false;
        WinHttpSetTimeouts(session, 3000, 3000, 5000, 5000);
        HINTERNET connection = WinHttpConnect(session, host.c_str(), parts.nPort, 0);
        if (!connection) { WinHttpCloseHandle(session); return false; }
        const DWORD flags = parts.nScheme == INTERNET_SCHEME_HTTPS ? WINHTTP_FLAG_SECURE : 0;
        HINTERNET request = WinHttpOpenRequest(connection, L"POST", full_path.c_str(),
            nullptr, WINHTTP_NO_REFERER, WINHTTP_DEFAULT_ACCEPT_TYPES, flags);
        if (!request) {
            WinHttpCloseHandle(connection); WinHttpCloseHandle(session); return false;
        }
        const std::wstring headers = L"Content-Type: application/json\r\nX-API-Key: " + api_key;
        BOOL ok = WinHttpSendRequest(request, headers.c_str(), static_cast<DWORD>(headers.size()),
            const_cast<char*>(body.data()), static_cast<DWORD>(body.size()),
            static_cast<DWORD>(body.size()), 0);
        if (ok) ok = WinHttpReceiveResponse(request, nullptr);
        if (ok) {
            DWORD status_size = sizeof(status);
            ok = WinHttpQueryHeaders(request,
                WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER,
                WINHTTP_HEADER_NAME_BY_INDEX, &status, &status_size,
                WINHTTP_NO_HEADER_INDEX);
        }
        WinHttpCloseHandle(request);
        WinHttpCloseHandle(connection);
        WinHttpCloseHandle(session);
        return ok != FALSE;
    }

    static bool SyncPlayer(const std::string& steam_id) {
        try {
            const auto settings = ReadWebSettings();
            auto& config = FazendaRecursos::FarmConfig::Get();
            const auto definitions = config.ResourcesSnapshot();
            const int64_t now = static_cast<int64_t>(std::chrono::duration_cast<std::chrono::seconds>(
                std::chrono::system_clock::now().time_since_epoch()).count());
            auto& state = FazendaRecursos::FarmState::Get();
            state.Accrue(steam_id, definitions, now);
            if (!state.Save())
                Log::GetLog()->warn("Fazenda sync: estado não persistido antes do envio (steam={})", steam_id);
            const auto player = state.GetPlayer(steam_id);
            nlohmann::json stock = nlohmann::json::object();
            for (const auto& def : definitions) {
                if (!def.enabled) continue;
                const auto it = player.resources.find(def.id);
                stock[def.id] = it == player.resources.end() ? int64_t{0} : it->second.stock;
            }
            const auto body = nlohmann::json{
                {"steam_id", steam_id}, {"server_id", config.ServerId()},
                {"plugin_version", "0.1.5-test"}, {"stock", std::move(stock)}
            }.dump();
            DWORD status = 0;
            if (!PostJson(settings, "/api/plugin/farm/sync", body, status)) {
                Log::GetLog()->warn("Fazenda sync: transporte HTTP falhou (steam={})", steam_id);
                return false;
            }
            if (status < 200 || status >= 300) {
                Log::GetLog()->warn("Fazenda sync: API respondeu HTTP {} (steam={})", status, steam_id);
                return false;
            }
            Log::GetLog()->info("Fazenda sync: estoque enviado à WebStore (steam={}, recursos={}, http={})",
                steam_id, stock.size(), status);
            return true;
        } catch (const std::exception& e) {
            Log::GetLog()->warn("Fazenda sync: não foi possível sincronizar steam={} ({})", steam_id, e.what());
            return false;
        }
    }

    void SyncKnownPlayers() {
        for (const auto& id : FazendaRecursos::FarmState::Get().PlayerIds()) {
            {
                std::lock_guard<std::mutex> lock(mutex_);
                if (stop_) return;
            }
            SyncPlayer(id);
        }
    }

    void Run() {
        auto next_full_sync = std::chrono::steady_clock::now();
        bool first_sync = true;
        for (;;) {
            std::set<std::string> queued;
            bool full_sync = false;
            {
                std::unique_lock<std::mutex> lock(mutex_);
                const auto interval = std::chrono::seconds(
                    FazendaRecursos::FarmConfig::Get().SyncIntervalSeconds());
                const bool notified = wake_.wait_for(lock, interval,
                    [this] { return stop_ || !queued_.empty(); });
                if (stop_) return;
                queued.swap(queued_);
                const auto now = std::chrono::steady_clock::now();
                full_sync = first_sync || !notified || now >= next_full_sync;
                first_sync = false;
                if (full_sync) next_full_sync = now + interval;
            }
            if (full_sync) SyncKnownPlayers();
            for (const auto& id : queued) SyncPlayer(id);
        }
    }
};
}

namespace FazendaRecursos::FarmSync {
void Start() { SyncWorker::Get().Start(); }
void Stop() { SyncWorker::Get().Stop(); }
void QueuePlayer(const std::string& steam_id) { SyncWorker::Get().Queue(steam_id); }
}
