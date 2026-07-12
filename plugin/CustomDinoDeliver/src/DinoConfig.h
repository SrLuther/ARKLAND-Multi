#pragma once

#include "pch.h"

namespace CustomDinoDeliver {

class DinoConfig {
public:
    static DinoConfig& Get();
    void Load();

    std::string WebApiUrl() const;
    std::string WebApiKey() const;
    int PollIntervalSeconds() const;
    bool GroundFallbackOnFullInventory() const;
    bool UseSpawnExact() const;
    std::string CryoItemPath() const;
    const nlohmann::json& DebugCfg() const { return debug_cfg_; }

private:
    DinoConfig() = default;
    nlohmann::json config_;
    nlohmann::json debug_cfg_;
};

} // namespace CustomDinoDeliver
