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
    const nlohmann::json& Items()              const { return items_; }
    const nlohmann::json& Kits()               const { return kits_; }
    const nlohmann::json& Settings()           const { return settings_; }
    const nlohmann::json& TimedPointsReward()  const { return timed_points_; }

    int         StartingPoints()     const;
    std::string ShopName()           const;
    std::string UiKey()              const;
    std::string WebApiUrl()          const;
    std::string WebApiKey()          const;
    bool        DisableSell()        const;
    bool        DisableTrade()       const;

    // Cloud inventory (Nuvem)
    bool        CloudEnabled()                  const;
    int         CloudMaxItems()                 const;
    int         CloudCooldownSeconds()          const;
    bool        CloudRequireLicenseForDownload() const;
    std::string WebsiteUrl()                    const;

    // Dino delivery
    bool        DeliverDinosInCryopods() const;
    std::string CryoItemPath()           const;
    bool        CryoLimitedTime()        const;

    /** Logs detalhados de cryopod no Comercio + chat em /enviardebug e falhas de /enviar. */
    bool        MarketCryoDebug()        const;

    /** Minimo de dias de timer restante para /enviar ao Comercio (cryos permanentes ignoram). */
    float       MarketCryoMinDaysRemaining() const;

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
    nlohmann::json timed_points_;
};

} // namespace CustomShop
