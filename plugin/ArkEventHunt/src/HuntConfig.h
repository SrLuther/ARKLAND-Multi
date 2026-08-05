#pragma once

#include "pch.h"

namespace ArkEventHunt {

class HuntConfig {
public:
    static HuntConfig& Get();
    void Load();

    bool Enabled() const { return enabled_; }
    std::string WebApiUrl() const;
    std::string WebApiKey() const;
    std::string ServerId() const { return server_id_; }
    std::string SenderName() const;
    std::string Msg(const char* key, const std::string& fallback = "") const;

    const std::vector<std::string>& WeaponWhitelist() const {
        return weapon_whitelist_;
    }

    float MinAllowedWeaponDamageRatio() const {
        return min_allowed_weapon_damage_ratio_;
    }
    bool ForbidTorpor() const { return forbid_torpor_; }
    bool OfficialWeaponsOnly() const { return official_weapons_only_; }
    const std::vector<std::string>& OfficialWeaponCatalog() const {
        return official_weapon_catalog_;
    }

    bool SpikeEnabled() const { return spike_enabled_; }
    int SpikeDefaultLevel() const { return spike_default_level_; }
    std::string SpikeDefaultBlueprint() const { return spike_default_bp_; }
    const std::vector<std::string>& SpikeWeaponWhitelist() const {
        return spike_weapon_whitelist_.empty() ? weapon_whitelist_
                                              : spike_weapon_whitelist_;
    }

    bool ModeAEnabled() const { return enabled_ && mode_a_enabled_; }
    bool ModeBEnabled() const { return enabled_ && mode_b_enabled_; }
    const std::vector<std::string>& AdminGroups() const { return admin_groups_; }
    int TtlTickSeconds() const { return ttl_tick_seconds_; }
    bool AllowPersonalTamesDefault() const {
        return allow_personal_tames_default_;
    }

private:
    HuntConfig() = default;

    nlohmann::json root_;
    nlohmann::json messages_;
    std::string sender_name_ = "ARKLAND EVENT";
    std::string server_id_;
    bool enabled_ = true;
    bool mode_a_enabled_ = true;
    bool mode_b_enabled_ = true;
    bool spike_enabled_ = true;
    int spike_default_level_ = 150;
    std::string spike_default_bp_;
    std::vector<std::string> weapon_whitelist_;
    std::vector<std::string> spike_weapon_whitelist_;
    std::vector<std::string> admin_groups_;
    float min_allowed_weapon_damage_ratio_ = 0.80f;
    bool forbid_torpor_ = true;
    bool official_weapons_only_ = true;
    bool allow_personal_tames_default_ = false;
    int ttl_tick_seconds_ = 5;
    std::vector<std::string> official_weapon_catalog_;
};

} // namespace ArkEventHunt
