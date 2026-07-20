#pragma once

#include "pch.h"

namespace ArkPlayer {

struct GroupSettings {
    int priority = 99;
    bool wipe_enabled = true;
    int wipe_price = 0;
    bool wipe_require_mindwipe = false;
    bool mission_enabled = true;
    int mission_price = 0;
    bool loot_enabled = true;
    int loot_price = 0;
    int loot_range_foundations = 15;
    bool rename_enabled = true;
    int rename_price = 0;
    std::vector<std::string> rename_blacklist;
    bool suicide_enabled = true;
    int suicide_price = 0;
    bool suicide_allow_ko = false;
    bool suicide_allow_handcuffs = false;
    bool suicide_allow_sitting = false;
    bool suicide_allow_riding = false;
    bool suicide_allow_picked = false;
    bool suicide_allow_grappled = false;
    bool suicide_allow_mind_control = false;
};

struct CmdMeta {
    bool enabled = true;
    std::string chat_command;
    std::string description;
    int cooldown_seconds = 0;
    std::vector<std::string> master_blacklist;
};

class PlayerConfig {
public:
    static PlayerConfig& Get();

    void Load();

    bool EverythingFree() const { return everything_free_; }
    std::string SenderName() const { return sender_name_; }
    std::string Msg(const char* key, const std::string& fallback = "") const;
    std::string FormatMsg(const char* key, int value, const std::string& fallback = "") const;

    const CmdMeta& WipeMeta() const { return wipe_meta_; }
    const CmdMeta& MissionMeta() const { return mission_meta_; }
    const CmdMeta& LootMeta() const { return loot_meta_; }
    const CmdMeta& RenameMeta() const { return rename_meta_; }
    const CmdMeta& SuicideMeta() const { return suicide_meta_; }

    GroupSettings ResolveGroup(uint64_t steam_id) const;

private:
    PlayerConfig() = default;

    void ParseGroup(const nlohmann::json& j, GroupSettings& out) const;
    CmdMeta ParseCmdMeta(const nlohmann::json& j, const char* default_cmd) const;

    nlohmann::json root_;
    nlohmann::json messages_;
    bool everything_free_ = false;
    std::string sender_name_ = "ARKLAND SERVER";
    bool stacking_ = false;
    GroupSettings default_group_;
    std::map<std::string, GroupSettings> groups_;
    CmdMeta wipe_meta_;
    CmdMeta mission_meta_;
    CmdMeta loot_meta_;
    CmdMeta rename_meta_;
    CmdMeta suicide_meta_;
};

} // namespace ArkPlayer
