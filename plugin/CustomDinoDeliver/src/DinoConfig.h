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

private:
    DinoConfig() = default;
    nlohmann::json config_;
};

} // namespace CustomDinoDeliver
