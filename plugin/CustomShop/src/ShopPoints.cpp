#include "pch.h"
#include "ShopPoints.h"
#include "ShopConfig.h"

#include <algorithm>
#include <vector>

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
        const unsigned err = mysql_errno(db_);
        if (err == 1060) {
            Log::GetLog()->warn("ShopPoints::Exec duplicate column ignored (idempotent migration): {}", mysql_error(db_));
            return true;
        }
        Log::GetLog()->error("ShopPoints::Exec failed: {}", mysql_error(db_));
        return false;
    }
    return true;
}

bool ShopPoints::TryConnect(const std::string& host, std::string& err_out) {
    const auto& cfg = ShopConfig::Get();
    const unsigned int port = static_cast<unsigned int>(cfg.DbPort());

    if (db_) {
        mysql_close(db_);
        db_ = nullptr;
    }

    db_ = mysql_init(nullptr);
    if (!db_) {
        Log::GetLog()->critical("ShopPoints: mysql_init failed");
        return false;
    }

    my_bool reconnect = 1;
    mysql_options(db_, MYSQL_OPT_RECONNECT, &reconnect);

    my_bool ssl_enforce = 0;
    mysql_options(db_, MYSQL_OPT_SSL_ENFORCE, &ssl_enforce);
    my_bool ssl_verify = 0;
    mysql_options(db_, MYSQL_OPT_SSL_VERIFY_SERVER_CERT, &ssl_verify);

    const std::string& user = cfg.DbUser();
    const std::string& password = cfg.DbPassword();
    const std::string& database = cfg.DbDatabase();

    Log::GetLog()->info(
        "ShopPoints: connecting user='{}' host='{}' port={} db='{}' pw_len={}",
        user, host, port, database, password.size());

    if (!mysql_real_connect(db_,
                            host.c_str(),
                            user.c_str(),
                            password.c_str(),
                            database.c_str(),
                            port,
                            nullptr, 0)) {
        err_out = mysql_error(db_) ? mysql_error(db_) : "connect failed";
        Log::GetLog()->warn("ShopPoints: connect failed ({}:{} as {}): {}",
                            host, port, user, err_out);
        mysql_close(db_);
        db_ = nullptr;
        return false;
    }

    mysql_set_character_set(db_, "utf8mb4");
    mysql_query(db_, "SET SESSION sql_mode='NO_ENGINE_SUBSTITUTION'");
    return true;
}

bool ShopPoints::Open() {
    const auto& cfg = ShopConfig::Get();
    const std::string preferred = cfg.DbHost();
    std::vector<std::string> hosts;
    auto push_unique = [&](const std::string& h) {
        if (h.empty()) return;
        if (std::find(hosts.begin(), hosts.end(), h) == hosts.end())
            hosts.push_back(h);
    };
    push_unique(preferred);
    push_unique("127.0.0.1");
    push_unique("localhost");

    std::string last_err = "no hosts tried";
    for (const auto& host : hosts) {
        if (TryConnect(host, last_err)) {
            Log::GetLog()->info("ShopPoints: MySQL connected to {}:{}/{} (user={})",
                                host, cfg.DbPort(), cfg.DbDatabase(), cfg.DbUser());
            break;
        }
    }

    if (!db_) {
        Log::GetLog()->critical(
            "ShopPoints: cannot connect to MySQL — {} (tried hosts: {}:{}, user='{}', pw_len={})",
            last_err, preferred, cfg.DbPort(), cfg.DbUser(), cfg.DbPassword().size());
        return false;
    }

    // ── Create tables ────────────────────────────────────────────────
    if (!Exec(
        "CREATE TABLE IF NOT EXISTS players ("
        "  steam_id VARCHAR(20) PRIMARY KEY NOT NULL,"
        "  points   INT NOT NULL DEFAULT 0,"
        "  kits     TEXT"
        ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"))
        return false;

    // Migrate existing databases that predate the kits column.
    if (mysql_query(db_, "ALTER TABLE players ADD COLUMN IF NOT EXISTS kits TEXT") != 0) {
        const unsigned err = mysql_errno(db_);
        // ER_DUP_FIELDNAME (1060) — coluna já existe; ignorar
        if (err != 1060) {
            Log::GetLog()->error("ShopPoints::Exec failed: {}", mysql_error(db_));
            return false;
        }
    }

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

    if (!Exec(
        "CREATE TABLE IF NOT EXISTS player_entitlements ("
        "  id         INT AUTO_INCREMENT PRIMARY KEY,"
        "  steam_id   VARCHAR(20) NOT NULL,"
        "  group_name VARCHAR(32) NOT NULL,"
        "  expires    DATETIME DEFAULT NULL,"
        "  source     VARCHAR(64) DEFAULT NULL,"
        "  notes      VARCHAR(255) DEFAULT NULL,"
        "  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,"
        "  UNIQUE KEY uq_steam_group (steam_id, group_name),"
        "  INDEX idx_steam_expires (steam_id, expires)"
        ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"))
        return false;

    if (!Exec(
        "CREATE TABLE IF NOT EXISTS player_cloud_inventory ("
        "  steam_id     VARCHAR(20) PRIMARY KEY NOT NULL,"
        "  item_count   INT NOT NULL DEFAULT 0,"
        "  uploaded_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,"
        "  source_map   VARCHAR(128) DEFAULT NULL,"
        "  INDEX idx_uploaded (uploaded_at)"
        ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"))
        return false;

    if (!Exec(
        "CREATE TABLE IF NOT EXISTS player_cloud_items ("
        "  id           BIGINT AUTO_INCREMENT PRIMARY KEY,"
        "  steam_id     VARCHAR(20) NOT NULL,"
        "  sort_order   INT NOT NULL,"
        "  item_blob    MEDIUMBLOB NOT NULL,"
        "  INDEX idx_steam_order (steam_id, sort_order),"
        "  CONSTRAINT fk_cloud_steam"
        "    FOREIGN KEY (steam_id) REFERENCES player_cloud_inventory(steam_id)"
        "    ON DELETE CASCADE"
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
        "INSERT IGNORE INTO players (steam_id, points, kits) VALUES ('" +
        steam_id + "', " + std::to_string(starting_points) + ", '{}')";
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
    EnsurePlayer(steam_id, ShopConfig::Get().StartingPoints());
    const std::string sql =
        "UPDATE players SET points = points - " + std::to_string(cost) +
        " WHERE steam_id = '" + steam_id + "' AND points >= " + std::to_string(cost) + ";";
    if (!Exec(sql.c_str())) return false;
    return mysql_affected_rows(db_) > 0;
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

// ── Kit stash ────────────────────────────────────────────────────

nlohmann::json ShopPoints::GetKitStash(const std::string& steam_id) {
    EnsurePlayer(steam_id, ShopConfig::Get().StartingPoints());

    const std::string sql =
        "SELECT kits FROM players WHERE steam_id = '" + steam_id + "';";
    if (mysql_query(db_, sql.c_str()) != 0) return nlohmann::json::object();

    MYSQL_RES* res = mysql_store_result(db_);
    if (!res) return nlohmann::json::object();

    nlohmann::json stash = nlohmann::json::object();
    MYSQL_ROW row = mysql_fetch_row(res);
    if (row && row[0]) {
        try { stash = nlohmann::json::parse(row[0]); }
        catch (...) { stash = nlohmann::json::object(); }
    }
    mysql_free_result(res);
    return stash;
}

bool ShopPoints::SetKitStash(const std::string& steam_id,
                              const nlohmann::json& stash) {
    EnsurePlayer(steam_id, 0);
    const std::string json_str = stash.dump();

    std::vector<char> escaped(json_str.size() * 2 + 1);
    unsigned long len = mysql_real_escape_string(
        db_, escaped.data(), json_str.c_str(),
        static_cast<unsigned long>(json_str.size()));

    const std::string sql =
        "UPDATE players SET kits = '" + std::string(escaped.data(), len) +
        "' WHERE steam_id = '" + steam_id + "';";
    return Exec(sql.c_str());
}

bool ShopPoints::AddKitToStash(const std::string& steam_id,
                                const std::string& kit_id,
                                int amount) {
    nlohmann::json stash = GetKitStash(steam_id);
    const int current = stash.contains(kit_id)
        ? stash[kit_id].value("Amount", 0) : 0;
    stash[kit_id]["Amount"] = current + amount;
    return SetKitStash(steam_id, stash);
}

} // namespace CustomShop

