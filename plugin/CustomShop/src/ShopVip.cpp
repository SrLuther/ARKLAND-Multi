#include "pch.h"
#include "ShopVip.h"

namespace CustomShop {

ShopVip& ShopVip::Get() {
    static ShopVip instance;
    return instance;
}

void ShopVip::SetDb(MYSQL* db) {
    db_ = db;
}

// ─────────────────────────────────────────────────────────────────

bool ShopVip::AddVip(const std::string& steam_id,
                     int days,
                     const std::string& tier,
                     const std::string& notes) {
    if (!db_) return false;

    char buf_id[64], buf_tier[128], buf_notes[512];
    mysql_real_escape_string(db_, buf_id,
        steam_id.c_str(), static_cast<unsigned long>(steam_id.size()));
    mysql_real_escape_string(db_, buf_tier,
        tier.c_str(), static_cast<unsigned long>(tier.size()));
    mysql_real_escape_string(db_, buf_notes,
        notes.c_str(), static_cast<unsigned long>(notes.size()));

    const std::string expires_sql =
        (days <= 0)
            ? "NULL"
            : "DATE_ADD(NOW(), INTERVAL " + std::to_string(days) + " DAY)";

    const std::string sql =
        "INSERT INTO vip_players (steam_id, expires, tier, notes) VALUES ('"
        + std::string(buf_id) + "', " + expires_sql + ", '"
        + std::string(buf_tier) + "', '"
        + std::string(buf_notes) + "') "
        "ON DUPLICATE KEY UPDATE "
        "  expires = " + expires_sql + ","
        "  tier    = '" + std::string(buf_tier) + "',"
        "  notes   = '" + std::string(buf_notes) + "';";

    if (mysql_query(db_, sql.c_str()) != 0) {
        Log::GetLog()->error("ShopVip::AddVip failed: {}", mysql_error(db_));
        return false;
    }
    return true;
}

bool ShopVip::RemoveVip(const std::string& steam_id) {
    if (!db_) return false;

    char buf[64];
    mysql_real_escape_string(db_, buf,
        steam_id.c_str(), static_cast<unsigned long>(steam_id.size()));

    const std::string sql =
        "DELETE FROM vip_players WHERE steam_id = '" + std::string(buf) + "';";

    if (mysql_query(db_, sql.c_str()) != 0) {
        Log::GetLog()->error("ShopVip::RemoveVip failed: {}", mysql_error(db_));
        return false;
    }
    return mysql_affected_rows(db_) > 0;
}

bool ShopVip::IsVip(const std::string& steam_id) {
    if (!db_) return false;

    char buf[64];
    mysql_real_escape_string(db_, buf,
        steam_id.c_str(), static_cast<unsigned long>(steam_id.size()));

    const std::string sql =
        "SELECT 1 FROM vip_players "
        "WHERE steam_id = '" + std::string(buf) + "' "
        "  AND (expires IS NULL OR expires > NOW()) LIMIT 1;";

    if (mysql_query(db_, sql.c_str()) != 0) return false;

    MYSQL_RES* res = mysql_store_result(db_);
    if (!res) return false;

    const bool found = (mysql_num_rows(res) > 0);
    mysql_free_result(res);
    return found;
}

std::vector<VipEntry> ShopVip::ListVip() {
    std::vector<VipEntry> result;
    if (!db_) return result;

    const char* sql =
        "SELECT steam_id, "
        "       IFNULL(DATE_FORMAT(expires,'%Y-%m-%d %H:%i:%s'), 'permanent'), "
        "       tier, IFNULL(notes,'') "
        "FROM vip_players "
        "ORDER BY expires IS NULL DESC, expires ASC;";

    if (mysql_query(db_, sql) != 0) {
        Log::GetLog()->error("ShopVip::ListVip failed: {}", mysql_error(db_));
        return result;
    }

    MYSQL_RES* res = mysql_store_result(db_);
    if (!res) return result;

    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res))) {
        VipEntry e;
        e.steam_id = row[0] ? row[0] : "";
        e.expires  = row[1] ? row[1] : "permanent";
        e.tier     = row[2] ? row[2] : "vip";
        e.notes    = row[3] ? row[3] : "";
        result.push_back(std::move(e));
    }
    mysql_free_result(res);
    return result;
}

void ShopVip::PruneExpired() {
    if (!db_) return;
    mysql_query(db_,
        "DELETE FROM vip_players WHERE expires IS NOT NULL AND expires < NOW();");
}

} // namespace CustomShop
