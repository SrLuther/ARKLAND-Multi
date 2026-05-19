#pragma once

#include "pch.h"

// ─────────────────────────────────────────────────────────────────
//  ShopConfig — loads and exposes configs/config.json.
//
//  Expected file location (server):
//    <ServerRoot>/ArkApi/Plugins/CustomShop/config.json
// ─────────────────────────────────────────────────────────────────

namespace CustomShop {

class ShopConfig {
public:
    static ShopConfig& Get();

    // Reads or re-reads the config file from disk. Throws on parse error.
    void Load();

    // Convenience accessors
    const nlohmann::json& Items()    const { return items_; }
    const nlohmann::json& Kits()     const { return kits_; }
    const nlohmann::json& Settings() const { return settings_; }

    int         StartingPoints()     const;
    std::string ShopName()           const;
    std::string UiKey()              const;
    bool        DisableSell()        const;
    bool        DisableTrade()       const;

    // Database (MySQL)
    std::string DbHost()             const;
    int         DbPort()             const;
    std::string DbUser()             const;
    std::string DbPassword()         const;
    std::string DbDatabase()         const;

private:
    ShopConfig() = default;

    nlohmann::json config_;
    nlohmann::json items_;
    nlohmann::json kits_;
    nlohmann::json settings_;
    nlohmann::json db_cfg_;
};

} // namespace CustomShop
