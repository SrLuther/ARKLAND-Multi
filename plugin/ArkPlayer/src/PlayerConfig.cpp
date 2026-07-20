#include "pch.h"
#include "PlayerConfig.h"
#include "PlayerPerms.h"

namespace ArkPlayer {

PlayerConfig& PlayerConfig::Get() {
    static PlayerConfig instance;
    return instance;
}

void PlayerConfig::ParseGroup(const nlohmann::json& j, GroupSettings& out) const {
    if (!j.is_object()) return;
    out.priority = JsonInt(j, "Priority", out.priority);
    out.wipe_enabled = JsonBool(j, "PlayerCharacterWipeEnabled", out.wipe_enabled);
    out.wipe_price = JsonInt(j, "PlayerCharacterWipePrice", out.wipe_price);
    out.wipe_require_mindwipe = JsonBool(j, "PlayerCharacterWipeRequireMindwipe", out.wipe_require_mindwipe);
    out.mission_enabled = JsonBool(j, "PlayerCompleteMissionEnabled", out.mission_enabled);
    out.mission_price = JsonInt(j, "PlayerCompleteMissionPrice", out.mission_price);
    out.loot_enabled = JsonBool(j, "PlayerGetDeathBagsEnabled", out.loot_enabled);
    out.loot_price = JsonInt(j, "PlayerGetDeathBagsPrice", out.loot_price);
    out.loot_range_foundations = JsonInt(j, "PlayerGetDeathBagsRangeFoundations", out.loot_range_foundations);
    out.rename_enabled = JsonBool(j, "PlayerRenameEnabled", out.rename_enabled);
    out.rename_price = JsonInt(j, "PlayerRenamePrice", out.rename_price);
    if (j.contains("PlayerRenameBlacklist") && j["PlayerRenameBlacklist"].is_array()) {
        out.rename_blacklist.clear();
        for (const auto& w : j["PlayerRenameBlacklist"]) {
            if (w.is_string()) {
                const std::string s = w.get<std::string>();
                if (!s.empty()) out.rename_blacklist.push_back(s);
            }
        }
    }
    out.suicide_enabled = JsonBool(j, "PlayerSuicideEnabled", out.suicide_enabled);
    out.suicide_price = JsonInt(j, "PlayerSuicidePrice", out.suicide_price);
    out.suicide_allow_ko = JsonBool(j, "PlayerSuicideKnockedOut", out.suicide_allow_ko);
    out.suicide_allow_handcuffs = JsonBool(j, "PlayerSuicideHandCuffs", out.suicide_allow_handcuffs);
    out.suicide_allow_sitting = JsonBool(j, "PlayerSuicideSitting", out.suicide_allow_sitting);
    out.suicide_allow_riding = JsonBool(j, "PlayerSuicideRiding", out.suicide_allow_riding);
    out.suicide_allow_picked = JsonBool(j, "PlayerSuicidePicked", out.suicide_allow_picked);
    out.suicide_allow_grappled = JsonBool(j, "PlayerSuicideGrappled", out.suicide_allow_grappled);
    out.suicide_allow_mind_control = JsonBool(j, "PlayerSuicideMindControl", out.suicide_allow_mind_control);
}

CmdMeta PlayerConfig::ParseCmdMeta(const nlohmann::json& j, const char* default_cmd) const {
    CmdMeta m;
    m.enabled = JsonBool(j, "Enabled", true);
    m.chat_command = JsonStr(j, "ChatCommand", default_cmd);
    m.description = JsonStr(j, "Description", "");
    m.cooldown_seconds = JsonInt(j, "CommandCooldownInSeconds", 0);
    if (j.contains("MasterBlacklist") && j["MasterBlacklist"].is_array()) {
        for (const auto& w : j["MasterBlacklist"]) {
            if (w.is_string()) {
                const std::string s = w.get<std::string>();
                if (!s.empty()) m.master_blacklist.push_back(s);
            }
        }
    }
    return m;
}

void PlayerConfig::Load() {
    const std::string path =
        ArkApi::Tools::GetCurrentDir() + "/ArkApi/Plugins/ArkPlayer/config.json";

    nlohmann::json full = nlohmann::json::object();
    std::ifstream file(path);
    if (!file.is_open()) {
        // Instalador TEK deve copiar config.json; sem ficheiro usamos defaults
        // embutidos (ParseGroup/ParseCmdMeta) para o plugin não ficar morto.
        Log::GetLog()->warn(
            "ArkPlayer: config.json ausente — defaults embutidos (crie {} e use ArkPlayer.Reload)",
            path);
    } else {
        try {
            file >> full;
        } catch (const nlohmann::json::exception& e) {
            throw std::runtime_error(std::string("config.json parse error: ") + e.what());
        }
    }

    root_ = full.contains("ArkPlayer") ? full["ArkPlayer"] : full;
    if (!root_.is_object())
        root_ = nlohmann::json::object();
    everything_free_ = JsonBool(root_, "EverythingIsFREE", false);
    sender_name_ = JsonStr(root_, "SenderNameInChat", "ARKLAND SERVER");

    messages_ = nlohmann::json::object();
    if (root_.contains("Messages") && root_["Messages"].is_object()) {
        const auto& msgs = root_["Messages"];
        if (msgs.contains("GroupPermission") && msgs["GroupPermission"].is_object()
            && msgs["GroupPermission"].contains("Default")) {
            messages_ = msgs["GroupPermission"]["Default"];
        } else {
            messages_ = msgs;
        }
        if (messages_.contains("SenderNameInChat") && messages_["SenderNameInChat"].is_string())
            sender_name_ = messages_["SenderNameInChat"].get<std::string>();
    }

    groups_.clear();
    default_group_ = GroupSettings{};
    if (root_.contains("GroupPermission") && root_["GroupPermission"].is_object()) {
        const auto& gp = root_["GroupPermission"];
        stacking_ = JsonBool(gp, "Stacking", false);
        if (gp.contains("Default") && gp["Default"].is_object())
            ParseGroup(gp["Default"], default_group_);
        for (auto it = gp.begin(); it != gp.end(); ++it) {
            if (!it.value().is_object()) continue;
            if (it.key() == "Default" || it.key() == "Stacking") continue;
            GroupSettings g = default_group_;
            ParseGroup(it.value(), g);
            groups_[it.key()] = g;
        }
    }

    wipe_meta_ = ParseCmdMeta(
        root_.value("PlayerCharacterWipe", nlohmann::json::object()), "/mindwipe");
    mission_meta_ = ParseCmdMeta(
        root_.value("PlayerCompleteMission", nlohmann::json::object()), "/missao");
    loot_meta_ = ParseCmdMeta(
        root_.value("PlayerGetDeathBags", nlohmann::json::object()), "/loot");
    rename_meta_ = ParseCmdMeta(
        root_.value("PlayerRename", nlohmann::json::object()), "/nome");
    suicide_meta_ = ParseCmdMeta(
        root_.value("PlayerSuicide", nlohmann::json::object()), "/kill");

    Log::GetLog()->info(
        "ArkPlayer: config loaded (free={}, groups={}, cmds=/mindwipe,/missao,/loot,/nome,/kill)",
        everything_free_, groups_.size() + 1);
}

std::string PlayerConfig::Msg(const char* key, const std::string& fallback) const {
    if (messages_.contains(key) && messages_[key].is_string())
        return messages_[key].get<std::string>();
    return fallback;
}

std::string PlayerConfig::FormatMsg(const char* key, int value,
                                    const std::string& fallback) const {
    std::string tpl = Msg(key, fallback);
    const auto pos = tpl.find("{}");
    if (pos != std::string::npos)
        tpl.replace(pos, 2, std::to_string(value));
    return tpl;
}

GroupSettings PlayerConfig::ResolveGroup(uint64_t steam_id) const {
    GroupSettings best = default_group_;
    int best_pri = default_group_.priority;

    for (const auto& [name, settings] : groups_) {
        if (!Perms::IsInGroup(steam_id, name)) continue;
        if (settings.priority < best_pri) {
            best_pri = settings.priority;
            best = settings;
            if (!stacking_) {
                // Keep searching for even higher priority (lower number).
            }
        }
    }
    return best;
}

} // namespace ArkPlayer
