#pragma once

#include "pch.h"

// ─────────────────────────────────────────────────────────────────
//  DinoDebug — logging ARKLAND-first para CustomDinoDeliver.
//  Ficheiro JSONL + ring buffer; eventos críticos via HTTP ingest
//  (sem MySQL no plugin) → tabela arkland_plugin_debug na web.
// ─────────────────────────────────────────────────────────────────

namespace CustomDinoDeliver {
namespace Debug {

enum class Level : int {
    Off   = 0,
    Error = 1,
    Warn  = 2,
    Info  = 3,
    Debug = 4,
    Trace = 5,
};

struct Fields {
    std::string steam_id;
    std::string server_id;
    std::string order_id;
    std::string correlation_id;
    nlohmann::json extra = nlohmann::json::object();
};

void Configure(const nlohmann::json& debug_cfg);
void Shutdown();

bool Enabled();
Level CurrentLevel();
const char* LevelName(Level level);
Level ParseLevel(const std::string& name);
std::string NewCorrelationId();

void Emit(Level level,
          const char* category,
          const Fields& fields,
          const std::string& message);

void Error(const char* category, const Fields& fields, const std::string& message);
void Warn (const char* category, const Fields& fields, const std::string& message);
void Info (const char* category, const Fields& fields, const std::string& message);
void LogDebug(const char* category, const Fields& fields, const std::string& message);
void LogTrace(const char* category, const Fields& fields, const std::string& message);

std::vector<std::string> RecentLines(size_t max_n = 50);
std::string StatusSummary();
std::string LogFilePath();

void SetEnabledRuntime(bool enabled);
void SetLevelRuntime(Level level);

/** Callback opcional para POST /api/plugin-debug/ingest (HttpClient). */
using IngestFn = void (*)(const std::string& json_body);
void SetIngestCallback(IngestFn fn);

} // namespace Debug
} // namespace CustomDinoDeliver
