#include "pch.h"
#include "HuntConfig.h"
#include "HuntHttpClient.h"

namespace ArkEventHunt {

namespace {

void ReadStringArray(const nlohmann::json& parent,
                     const char* key,
                     std::vector<std::string>& out) {
    out.clear();
    if (!parent.contains(key) || !parent[key].is_array()) return;
    for (const auto& w : parent[key]) {
        if (!w.is_string()) continue;
        const std::string s = w.get<std::string>();
        if (!s.empty()) out.push_back(s);
    }
}

void ClampRatio(float& r) {
    if (r < 0.f) r = 0.f;
    if (r > 1.f) r = 1.f;
}

// Starter catalog — official ASE weapon item / projectile substrings.
// Source of truth for OfficialWeaponsOnly; expand via config.json.
const std::vector<std::string>& BuiltinOfficialCatalog() {
    static const std::vector<std::string> k = {
        // Melee
        "PrimalItem_WeaponStoneHatchet",
        "PrimalItem_WeaponMetalHatchet",
        "PrimalItem_WeaponStonePick",
        "PrimalItem_WeaponMetalPick",
        "PrimalItem_WeaponSpear",
        "PrimalItem_WeaponPike",
        "PrimalItem_WeaponSword",
        "PrimalItem_WeaponElectronicBinoculars",
        "WeapSword",
        "WeapPike",
        "WeapSpear",
        "WeapClub",
        "PrimalItem_WeaponMachinedClub",
        "WeapBaseSword",
        // Bows / arrows
        "PrimalItem_WeaponBow",
        "PrimalItem_WeaponCompoundBow",
        "PrimalItem_WeaponCrossbow",
        "WeapBow",
        "WeapCompoundBow",
        "WeapCrossbow",
        "PrimalItemAmmo_ArrowStone",
        "PrimalItemAmmo_ArrowTranq",
        "PrimalItemAmmo_ArrowFlame",
        "PrimalItemAmmo_CompoundBowArrow",
        "PrimalItemAmmo_ArrowMetal",
        // Guns
        "PrimalItem_WeaponGun",
        "PrimalItem_WeaponRifle",
        "PrimalItem_WeaponMachinedPistol",
        "PrimalItem_WeaponMachinedShotgun",
        "PrimalItem_WeaponMachinedSniper",
        "PrimalItem_WeaponMachinedRifle",
        "PrimalItem_WeaponSimplePistol",
        "PrimalItem_WeaponShotgun",
        "PrimalItem_WeaponOneShotRifle",
        "PrimalItem_WeaponProd",
        "WeapGun",
        "WeapRifle",
        "WeapShotgun",
        "WeapMachinedShotgun",
        "WeapMachinedPistol",
        "WeapMachinedSniper",
        "WeapMachinedRifle",
        "WeapSimplePistol",
        "WeapOneShotRifle",
        "WeapProd",
        "PrimalItemAmmo_SimpleBullet",
        "PrimalItemAmmo_SimpleRifleBullet",
        "PrimalItemAmmo_SimpleShotgunBullet",
        "PrimalItemAmmo_AdvancedBullet",
        "PrimalItemAmmo_AdvancedRifleBullet",
        "PrimalItemAmmo_AdvancedSniperBullet",
        "PrimalItemAmmo_TranqDart",
        "PrimalItemAmmo_RefinedTranqDart",
        // Grenades / explosives (vanilla)
        "PrimalItem_WeaponGrenade",
        "PrimalItem_WeaponClusterGrenade",
        "PrimalItem_WeaponSmokeGrenade",
        "PrimalItem_WeaponPoisonGrenade",
        "PrimalItem_WeaponC4",
        "WeapGrenade",
        "WeapC4",
        // Tek (official)
        "PrimalItem_WeaponTekRifle",
        "PrimalItem_WeaponTekPistol",
        "PrimalItem_WeaponTekSword",
        "PrimalItem_WeaponTekGrenade",
        "WeapTekRifle",
        "WeapTekPistol",
        "WeapTekSword",
        // DLC common
        "PrimalItem_WeaponHarpoon",
        "WeapHarpoon",
        "PrimalItem_WeaponBoomerang",
        "WeapBoomerang",
        "PrimalItem_WeaponWhip",
        "WeapWhip",
        "PrimalItem_WeaponClimbPick",
        "PrimalItem_WeaponScout",
        "PrimalItem_WeaponMinigun",
        "WeapMinigun",
        "PrimalItem_WeaponRocketLauncher",
        "WeapRocketLauncher",
        "PrimalItemAmmo_Rocket",
        "PrimalItem_WeaponFlamethrower",
        "WeapFlamethrower",
        "PrimalItem_WeaponRadioactiveLanternCharge",
    };
    return k;
}

} // anonymous

HuntConfig& HuntConfig::Get() {
    static HuntConfig instance;
    return instance;
}

void HuntConfig::Load() {
    const std::string path =
        ArkApi::Tools::GetCurrentDir() +
        "/ArkApi/Plugins/ArkEventHunt/config.json";

    nlohmann::json full = nlohmann::json::object();
    std::ifstream file(path);
    if (!file.is_open()) {
        Log::GetLog()->warn(
            "ArkEventHunt: config.json ausente — defaults embutidos ({})", path);
    } else {
        try {
            file >> full;
        } catch (const nlohmann::json::exception& e) {
            throw std::runtime_error(
                std::string("config.json parse error: ") + e.what());
        }
    }

    root_ = full.contains("ArkEventHunt") ? full["ArkEventHunt"] : full;
    if (!root_.is_object())
        root_ = nlohmann::json::object();

    enabled_ = JsonBool(root_, "Enabled", true);
    sender_name_ = JsonStr(root_, "SenderNameInChat", "ARKLAND EVENT");
    server_id_ = JsonStr(root_, "ServerId", "");
    messages_ = root_.value("Messages", nlohmann::json::object());

    ReadStringArray(root_, "WeaponWhitelist", weapon_whitelist_);
    ReadStringArray(root_, "OfficialWeaponCatalog", official_weapon_catalog_);
    if (official_weapon_catalog_.empty())
        official_weapon_catalog_ = BuiltinOfficialCatalog();

    min_allowed_weapon_damage_ratio_ = JsonFloat(
        root_, "MinAllowedWeaponDamageRatio", 0.80f);
    ClampRatio(min_allowed_weapon_damage_ratio_);
    forbid_torpor_ = JsonBool(root_, "ForbidTorpor", true);
    official_weapons_only_ = JsonBool(root_, "OfficialWeaponsOnly", true);

    const auto mode_a = root_.value("ModeA", nlohmann::json::object());
    mode_a_enabled_ = JsonBool(mode_a, "Enabled", true);
    if (mode_a.contains("MinAllowedWeaponDamageRatio")) {
        min_allowed_weapon_damage_ratio_ = JsonFloat(
            mode_a, "MinAllowedWeaponDamageRatio",
            min_allowed_weapon_damage_ratio_);
        ClampRatio(min_allowed_weapon_damage_ratio_);
    }
    if (mode_a.contains("ForbidTorpor"))
        forbid_torpor_ = JsonBool(mode_a, "ForbidTorpor", forbid_torpor_);
    if (mode_a.contains("OfficialWeaponsOnly"))
        official_weapons_only_ =
            JsonBool(mode_a, "OfficialWeaponsOnly", official_weapons_only_);

    const auto mode_b = root_.value("ModeB", nlohmann::json::object());
    mode_b_enabled_ = JsonBool(mode_b, "Enabled", true);
    allow_personal_tames_default_ =
        JsonBool(mode_b, "AllowPersonalTamesDefault", false);
    ttl_tick_seconds_ = JsonInt(mode_b, "TtlTickSeconds", 5);
    if (ttl_tick_seconds_ < 1) ttl_tick_seconds_ = 1;
    ReadStringArray(mode_b, "AdminGroups", admin_groups_);
    if (admin_groups_.empty())
        ReadStringArray(root_, "AdminGroups", admin_groups_);
    if (admin_groups_.empty())
        admin_groups_ = {"Admins"};

    const auto spike = root_.value("Spike", nlohmann::json::object());
    spike_enabled_ = JsonBool(spike, "Enabled", true);
    spike_default_level_ = JsonInt(spike, "DefaultLevel", 150);
    spike_default_bp_ = JsonStr(
        spike, "DefaultBlueprint",
        "Blueprint'/Game/PrimalEarth/Dinos/Dodo/Dodo_Character_BP.Dodo_Character_BP'");
    ReadStringArray(spike, "WeaponWhitelist", spike_weapon_whitelist_);

    HttpClient::Configure(WebApiUrl(), WebApiKey());

    Log::GetLog()->info(
        "ArkEventHunt: config loaded (enabled={}, modeA={}, modeB={}, spike={}, "
        "whitelist={}, officialCatalog={}, minWeaponRatio={:.2f}, "
        "forbidTorpor={}, officialOnly={}, adminGroups={}, api={})",
        enabled_, mode_a_enabled_, mode_b_enabled_, spike_enabled_,
        weapon_whitelist_.size(), official_weapon_catalog_.size(),
        min_allowed_weapon_damage_ratio_, forbid_torpor_,
        official_weapons_only_, admin_groups_.size(), WebApiUrl());
}

std::string HuntConfig::WebApiUrl() const {
    if (root_.contains("WebApiUrl"))
        return JsonStr(root_, "WebApiUrl", "http://127.0.0.1:5177");
    return JsonStr(root_, "WebStoreUrl", "http://127.0.0.1:5177");
}

std::string HuntConfig::WebApiKey() const {
    if (root_.contains("WebApiKey"))
        return JsonStr(root_, "WebApiKey", "");
    return JsonStr(root_, "ApiKey", "");
}

std::string HuntConfig::SenderName() const { return sender_name_; }

std::string HuntConfig::Msg(const char* key, const std::string& fallback) const {
    if (messages_.contains(key) && messages_[key].is_string())
        return messages_[key].get<std::string>();
    return fallback;
}

} // namespace ArkEventHunt
