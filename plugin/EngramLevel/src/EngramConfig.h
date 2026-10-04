#pragma once

#include "pch.h"
#include "EngramGrant.h"

namespace EngramLevel {

class Config {
public:
    static Config& Get();
    void Load();

    bool Enabled() const { return enabled_; }
    bool SuppressAutoUnlock() const { return suppress_auto_unlock_; }
    bool UnlockOnlyAppliedLevel() const { return unlock_only_applied_level_; }
    bool UnlockNonTek() const { return unlock_non_tek_; }
    bool UnlockTotal() const { return unlock_total_; }
    int CatalogBuyoutPoints() const { return catalog_buyout_points_; }
    // true só quando Engrams veio preenchido. Array vazio mantém a base.
    bool UseConfiguredEngramList() const { return use_configured_engrams_; }
    const std::vector<std::string>& Engrams() const { return engrams_; }
    const std::vector<std::string>& ExtraEngrams() const { return extra_engrams_; }
    const std::vector<std::string>& RemovedEngrams() const { return removed_engrams_; }

private:
    Config() = default;

    bool enabled_ = true;
    bool suppress_auto_unlock_ = true;
    bool unlock_only_applied_level_ = true;
    bool unlock_non_tek_ = true;
    bool unlock_total_ = false;
    bool use_configured_engrams_ = false;
    int catalog_buyout_points_ = kDefaultCatalogBuyoutPoints;
    std::vector<std::string> engrams_;
    std::vector<std::string> extra_engrams_;
    std::vector<std::string> removed_engrams_;
};

} // namespace EngramLevel
