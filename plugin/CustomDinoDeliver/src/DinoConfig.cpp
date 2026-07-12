#include "pch.h"
#include "DinoConfig.h"
#include "DinoDebug.h"

namespace CustomDinoDeliver {

DinoConfig& DinoConfig::Get() {
    static DinoConfig instance;
    return instance;
}

void DinoConfig::Load() {
    const std::string path =
        ArkApi::Tools::GetCurrentDir() +
        "/ArkApi/Plugins/CustomDinoDeliver/config.json";

    std::ifstream file(path);
    if (!file.is_open())
        throw std::runtime_error("Cannot open config: " + path);

    try {
        file >> config_;
    } catch (const nlohmann::json::exception& e) {
        throw std::runtime_error(std::string("config.json parse error: ") + e.what());
    }

    debug_cfg_ = config_.value("Debug", nlohmann::json::object());
    if (!config_.contains("Debug")) {
        debug_cfg_ = {
            {"Enabled", false},
            {"Level", "INFO"},
            {"Categories", nlohmann::json::array({"*"})},
            {"RingBufferSize", 500},
            {"MaxFileBytes", 10485760},
            {"MaxFiles", 5},
            {"HttpPersist", true},
            {"HttpMinLevel", "WARN"},
            {"HttpCategories", nlohmann::json::array(
                {"Deliver", "DinoLab", "Http", "SpawnExact"})}
        };
    }
    Debug::Configure(debug_cfg_);

    Log::GetLog()->info(
        "DinoConfig: loaded WebApiUrl={} poll={}s ground_fallback={} use_spawn_exact={}",
        WebApiUrl(), PollIntervalSeconds(), GroundFallbackOnFullInventory(),
        UseSpawnExact());
}

std::string DinoConfig::WebApiUrl() const {
    if (config_.contains("WebApiUrl"))
        return config_.value("WebApiUrl", std::string("http://127.0.0.1:5177"));
    return config_.value("WebStoreUrl", std::string("http://127.0.0.1:5177"));
}

std::string DinoConfig::WebApiKey() const {
    if (config_.contains("WebApiKey"))
        return config_.value("WebApiKey", "");
    return config_.value("ApiKey", "");
}

int DinoConfig::PollIntervalSeconds() const {
    return std::max(15, config_.value("PollIntervalSeconds", 60));
}

bool DinoConfig::GroundFallbackOnFullInventory() const {
    return config_.value("GroundFallbackOnFullInventory", true);
}

bool DinoConfig::UseSpawnExact() const {
    return config_.value("UseSpawnExact", false);
}

std::string DinoConfig::CryoItemPath() const {
    return config_.value("CryoItemPath", "");
}

} // namespace CustomDinoDeliver
