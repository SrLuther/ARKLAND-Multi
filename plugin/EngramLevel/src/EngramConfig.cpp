#include "pch.h"
#include "EngramConfig.h"

namespace {

std::vector<std::string> ReadStringArray(const nlohmann::json& root, const char* key) {
    std::vector<std::string> out;
    if (!root.contains(key) || !root.at(key).is_array()) return out;
    for (const auto& item : root.at(key)) {
        if (!item.is_string()) continue;
        const std::string value = item.get<std::string>();
        if (!value.empty()) out.push_back(value);
    }
    return out;
}

} // namespace

namespace EngramLevel {

Config& Config::Get() {
    static Config instance;
    return instance;
}

void Config::Load() {
    const std::string path =
        ArkApi::Tools::GetCurrentDir() + "/ArkApi/Plugins/EngramLevel/config.json";

    enabled_ = true;
    suppress_auto_unlock_ = true;
    unlock_only_applied_level_ = true;
    unlock_non_tek_ = true;
    unlock_total_ = false;
    use_configured_engrams_ = false;
    catalog_buyout_points_ = kDefaultCatalogBuyoutPoints;
    engrams_.clear();
    extra_engrams_.clear();
    removed_engrams_.clear();

    std::ifstream file(path);
    if (!file.is_open()) {
        Log::GetLog()->warn(
            "EngramLevel: config.json ausente — defaults (auto-unlock suprimido, "
            "buyout {}). Crie {} e use EngramLevel.Reload",
            catalog_buyout_points_, path);
        return;
    }

    nlohmann::json full;
    try {
        file >> full;
    } catch (const nlohmann::json::exception& e) {
        throw std::runtime_error(std::string("config.json parse error: ") + e.what());
    }

    const nlohmann::json root = full.contains("EngramLevel") && full["EngramLevel"].is_object()
        ? full["EngramLevel"]
        : full;

    enabled_ = JsonBool(root, "Enabled", enabled_);
    suppress_auto_unlock_ = JsonBool(
        root, "SuppressAutoUnlockDuringLevelUp", suppress_auto_unlock_);
    unlock_only_applied_level_ = JsonBool(
        root, "UnlockOnlyAppliedLevel", unlock_only_applied_level_);
    unlock_non_tek_ = JsonBool(root, "UnlockNonTek", unlock_non_tek_);
    unlock_total_ = JsonBool(root, "UnlockTotal", unlock_total_);
    const int buyout = JsonInt(root, "CatalogBuyoutPoints", catalog_buyout_points_);
    catalog_buyout_points_ = buyout > 0 ? buyout : kDefaultCatalogBuyoutPoints;

    const bool engrams_key = root.contains("Engrams") && root.at("Engrams").is_array();
    engrams_ = engrams_key ? ReadStringArray(root, "Engrams") : std::vector<std::string>{};
    use_configured_engrams_ = engrams_key && !engrams_.empty();
    extra_engrams_ = ReadStringArray(root, "ExtraEngrams");
    removed_engrams_ = ReadStringArray(root, "RemovedEngrams");

    Log::GetLog()->info(
        "EngramLevel: enabled={} non_tek={} total={} engrams={} extra={} removed={} buyout={}",
        enabled_, unlock_non_tek_, unlock_total_,
        use_configured_engrams_ ? engrams_.size() : 0,
        extra_engrams_.size(), removed_engrams_.size(), catalog_buyout_points_);
}

} // namespace EngramLevel
