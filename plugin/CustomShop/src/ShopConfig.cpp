#include "pch.h"
#include "ShopConfig.h"

namespace CustomShop {

ShopConfig& ShopConfig::Get() {
    static ShopConfig instance;
    return instance;
}

void ShopConfig::Load() {
    const std::string path =
        ArkApi::Tools::GetCurrentDir() +
        "/ArkApi/Plugins/CustomShop/config.json";

    std::ifstream file(path);
    if (!file.is_open())
        throw std::runtime_error("Cannot open config: " + path);

    try {
        file >> config_;
    } catch (const nlohmann::json::exception& e) {
        throw std::runtime_error(
            std::string("config.json parse error: ") + e.what());
    }

    items_         = config_.value("Items",             nlohmann::json::object());
    kits_          = config_.value("Kits",              nlohmann::json::object());
    settings_      = config_.value("Settings",          nlohmann::json::object());
    db_cfg_        = config_.value("Database",          nlohmann::json::object());
    timed_points_  = config_.value("TimedPointsReward", nlohmann::json::object());
    cross_chat_    = config_.value("CrossChat",         nlohmann::json::object());

    Log::GetLog()->info("ShopConfig: loaded ({} items, {} kits, DeliverDinosInCryopods={})",
                        items_.size(), kits_.size(),
                        settings_.value("DeliverDinosInCryopods", true));

    const bool tp_enabled = timed_points_.value("Enabled", false);
    const int tp_interval = timed_points_.value("Interval", 30);
    const auto& tp_groups = timed_points_.value("Groups", nlohmann::json::object());
    std::string grp_summary;
    for (const auto& [name, val] : tp_groups.items()) {
        const int amt = val.value("Amount", 0);
        if (amt <= 0) continue;
        if (!grp_summary.empty()) grp_summary += ", ";
        grp_summary += name + "=" + std::to_string(amt);
    }
    Log::GetLog()->info(
        "ShopConfig: TimedPointsReward enabled={} interval={}min groups=[{}]",
        tp_enabled ? "yes" : "no",
        tp_interval,
        grp_summary.empty() ? "(none)" : grp_summary);
}

int ShopConfig::StartingPoints() const {
    return settings_.value("StartingPoints", 0);
}

std::string ShopConfig::ShopName() const {
    return settings_.value("ShopName", "ARKLAND Shop");
}

std::string ShopConfig::UiKey() const {
    return settings_.value("UiKey", "F3");
}

std::string ShopConfig::WebApiUrl() const {
    return settings_.value("WebApiUrl", "http://127.0.0.1:5177");
}

std::string ShopConfig::WebApiKey() const {
    return settings_.value("WebApiKey", "");
}

bool ShopConfig::DisableSell() const {
    return settings_.value("DisableSellButton", true);
}

bool ShopConfig::DisableTrade() const {
    return settings_.value("DisableTradeButton", true);
}

bool ShopConfig::CloudEnabled() const {
    return settings_.value("CloudInventoryEnabled", true);
}

int ShopConfig::CloudMaxItems() const {
    return settings_.value("CloudMaxItems", 250);
}

int ShopConfig::CloudCooldownSeconds() const {
    return settings_.value("CloudCooldownSeconds", 30);
}

bool ShopConfig::CloudRequireLicenseForDownload() const {
    return settings_.value("CloudRequireLicenseForDownload", false);
}

std::string ShopConfig::WebsiteUrl() const {
    return settings_.value("WebsiteUrl", "");
}

bool ShopConfig::DeliverDinosInCryopods() const {
    return settings_.value("DeliverDinosInCryopods", true);
}

std::string ShopConfig::CryoItemPath() const {
    return settings_.value(
        "CryoItemPath",
        "Blueprint'/Game/Extinction/CoreBlueprints/Weapons/"
        "PrimalItem_WeaponEmptyCryopod.PrimalItem_WeaponEmptyCryopod'");
}

bool ShopConfig::CryoLimitedTime() const {
    return settings_.value("CryoLimitedTime", false);
}

bool ShopConfig::MarketCryoDebug() const {
    return settings_.value("MarketCryoDebug", false);
}

float ShopConfig::MarketCryoMinDaysRemaining() const {
    return settings_.value("MarketCryoMinDaysRemaining", 20.f);
}

bool ShopConfig::MarketCryoRequireMinDays() const {
    return settings_.value("MarketCryoRequireMinDays", false);
}

int ShopConfig::EngramasCommandPrice() const {
    return settings_.value("EngramasCommandPrice", 5000);
}

bool ShopConfig::MarketDeliverAsSpawn() const {
    return settings_.value("MarketDeliverAsSpawn", true);
}

std::string ShopConfig::MarketSpawnBonusSoulTrapBlueprint() const {
    return settings_.value(
        "MarketSpawnBonusSoulTrapBlueprint",
        "Blueprint'/Game/Mods/DinoStorage2/SoulTraps_DS.SoulTraps_DS'");
}

std::string ShopConfig::DbHost() const {
    return db_cfg_.value("Host", "127.0.0.1");
}
int ShopConfig::DbPort() const {
    return db_cfg_.value("Port", 3306);
}
std::string ShopConfig::DbUser() const {
    return db_cfg_.value("User", "arkland");
}
std::string ShopConfig::DbPassword() const {
    return db_cfg_.value("Password", "");
}
std::string ShopConfig::DbDatabase() const {
    return db_cfg_.value("Database", "arkland_shop");
}

} // namespace CustomShop
