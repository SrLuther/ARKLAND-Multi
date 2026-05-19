#include "pch.h"
#include "ShopPoints.h"
#include "ShopConfig.h"

namespace CustomShop {

ShopPoints& ShopPoints::Get() {
    static ShopPoints instance;
    return instance;
}

ShopPoints::~ShopPoints() {
    if (db_) {
        mysql_close(db_);
        db_ = nullptr;
    }
}

// ────────────────────────────────────────────────────

bool ShopPoints::Exec(const char* sql) {
    if (mysql_query(db_, sql) != 0) {
        Log::GetLog()->error("ShopPoints::Exec failed: {}", mysql_error(db_));
        return false;
    }
    return true;
}

bool ShopPoints::Open() {
    const auto& cfg = ShopConfig::Get();

    db_ = mysql_init(nullptr);
    if (!db_) {
        Log::GetLog()->critical("ShopPoints: mysql_init failed");
        return false;
    }

    // Reconnect automatically if the connection drops.
    my_bool reconnect = 1;
    mysql_options(db_, MYSQL_OPT_RECONNECT, &reconnect);

    unsigned int port = static_cast<unsigned int>(cfg.DbPort());
    if (!mysql_real_connect(db_,
                            cfg.DbHost().c_str(),
                            cfg.DbUser().c_str(),
                            cfg.DbPassword().c_str(),
                            cfg.DbDatabase().c_str(),
                            port,
                            nullptr, 0)) {
        Log::GetLog()->critical("ShopPoints: cannot connect to MySQL at {}:{} — {}",
                                cfg.DbHost(), cfg.DbPort(), mysql_error(db_));
        mysql_close(db_);
        db_ = nullptr;
        return false;
    }

    // Set charset explicitly
    mysql_set_character_set(db_, "utf8mb4");

    // ── Create tables ────────────────────────────────────────────────
    if (!Exec(
        "CREATE TABLE IF NOT EXISTS players ("
        "  steam_id VARCHAR(20) PRIMARY KEY NOT NULL,"
        "  points   INT NOT NULL DEFAULT 0"
        ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"))
        return false;

    if (!Exec(
        "CREATE TABLE IF NOT EXISTS transactions ("
        "  id           INT AUTO_INCREMENT PRIMARY KEY,"
        "  ts           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,"
        "  type         VARCHAR(20) NOT NULL,"
        "  steam_id     VARCHAR(20) NOT NULL,"
        "  target_id    VARCHAR(20) DEFAULT NULL,"
        "  item_id      VARCHAR(128) DEFAULT NULL,"
        "  amount       INT DEFAULT 1,"
        "  points_before INT DEFAULT 0,"
        "  points_after  INT DEFAULT 0,"
        "  INDEX idx_steam (steam_id),"
        "  INDEX idx_ts    (ts)"
        ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"))
        return false;

    if (!Exec(
        "CREATE TABLE IF NOT EXISTS vip_players ("
        "  steam_id VARCHAR(20) PRIMARY KEY NOT NULL,"
        "  expires  DATETIME DEFAULT NULL,"
        "  tier     VARCHAR(32) NOT NULL DEFAULT 'vip',"
        "  notes    VARCHAR(255) DEFAULT NULL"
        ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"))
        return false;

    Log::GetLog()->info("ShopPoints: MySQL connected to {}:{}/{}",
                        cfg.DbHost(), cfg.DbPort(), cfg.DbDatabase());
    return true;
}

// ── private ─────────────────────────────────────────────────────

void ShopPoints::EnsurePlayer(const std::string& steam_id,
                               int starting_points) {
    const std::string sql =
        "INSERT IGNORE INTO players (steam_id, points) VALUES ('" +
        steam_id + "', " + std::to_string(starting_points) + ");";
    Exec(sql.c_str());
}

// ── public ──────────────────────────────────────────────────────

int ShopPoints::GetPoints(const std::string& steam_id) {
    EnsurePlayer(steam_id, ShopConfig::Get().StartingPoints());

    const std::string sql =
        "SELECT points FROM players WHERE steam_id = '" + steam_id + "';";
    if (mysql_query(db_, sql.c_str()) != 0) return 0;

    MYSQL_RES* res = mysql_store_result(db_);
    if (!res) return 0;

    int points = 0;
    MYSQL_ROW row = mysql_fetch_row(res);
    if (row && row[0])
        points = std::stoi(row[0]);
    mysql_free_result(res);
    return points;
}

bool ShopPoints::SetPoints(const std::string& steam_id, int points) {
    EnsurePlayer(steam_id, 0);
    const std::string sql =
        "UPDATE players SET points = " + std::to_string(points) +
        " WHERE steam_id = '" + steam_id + "';";
    return Exec(sql.c_str());
}

bool ShopPoints::AddPoints(const std::string& steam_id, int delta) {
    EnsurePlayer(steam_id, ShopConfig::Get().StartingPoints());
    const std::string sql =
        "UPDATE players SET points = GREATEST(0, points + " +
        std::to_string(delta) +
        ") WHERE steam_id = '" + steam_id + "';";
    return Exec(sql.c_str());
}

bool ShopPoints::SpendPoints(const std::string& steam_id, int cost) {
    if (cost <= 0) return true;
    const int before = GetPoints(steam_id);
    if (before < cost) return false;
    return SetPoints(steam_id, before - cost);
}

void ShopPoints::LogTransaction(const std::string& type,
                                const std::string& steam_id,
                                const std::string& target_id,
                                const std::string& item_id,
                                int amount,
                                int points_before,
                                int points_after) {
    if (!db_) return;

    // Escape nullable string fields
    auto escape = [&](const std::string& s) -> std::string {
        if (s.empty()) return "NULL";
        char buf[512];
        unsigned long len = mysql_real_escape_string(db_, buf,
                                s.c_str(),
                                static_cast<unsigned long>(s.size()));
        return std::string("'") + std::string(buf, len) + "'";
    };

    const std::string sql =
        "INSERT INTO transactions "
        "(type, steam_id, target_id, item_id, amount, points_before, points_after) VALUES ("
        + escape(type) + ","
        + escape(steam_id) + ","
        + escape(target_id) + ","
        + escape(item_id) + ","
        + std::to_string(amount) + ","
        + std::to_string(points_before) + ","
        + std::to_string(points_after) + ");";

    if (mysql_query(db_, sql.c_str()) != 0)
        Log::GetLog()->warn("LogTransaction failed: {}", mysql_error(db_));
}

} // namespace CustomShop

