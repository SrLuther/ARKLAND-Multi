#pragma once

#include "pch.h"

// ─────────────────────────────────────────────────────────────────
//  ShopDebug — logging ARKLAND-first (ficheiro JSONL + ring buffer
//  + MySQL opcional). Independente do Log::GetLog() do ArkApi.
//
//  Config (top-level "Debug" em config.json):
//    Enabled, Level, Categories, RingBufferSize, MaxFileBytes,
//    MaxFiles, MySqlPersist, MySqlMinLevel, MySqlCategories
// ─────────────────────────────────────────────────────────────────

namespace CustomShop {
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

/** Aplica config.Debug (ou defaults se objecto vazio). Idempotente. */
void Configure(const nlohmann::json& debug_cfg);

/** Liga a ligação MySQL partilhada (ShopPoints) para persistência crítica. */
void SetDb(MYSQL* db);

void Shutdown();

bool Enabled();
Level CurrentLevel();
const char* LevelName(Level level);
Level ParseLevel(const std::string& name);

/** UUID hex simples para correlacionar um fluxo (login, deliver, sync). */
std::string NewCorrelationId();

/**
 * Emite um evento estruturado.
 * - Sempre (se Enabled + nível + categoria): ring buffer + ficheiro JSONL.
 * - ERROR: também espelha para Log::GetLog()->error (ArkApi).
 * - Críticos (MySqlPersist): INSERT em arkland_plugin_debug.
 */
void Emit(Level level,
          const char* category,
          const Fields& fields,
          const std::string& message);

void Error(const char* category, const Fields& fields, const std::string& message);
void Warn (const char* category, const Fields& fields, const std::string& message);
void Info (const char* category, const Fields& fields, const std::string& message);
void LogDebug(const char* category, const Fields& fields, const std::string& message);
void LogTrace(const char* category, const Fields& fields, const std::string& message);

/** Últimas N linhas do ring buffer (mais recentes no fim). */
std::vector<std::string> RecentLines(size_t max_n = 50);

/** Resumo para /shopdebug e Shop.DebugLevel. */
std::string StatusSummary();

/** Caminho do log actual (vazio se nunca configurado). */
std::string LogFilePath();

/** Override runtime (Shop.DebugLevel) — persiste só em memória até Reload. */
void SetEnabledRuntime(bool enabled);
void SetLevelRuntime(Level level);

} // namespace Debug
} // namespace CustomShop
