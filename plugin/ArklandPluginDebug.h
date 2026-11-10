#pragma once

// Mirrors ArkApi plugin logger output to the ARKLAND admin log feed.
// Uploads run on a worker thread; each event also has a local JSONL copy for
// diagnosis when the site cannot be reached.
#include <API/ARK/Ark.h>
#include <Logger/spdlog/sinks/base_sink.h>
#include <Windows.h>
#include <winhttp.h>
#include <json.hpp>

#include <condition_variable>
#include <algorithm>
#include <chrono>
#include <ctime>
#include <fstream>
#include <iomanip>
#include <memory>
#include <mutex>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

namespace ArklandPluginDebug {

struct Settings {
    std::string plugin;
    std::string version;
    std::string api_url;
    std::string api_key;
    std::string server_id;
    bool write_local_jsonl = true;
};

inline std::string ToUtf8(const std::wstring& value) {
    if (value.empty()) return {};
    const int size = WideCharToMultiByte(CP_UTF8, 0, value.data(),
        static_cast<int>(value.size()), nullptr, 0, nullptr, nullptr);
    if (size <= 0) return {};
    std::string out(static_cast<size_t>(size), '\0');
    WideCharToMultiByte(CP_UTF8, 0, value.data(), static_cast<int>(value.size()),
        out.data(), size, nullptr, nullptr);
    return out;
}

inline std::wstring ToWide(const std::string& value) {
    if (value.empty()) return {};
    const int size = MultiByteToWideChar(CP_UTF8, 0, value.data(),
        static_cast<int>(value.size()), nullptr, 0);
    if (size <= 0) return std::wstring(value.begin(), value.end());
    std::wstring out(static_cast<size_t>(size), L'\0');
    MultiByteToWideChar(CP_UTF8, 0, value.data(), static_cast<int>(value.size()),
        out.data(), size);
    return out;
}

inline std::string LevelName(spdlog::level::level_enum level) {
    switch (level) {
    case spdlog::level::trace: return "TRACE";
    case spdlog::level::debug: return "DEBUG";
    case spdlog::level::info: return "INFO";
    case spdlog::level::warn: return "WARN";
    case spdlog::level::err: return "ERROR";
    case spdlog::level::critical: return "CRITICAL";
    default: return "INFO";
    }
}

inline std::string TimestampUtc(const std::chrono::system_clock::time_point& tp) {
    const std::time_t raw = std::chrono::system_clock::to_time_t(tp);
    std::tm utc{};
    gmtime_s(&utc, &raw);
    std::ostringstream out;
    out << std::put_time(&utc, "%Y-%m-%dT%H:%M:%SZ");
    return out.str();
}

inline std::string ExtractValue(const std::string& message,
                                const std::string& key) {
    auto position = message.find(key);
    if (position == std::string::npos) return {};
    position += key.size();
    while (position < message.size() &&
           (message[position] == ' ' || message[position] == '=' ||
            message[position] == ':' || message[position] == '\'' ||
            message[position] == '"')) ++position;
    const auto start = position;
    while (position < message.size()) {
        const char ch = message[position];
        if (!((ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') ||
              (ch >= '0' && ch <= '9') || ch == '-' || ch == '_' || ch == '.')) break;
        ++position;
    }
    return message.substr(start, position - start);
}

class Runtime {
public:
    static Runtime& Get() {
        static Runtime instance;
        return instance;
    }

    void Configure(Settings settings) {
        std::lock_guard<std::mutex> lock(mu_);
        if (started_) return;
        settings_ = std::move(settings);
        if (settings_.plugin.empty() || settings_.api_url.empty() ||
            settings_.api_key.empty()) return;

        if (settings_.write_local_jsonl) {
            log_dir_ = ArkApi::Tools::GetCurrentDir() + "/ArkApi/Plugins/" +
                settings_.plugin + "/logs";
            CreateDirectoryA((ArkApi::Tools::GetCurrentDir() + "/ArkApi/Plugins").c_str(), nullptr);
            CreateDirectoryA((ArkApi::Tools::GetCurrentDir() + "/ArkApi/Plugins/" + settings_.plugin).c_str(), nullptr);
            CreateDirectoryA(log_dir_.c_str(), nullptr);
            log_file_ = log_dir_ + "/arkland_debug.log";
        }
        if (log_dir_.empty()) {
            log_dir_ = ArkApi::Tools::GetCurrentDir() + "/ArkApi/Plugins/" +
                settings_.plugin + "/logs";
            CreateDirectoryA((ArkApi::Tools::GetCurrentDir() + "/ArkApi/Plugins").c_str(), nullptr);
            CreateDirectoryA((ArkApi::Tools::GetCurrentDir() + "/ArkApi/Plugins/" + settings_.plugin).c_str(), nullptr);
            CreateDirectoryA(log_dir_.c_str(), nullptr);
        }
        spool_file_ = log_dir_ + "/arkland_debug.pending.jsonl";
        offset_file_ = log_dir_ + "/arkland_debug.pending.offset";
        {
            std::ifstream offset(offset_file_);
            if (offset) offset >> spool_offset_;
        }

        auto previous = Log::GetLog();
        if (!previous) return;
        auto sinks = previous->sinks();
        sink_ = std::make_shared<LogSink>(*this);
        sinks.push_back(sink_);
        auto replacement = std::make_shared<spdlog::logger>(
            previous->name(), sinks.begin(), sinks.end());
        replacement->set_pattern("%D %R [%n][%l] %v");
        replacement->set_level(spdlog::level::trace);
        replacement->flush_on(spdlog::level::info);
        Log::GetLog() = replacement;
        started_ = true;
        worker_ = std::thread([this] { Worker(); });
        // Resume any records persisted by a previous process immediately,
        // even if no new ArkApi log message arrives after startup.
        cv_.notify_one();
    }

    void Shutdown() {
        {
            std::lock_guard<std::mutex> lock(mu_);
            if (!started_) return;
            stopping_ = true;
            stop_deadline_ = std::chrono::steady_clock::now() + std::chrono::seconds(5);
        }
        cv_.notify_all();
        if (worker_.joinable()) worker_.join();
        std::lock_guard<std::mutex> lock(mu_);
        started_ = false;
        sink_.reset();
    }

    void Record(const spdlog::details::log_msg& msg) {
        const std::string message = msg.raw.str();
        if (message.empty()) return;
        const auto now = std::chrono::system_clock::now();
        std::string category = "Runtime";
        const auto colon = message.find(':');
        if (colon > 0 && colon < 32) {
            category = message.substr(0, colon);
            while (!category.empty() && category.back() == ' ') category.pop_back();
        }
        nlohmann::json fields = {
            {"logger", msg.logger_name ? *msg.logger_name : settings_.plugin},
            {"thread_id", static_cast<unsigned long long>(msg.thread_id)},
            {"timestamp_utc", TimestampUtc(now)},
            {"raw_message", message},
        };
        std::string steam_id = ExtractValue(message, "steam_id");
        if (steam_id.empty()) steam_id = ExtractValue(message, "steam=");
        if (steam_id.empty()) steam_id = ExtractValue(message, "SteamID");
        const std::string order_id = ExtractValue(message, "order_id");
        const std::string correlation_id = ExtractValue(message, "correlation_id");
        if (!steam_id.empty()) fields["steam_id"] = steam_id;
        if (!order_id.empty()) fields["order_id"] = order_id;
        if (!correlation_id.empty()) fields["correlation_id"] = correlation_id;
        nlohmann::json event = {
            {"plugin", settings_.plugin},
            {"version", settings_.version},
            {"level", LevelName(msg.level)},
            {"category", category.substr(0, 32)},
            {"message", message.substr(0, 4000)},
            {"fields", std::move(fields)},
        };
        if (!steam_id.empty()) event["steam_id"] = steam_id;
        if (!order_id.empty()) event["order_id"] = order_id;
        if (!correlation_id.empty()) event["correlation_id"] = correlation_id;
        if (!settings_.server_id.empty()) event["server_id"] = settings_.server_id;
        const std::string serialized = event.dump();
        if (settings_.write_local_jsonl) WriteLocal(serialized);
        WriteSpool(serialized);
        cv_.notify_one();
    }

private:
    class LogSink final : public spdlog::sinks::base_sink<std::mutex> {
    public:
        explicit LogSink(Runtime& owner) : owner_(owner) {}
    protected:
        void _sink_it(const spdlog::details::log_msg& msg) override {
            owner_.Record(msg);
        }
        void _flush() override {}
    private:
        Runtime& owner_;
    };

    Runtime() = default;
    ~Runtime() { Shutdown(); }
    Runtime(const Runtime&) = delete;
    Runtime& operator=(const Runtime&) = delete;

    void WriteLocal(const std::string& line) {
        std::lock_guard<std::mutex> lock(file_mu_);
        if (log_file_.empty()) return;
        WIN32_FILE_ATTRIBUTE_DATA attrs{};
        if (GetFileAttributesExA(log_file_.c_str(), GetFileExInfoStandard, &attrs)) {
            const ULONGLONG size = (static_cast<ULONGLONG>(attrs.nFileSizeHigh) << 32) |
                attrs.nFileSizeLow;
            if (size >= 10ULL * 1024 * 1024) {
                for (int i = 4; i >= 1; --i) {
                    const std::string from = log_dir_ + "/arkland_debug." + std::to_string(i) + ".log";
                    const std::string to = log_dir_ + "/arkland_debug." + std::to_string(i + 1) + ".log";
                    if (i == 4) DeleteFileA(to.c_str());
                    MoveFileExA(from.c_str(), to.c_str(), MOVEFILE_REPLACE_EXISTING);
                }
                MoveFileExA(log_file_.c_str(), (log_dir_ + "/arkland_debug.1.log").c_str(), MOVEFILE_REPLACE_EXISTING);
            }
        }
        std::ofstream out(log_file_, std::ios::binary | std::ios::app);
        if (out) out << line << '\n';
    }

    void WriteSpool(const std::string& line) {
        std::lock_guard<std::mutex> lock(file_mu_);
        std::ofstream out(spool_file_, std::ios::binary | std::ios::app);
        if (out) out << line << '\n';
    }

    std::vector<std::string> ReadPendingBatch(std::streamoff& next_offset) {
        std::lock_guard<std::mutex> lock(file_mu_);
        std::ifstream in(spool_file_, std::ios::binary);
        if (!in) return {};
        in.seekg(spool_offset_);
        std::vector<std::string> batch;
        std::string line;
        next_offset = spool_offset_;
        while (batch.size() < 100 && std::getline(in, line)) {
            next_offset += static_cast<std::streamoff>(line.size() + 1);
            if (!line.empty()) batch.push_back(line);
        }
        if (batch.empty()) return {};
        return batch;
    }

    void CommitPending(std::streamoff next_offset) {
        std::lock_guard<std::mutex> lock(file_mu_);
        spool_offset_ = next_offset;
        if (spool_offset_ >= 2 * 1024 * 1024) {
            std::ifstream in(spool_file_, std::ios::binary);
            in.seekg(spool_offset_);
            const std::string temp = spool_file_ + ".tmp";
            std::ofstream out(temp, std::ios::binary | std::ios::trunc);
            out << in.rdbuf();
            out.close();
            in.close();
            MoveFileExA(temp.c_str(), spool_file_.c_str(), MOVEFILE_REPLACE_EXISTING);
            spool_offset_ = 0;
        }
        std::ofstream offset(offset_file_, std::ios::trunc);
        if (offset) offset << spool_offset_;
    }

    bool Send(const std::vector<std::string>& events) {
        nlohmann::json batch = nlohmann::json::array();
        try {
            for (const auto& event : events) batch.push_back(nlohmann::json::parse(event));
        } catch (...) {
            return false;
        }
        const std::string body = batch.dump();
        std::wstring url = ToWide(settings_.api_url);
        URL_COMPONENTS parts{};
        parts.dwStructSize = sizeof(parts);
        wchar_t host[256]{};
        wchar_t path[2048]{};
        parts.lpszHostName = host;
        parts.dwHostNameLength = static_cast<DWORD>(sizeof(host) / sizeof(host[0]));
        parts.lpszUrlPath = path;
        parts.dwUrlPathLength = static_cast<DWORD>(sizeof(path) / sizeof(path[0]));
        if (!WinHttpCrackUrl(url.c_str(), 0, 0, &parts)) return false;
        const bool secure = parts.nScheme == INTERNET_SCHEME_HTTPS;
        HINTERNET session = WinHttpOpen(L"ARKLAND-PluginLog/1.0",
            WINHTTP_ACCESS_TYPE_DEFAULT_PROXY, WINHTTP_NO_PROXY_NAME,
            WINHTTP_NO_PROXY_BYPASS, 0);
        if (!session) return false;
        WinHttpSetTimeouts(session, 5000, 5000, 8000, 8000);
        HINTERNET connection = WinHttpConnect(session, host, parts.nPort, 0);
        std::wstring base_path(path, parts.dwUrlPathLength);
        while (!base_path.empty() && base_path.back() == L'/') base_path.pop_back();
        const std::wstring endpoint = base_path + L"/api/plugin-debug/ingest";
        HINTERNET request = connection ? WinHttpOpenRequest(connection, L"POST",
            endpoint.c_str(), nullptr, WINHTTP_NO_REFERER,
            WINHTTP_DEFAULT_ACCEPT_TYPES, secure ? WINHTTP_FLAG_SECURE : 0) : nullptr;
        bool ok = false;
        if (request) {
            const std::wstring headers = L"Content-Type: application/json\r\nX-API-Key: " +
                ToWide(settings_.api_key) + L"\r\n";
            if (WinHttpSendRequest(request, headers.c_str(),
                    static_cast<DWORD>(headers.size()),
                    const_cast<char*>(body.data()), static_cast<DWORD>(body.size()),
                    static_cast<DWORD>(body.size()), 0) && WinHttpReceiveResponse(request, nullptr)) {
                DWORD status = 0, bytes = sizeof(status);
                ok = WinHttpQueryHeaders(request, WINHTTP_QUERY_STATUS_CODE |
                    WINHTTP_QUERY_FLAG_NUMBER, WINHTTP_HEADER_NAME_BY_INDEX,
                    &status, &bytes, WINHTTP_NO_HEADER_INDEX) && status >= 200 && status < 300;
            }
            WinHttpCloseHandle(request);
        }
        if (connection) WinHttpCloseHandle(connection);
        WinHttpCloseHandle(session);
        return ok;
    }

    void Worker() {
        for (;;) {
            std::streamoff next_offset = 0;
            const auto batch = ReadPendingBatch(next_offset);
            if (batch.empty()) {
                std::unique_lock<std::mutex> lock(mu_);
                if (stopping_) return;
                cv_.wait(lock);
                continue;
            }
            if (Send(batch)) {
                CommitPending(next_offset);
                continue;
            }
            {
                std::unique_lock<std::mutex> lock(mu_);
                if (stopping_) {
                    const auto remaining = std::chrono::duration_cast<std::chrono::milliseconds>(
                        stop_deadline_ - std::chrono::steady_clock::now());
                    if (remaining.count() <= 0) return;
                    cv_.wait_for(lock, std::min<std::chrono::milliseconds>(
                        remaining, std::chrono::milliseconds(500)));
                    if (std::chrono::steady_clock::now() >= stop_deadline_) return;
                } else {
                    cv_.wait_for(lock, std::chrono::seconds(10));
                }
            }
        }
    }

    std::mutex mu_;
    std::mutex file_mu_;
    std::condition_variable cv_;
    Settings settings_;
    std::thread worker_;
    std::shared_ptr<LogSink> sink_;
    std::string log_dir_;
    std::string log_file_;
    std::string spool_file_;
    std::string offset_file_;
    std::streamoff spool_offset_ = 0;
    bool started_ = false;
    bool stopping_ = false;
    std::chrono::steady_clock::time_point stop_deadline_{};
};

inline nlohmann::json ReadCustomShopConfig() {
    const std::string path = ArkApi::Tools::GetCurrentDir() +
        "/ArkApi/Plugins/CustomShop/config.json";
    std::ifstream input(path);
    nlohmann::json config = nlohmann::json::object();
    if (input) {
        try { input >> config; } catch (...) { return nlohmann::json::object(); }
    }
    return config;
}

inline Settings SettingsFromCustomShop(const std::string& plugin,
                                       const std::string& version,
                                       bool write_local_jsonl = true) {
    const auto config = ReadCustomShopConfig();
    const auto settings = config.value("Settings", nlohmann::json::object());
    const auto cross_chat = config.value("CrossChat", nlohmann::json::object());
    Settings out;
    out.plugin = plugin;
    out.version = version;
    out.api_url = settings.value("WebApiUrl", std::string{});
    out.api_key = settings.value("WebApiKey", std::string{});
    out.server_id = settings.value("ServerId",
        cross_chat.value("ServerId", std::string{}));
    out.write_local_jsonl = write_local_jsonl;
    return out;
}

inline void Configure(Settings settings) {
    Runtime::Get().Configure(std::move(settings));
}

inline void ConfigureFromCustomShop(const std::string& plugin,
                                    const std::string& version,
                                    bool write_local_jsonl = true) {
    Configure(SettingsFromCustomShop(plugin, version, write_local_jsonl));
}

inline void Shutdown() { Runtime::Get().Shutdown(); }

} // namespace ArklandPluginDebug
