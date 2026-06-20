#include "pch.h"
#include "ShopEntitlements.h"
#include "ShopBridge.h"
#include "ShopPerms.h"

#include <sstream>

namespace {

bool IsPaidTier(const std::string& group) {
    for (const char* g : CustomShop::kPaidLicenseGroups) {
        if (group == g) return true;
    }
    return false;
}

std::vector<std::string> ParsePermissionsList(const std::string& perms_str) {
    std::vector<std::string> out;
    std::stringstream ss(perms_str);
    std::string token;
    while (std::getline(ss, token, ',')) {
        const auto first = token.find_first_not_of(" \t");
        if (first == std::string::npos) continue;
        const auto last = token.find_last_not_of(" \t");
        out.push_back(token.substr(first, last - first + 1));
    }
    return out;
}

void RunPermissionConsole(const std::string& steam_id, const std::string& cmd) {
    auto* world = ArkApi::GetApiUtils().GetWorld();
    if (!world) return;
    const auto& controllers = world->PlayerControllerListField();
    AShooterPlayerController* target = nullptr;
    for (TWeakObjectPtr<APlayerController> wpc : controllers) {
        auto* sc = static_cast<AShooterPlayerController*>(wpc.Get());
        if (!sc) continue;
        if (CustomShop::Bridge::GetSteamId(sc) == steam_id) {
            target = sc;
            break;
        }
    }
    if (!target) {
        Log::GetLog()->info(
            "ShopEntitlements: no online player for Permissions sync ({})", steam_id);
        return;
    }
    FString fscmd(cmd.c_str());
    FString result;
    target->ConsoleCommand(&result, &fscmd, true);
    Log::GetLog()->info(
        "ShopEntitlements: Permissions sync cmd='{}' steam_id={} result='{}'",
        cmd, steam_id, result.ToString());
}

} // anonymous namespace

namespace CustomShop {

ShopEntitlements& ShopEntitlements::Get() {
    static ShopEntitlements instance;
    return instance;
}

void ShopEntitlements::SetDb(MYSQL* db) {
    db_ = db;
}

void ShopEntitlements::SyncPermissionsCommand(const std::string& steam_id,
                                            const std::string& group,
                                            int days) {
    std::string cmd;
    if (days <= 0) {
        cmd = "Permissions.Add " + steam_id + " " + group;
    } else {
        const int hours = days * 24;
        cmd = "Permissions.AddTimed " + steam_id + " " + group + " " + std::to_string(hours);
    }
    RunPermissionConsole(steam_id, cmd);
}

bool ShopEntitlements::Grant(const std::string& steam_id,
                           const std::string& group,
                           int days,
                           const std::string& source,
                           const std::string& notes) {
    if (!db_ || steam_id.empty() || group.empty()) return false;

    char buf_id[64], buf_grp[64], buf_src[128], buf_notes[512];
    mysql_real_escape_string(db_, buf_id, steam_id.c_str(),
        static_cast<unsigned long>(steam_id.size()));
    mysql_real_escape_string(db_, buf_grp, group.c_str(),
        static_cast<unsigned long>(group.size()));
    mysql_real_escape_string(db_, buf_src, source.c_str(),
        static_cast<unsigned long>(source.size()));
    mysql_real_escape_string(db_, buf_notes, notes.c_str(),
        static_cast<unsigned long>(notes.size()));

    if (IsPaidTier(group)) {
        const std::string del = "DELETE FROM player_entitlements WHERE steam_id = '"
            + std::string(buf_id) + "' AND group_name IN ('Gamma','Beta','Alfa') "
            "AND group_name != '" + std::string(buf_grp) + "';";
        mysql_query(db_, del.c_str());
    }

    std::string sql;
    if (days <= 0) {
        sql =
            "INSERT INTO player_entitlements (steam_id, group_name, expires, source, notes) VALUES ('"
            + std::string(buf_id) + "', '" + std::string(buf_grp) + "', NULL, '"
            + std::string(buf_src) + "', '" + std::string(buf_notes) + "') "
            "ON DUPLICATE KEY UPDATE "
            "  expires = NULL,"
            "  source  = '" + std::string(buf_src) + "',"
            "  notes   = '" + std::string(buf_notes) + "';";
    } else {
        const std::string insert_expires =
            "DATE_ADD(NOW(), INTERVAL " + std::to_string(days) + " DAY)";
        const std::string update_expires =
            "DATE_ADD(GREATEST(COALESCE(expires, NOW()), NOW()), INTERVAL "
            + std::to_string(days) + " DAY)";
        sql =
            "INSERT INTO player_entitlements (steam_id, group_name, expires, source, notes) VALUES ('"
            + std::string(buf_id) + "', '" + std::string(buf_grp) + "', "
            + insert_expires + ", '" + std::string(buf_src) + "', '"
            + std::string(buf_notes) + "') "
            "ON DUPLICATE KEY UPDATE "
            "  expires = " + update_expires + ","
            "  source  = '" + std::string(buf_src) + "',"
            "  notes   = '" + std::string(buf_notes) + "';";
    }

    if (mysql_query(db_, sql.c_str()) != 0) {
        Log::GetLog()->error("ShopEntitlements::Grant failed: {}", mysql_error(db_));
        return false;
    }

    SyncPermissionsCommand(steam_id, group, days);
    return true;
}

bool ShopEntitlements::Revoke(const std::string& steam_id, const std::string& group) {
    if (!db_ || steam_id.empty() || group.empty()) return false;

    char buf_id[64], buf_grp[64];
    mysql_real_escape_string(db_, buf_id, steam_id.c_str(),
        static_cast<unsigned long>(steam_id.size()));
    mysql_real_escape_string(db_, buf_grp, group.c_str(),
        static_cast<unsigned long>(group.size()));

    const std::string sql =
        "DELETE FROM player_entitlements WHERE steam_id = '"
        + std::string(buf_id) + "' AND group_name = '" + std::string(buf_grp) + "';";

    if (mysql_query(db_, sql.c_str()) != 0) {
        Log::GetLog()->error("ShopEntitlements::Revoke failed: {}", mysql_error(db_));
        return false;
    }

    RunPermissionConsole(steam_id, "Permissions.Remove " + steam_id + " " + group);
    return mysql_affected_rows(db_) > 0;
}

bool ShopEntitlements::HasActive(const std::string& steam_id, const std::string& group) {
    if (group == "Default") return true;
    if (steam_id.empty()) return false;

    uint64_t sid = 0;
    try { sid = std::stoull(steam_id); } catch (...) {}

    if (sid && Perms::IsInGroup(sid, group)) return true;

    if (!db_) return false;

    char buf_id[64], buf_grp[64];
    mysql_real_escape_string(db_, buf_id, steam_id.c_str(),
        static_cast<unsigned long>(steam_id.size()));
    mysql_real_escape_string(db_, buf_grp, group.c_str(),
        static_cast<unsigned long>(group.size()));

    const std::string sql =
        "SELECT 1 FROM player_entitlements WHERE steam_id = '"
        + std::string(buf_id) + "' AND group_name = '" + std::string(buf_grp) + "' "
        "AND (expires IS NULL OR expires > NOW()) LIMIT 1;";

    if (mysql_query(db_, sql.c_str()) != 0) return false;
    MYSQL_RES* res = mysql_store_result(db_);
    if (!res) return false;
    const bool found = mysql_fetch_row(res) != nullptr;
    mysql_free_result(res);
    return found;
}

bool ShopEntitlements::HasAnyActive(const std::string& steam_id,
                                    const std::vector<std::string>& groups) {
    if (groups.empty()) return true;
    for (const auto& g : groups)
        if (HasActive(steam_id, g)) return true;
    return false;
}

std::vector<std::string> ShopEntitlements::GetActiveGroups(const std::string& steam_id) {
    std::vector<std::string> out;
    if (!db_ || steam_id.empty()) return out;

    char buf_id[64];
    mysql_real_escape_string(db_, buf_id, steam_id.c_str(),
        static_cast<unsigned long>(steam_id.size()));

    const std::string sql =
        "SELECT group_name FROM player_entitlements WHERE steam_id = '"
        + std::string(buf_id) + "' AND (expires IS NULL OR expires > NOW());";

    if (mysql_query(db_, sql.c_str()) != 0) return out;
    MYSQL_RES* res = mysql_store_result(db_);
    if (!res) return out;

    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res))) {
        if (row[0] && row[0][0]) out.emplace_back(row[0]);
    }
    mysql_free_result(res);
    return out;
}

void ShopEntitlements::PruneExpired() {
    if (!db_) return;
    const char* sql =
        "DELETE FROM player_entitlements WHERE expires IS NOT NULL AND expires < NOW();";
    if (mysql_query(db_, sql) != 0) {
        Log::GetLog()->error("ShopEntitlements::PruneExpired failed: {}", mysql_error(db_));
    }
}

bool ShopEntitlements::CanRedeem(uint64_t steam_id, const nlohmann::json& entry) {
    if (!entry.contains("Permissions")) return true;

    const std::string perms_str = entry.value("Permissions", "");
    if (perms_str.empty()) return true;

    const auto groups = ParsePermissionsList(perms_str);
    if (groups.empty()) return true;

    const std::string mode = entry.value("PermissionsMode", "any");
    const std::string sid = std::to_string(steam_id);

    if (mode == "all") {
        for (const auto& g : groups)
            if (!HasActive(sid, g)) return false;
        return true;
    }
    return HasAnyActive(sid, groups);
}

bool ShopEntitlements::ApplyLicenseGrant(AShooterPlayerController* controller,
                                       const nlohmann::json& entry,
                                       const std::string& kit_or_item_id) {
    if (!entry.contains("LicenseGrant") || !entry.at("LicenseGrant").is_object())
        return false;

    const auto& lic = entry.at("LicenseGrant");
    if (lic.value("Redeemable", true) == false && lic.value("AdminOnly", false))
        return false;

    const std::string group = lic.value("Group", "");
    if (group.empty()) return false;

    const int days = lic.value("Days", 30);
    const std::string sid = controller
        ? Bridge::GetSteamId(controller)
        : std::string();

    if (sid.empty()) return false;

    const std::string notes = "deliver:" + kit_or_item_id;
    return Grant(sid, group, days, notes, notes);
}

} // namespace CustomShop
