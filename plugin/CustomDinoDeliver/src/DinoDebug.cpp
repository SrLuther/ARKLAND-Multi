#include "pch.h"
#include "DinoDebug.h"
#include "plugin_version.h"

#include <chrono>
#include <ctime>
#include <deque>
#include <iomanip>
#include <mutex>
#include <random>
#include <set>

namespace CustomDinoDeliver {
namespace Debug {
namespace {

std::mutex g_mu;
bool g_enabled = false;
Level g_level = Level::Info;
std::set<std::string> g_categories;
size_t g_ring_cap = 500;
size_t g_max_file_bytes = 10 * 1024 * 1024;
int g_max_files = 5;
bool g_http_persist = true;
Level g_http_min = Level::Warn;
std::set<std::string> g_http_categories;

std::deque<std::string> g_ring;
std::string g_log_dir;
std::string g_log_path;
std::ofstream g_file;
size_t g_file_bytes = 0;
IngestFn g_ingest = nullptr;

std::string ToLower(std::string s) {
    for (char& c : s) c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    return s;
}

std::set<std::string> ParseCategorySet(const nlohmann::json& arr) {
    std::set<std::string> out;
    if (!arr.is_array()) return out;
    for (const auto& v : arr) {
        if (!v.is_string()) continue;
        std::string s = v.get<std::string>();
        if (s.empty()) continue;
        if (s == "*") {
            out.clear();
            out.insert("*");
            return out;
        }
        out.insert(s);
    }
    return out;
}

bool CategoryAllowed(const std::set<std::string>& cats, const char* category) {
    if (cats.empty() || cats.count("*")) return true;
    return category && cats.count(category) > 0;
}

std::string IsoTimestamp() {
    using clock = std::chrono::system_clock;
    const auto now = clock::now();
    const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(
                        now.time_since_epoch()) %
                    1000;
    const std::time_t t = clock::to_time_t(now);
    std::tm tm{};
#ifdef _WIN32
    gmtime_s(&tm, &t);
#else
    gmtime_r(&t, &tm);
#endif
    std::ostringstream oss;
    oss << std::put_time(&tm, "%Y-%m-%dT%H:%M:%S") << '.'
        << std::setfill('0') << std::setw(3) << ms.count() << 'Z';
    return oss.str();
}

void EnsureLogDirUnlocked() {
    if (!g_log_dir.empty()) return;
    g_log_dir = ArkApi::Tools::GetCurrentDir() +
                "/ArkApi/Plugins/CustomDinoDeliver/logs";
    CreateDirectoryA(g_log_dir.c_str(), nullptr);
    g_log_path = g_log_dir + "/arkland_debug.log";
}

void RotateIfNeededUnlocked() {
    if (!g_file.is_open()) return;
    if (g_file_bytes < g_max_file_bytes) return;

    g_file.flush();
    g_file.close();

    for (int i = g_max_files - 1; i >= 1; --i) {
        const std::string src =
            g_log_dir + "/arkland_debug." + std::to_string(i) + ".log";
        const std::string dst =
            g_log_dir + "/arkland_debug." + std::to_string(i + 1) + ".log";
        if (i + 1 > g_max_files) {
            DeleteFileA(src.c_str());
        } else {
            MoveFileExA(src.c_str(), dst.c_str(), MOVEFILE_REPLACE_EXISTING);
        }
    }
    const std::string first = g_log_dir + "/arkland_debug.1.log";
    MoveFileExA(g_log_path.c_str(), first.c_str(), MOVEFILE_REPLACE_EXISTING);

    g_file.open(g_log_path, std::ios::app | std::ios::binary);
    g_file_bytes = 0;
}

void OpenFileUnlocked() {
    EnsureLogDirUnlocked();
    if (g_file.is_open()) return;
    g_file.open(g_log_path, std::ios::app | std::ios::binary);
    if (g_file.is_open()) {
        g_file.seekp(0, std::ios::end);
        const auto pos = g_file.tellp();
        g_file_bytes = pos >= 0 ? static_cast<size_t>(pos) : 0;
    }
}

} // namespace

const char* LevelName(Level level) {
    switch (level) {
    case Level::Off:   return "OFF";
    case Level::Error: return "ERROR";
    case Level::Warn:  return "WARN";
    case Level::Info:  return "INFO";
    case Level::Debug: return "DEBUG";
    case Level::Trace: return "TRACE";
    }
    return "INFO";
}

Level ParseLevel(const std::string& name) {
    const std::string s = ToLower(name);
    if (s == "off" || s == "0") return Level::Off;
    if (s == "error" || s == "err") return Level::Error;
    if (s == "warn" || s == "warning") return Level::Warn;
    if (s == "info") return Level::Info;
    if (s == "debug" || s == "dbg") return Level::Debug;
    if (s == "trace") return Level::Trace;
    return Level::Info;
}

void Configure(const nlohmann::json& debug_cfg) {
    std::lock_guard<std::mutex> lock(g_mu);
    g_enabled = debug_cfg.value("Enabled", false);
    g_level = ParseLevel(debug_cfg.value("Level", std::string("INFO")));
    g_categories = ParseCategorySet(debug_cfg.value("Categories", nlohmann::json::array({"*"})));
    g_ring_cap = static_cast<size_t>(
        std::max(50, debug_cfg.value("RingBufferSize", 500)));
    g_max_file_bytes = static_cast<size_t>(
        std::max(1024 * 1024, debug_cfg.value("MaxFileBytes", 10 * 1024 * 1024)));
    g_max_files = std::max(1, debug_cfg.value("MaxFiles", 5));
    g_http_persist = debug_cfg.value("HttpPersist", true);
    g_http_min = ParseLevel(debug_cfg.value("HttpMinLevel", std::string("WARN")));
    g_http_categories = ParseCategorySet(debug_cfg.value(
        "HttpCategories",
        nlohmann::json::array({"Deliver", "DinoLab", "Http", "SpawnExact"})));

    if (g_enabled) {
        OpenFileUnlocked();
        Log::GetLog()->info(
            "DinoDebug: enabled level={} file={} http_persist={}",
            LevelName(g_level), g_log_path, g_http_persist ? "yes" : "no");
    } else {
        if (g_file.is_open()) {
            g_file.flush();
            g_file.close();
        }
        Log::GetLog()->info("DinoDebug: disabled (produção — ligar Debug.Enabled=true)");
    }
}

void SetIngestCallback(IngestFn fn) {
    std::lock_guard<std::mutex> lock(g_mu);
    g_ingest = fn;
}

void Shutdown() {
    std::lock_guard<std::mutex> lock(g_mu);
    if (g_file.is_open()) {
        g_file.flush();
        g_file.close();
    }
    g_ingest = nullptr;
}

bool Enabled() {
    std::lock_guard<std::mutex> lock(g_mu);
    return g_enabled;
}

Level CurrentLevel() {
    std::lock_guard<std::mutex> lock(g_mu);
    return g_level;
}

std::string NewCorrelationId() {
    static thread_local std::mt19937_64 rng{
        std::random_device{}() ^
        (static_cast<uint64_t>(
             std::chrono::high_resolution_clock::now().time_since_epoch().count())
         << 1)};
    std::uniform_int_distribution<uint64_t> dist;
    const uint64_t a = dist(rng);
    const uint64_t b = dist(rng);
    std::ostringstream oss;
    oss << std::hex << std::setfill('0') << std::setw(16) << a << std::setw(16)
        << b;
    return oss.str();
}

void Emit(Level level,
          const char* category,
          const Fields& fields,
          const std::string& message) {
    if (level == Level::Off) return;

    std::string ingest_body;
    IngestFn ingest = nullptr;
    bool mirror_error = false;
    {
        std::lock_guard<std::mutex> lock(g_mu);
        if (!g_enabled) {
            if (level == Level::Error)
                Log::GetLog()->error("[{}] {}", category ? category : "?", message);
            return;
        }
        if (static_cast<int>(level) > static_cast<int>(g_level)) return;
        if (!CategoryAllowed(g_categories, category)) return;

        nlohmann::json line = {
            {"ts", IsoTimestamp()},
            {"plugin", "CustomDinoDeliver"},
            {"version", ARKLAND_PLUGIN_VERSION},
            {"level", LevelName(level)},
            {"category", category ? category : ""},
            {"message", message},
        };
        if (!fields.steam_id.empty()) line["steam_id"] = fields.steam_id;
        if (!fields.server_id.empty()) line["server_id"] = fields.server_id;
        if (!fields.order_id.empty()) line["order_id"] = fields.order_id;
        if (!fields.correlation_id.empty())
            line["correlation_id"] = fields.correlation_id;
        if (fields.extra.is_object() && !fields.extra.empty())
            line["fields"] = fields.extra;

        const std::string line_str = line.dump();
        g_ring.push_back(line_str);
        while (g_ring.size() > g_ring_cap) g_ring.pop_front();

        OpenFileUnlocked();
        if (g_file.is_open()) {
            RotateIfNeededUnlocked();
            g_file << line_str << '\n';
            g_file.flush();
            g_file_bytes += line_str.size() + 1;
        }

        if (g_http_persist && g_ingest &&
            static_cast<int>(level) >= static_cast<int>(g_http_min) &&
            CategoryAllowed(g_http_categories, category)) {
            nlohmann::json body = line;
            body["plugin"] = "CustomDinoDeliver";
            ingest_body = body.dump();
            ingest = g_ingest;
        }
        mirror_error = (level == Level::Error);
    }

    if (ingest && !ingest_body.empty()) {
        try {
            ingest(ingest_body);
        } catch (...) {
        }
    }
    if (mirror_error)
        Log::GetLog()->error("[{}] {}", category ? category : "?", message);
}

void Error(const char* category, const Fields& fields, const std::string& message) {
    Emit(Level::Error, category, fields, message);
}
void Warn(const char* category, const Fields& fields, const std::string& message) {
    Emit(Level::Warn, category, fields, message);
}
void Info(const char* category, const Fields& fields, const std::string& message) {
    Emit(Level::Info, category, fields, message);
}
void LogDebug(const char* category, const Fields& fields, const std::string& message) {
    Emit(Level::Debug, category, fields, message);
}
void LogTrace(const char* category, const Fields& fields, const std::string& message) {
    Emit(Level::Trace, category, fields, message);
}

std::vector<std::string> RecentLines(size_t max_n) {
    std::lock_guard<std::mutex> lock(g_mu);
    std::vector<std::string> out;
    if (max_n == 0 || g_ring.empty()) return out;
    const size_t start =
        g_ring.size() > max_n ? g_ring.size() - max_n : 0;
    for (size_t i = start; i < g_ring.size(); ++i)
        out.push_back(g_ring[i]);
    return out;
}

std::string StatusSummary() {
    std::lock_guard<std::mutex> lock(g_mu);
    std::ostringstream oss;
    oss << "DinoDebug enabled=" << (g_enabled ? "yes" : "no")
        << " level=" << LevelName(g_level)
        << " ring=" << g_ring.size() << "/" << g_ring_cap
        << " file=" << (g_log_path.empty() ? "(n/a)" : g_log_path)
        << " http_persist=" << (g_http_persist ? "on" : "off");
    return oss.str();
}

std::string LogFilePath() {
    std::lock_guard<std::mutex> lock(g_mu);
    return g_log_path;
}

void SetEnabledRuntime(bool enabled) {
    std::lock_guard<std::mutex> lock(g_mu);
    g_enabled = enabled;
    if (g_enabled) OpenFileUnlocked();
}

void SetLevelRuntime(Level level) {
    std::lock_guard<std::mutex> lock(g_mu);
    g_level = level;
}

} // namespace Debug
} // namespace CustomDinoDeliver
