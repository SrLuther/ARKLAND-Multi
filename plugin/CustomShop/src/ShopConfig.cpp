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

    items_    = config_.value("Items",    nlohmann::json::object());
    kits_     = config_.value("Kits",     nlohmann::json::object());
    settings_ = config_.value("Settings", nlohmann::json::object());
    db_cfg_   = config_.value("Database", nlohmann::json::object());

    Log::GetLog()->info("ShopConfig: loaded ({} items, {} kits)",
                        items_.size(), kits_.size());
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

bool ShopConfig::DisableSell() const {
    return settings_.value("DisableSellButton", true);
}

bool ShopConfig::DisableTrade() const {
    return settings_.value("DisableTradeButton", true);
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
