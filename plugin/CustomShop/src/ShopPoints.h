#pragma once

#include "pch.h"

// ─────────────────────────────────────────────────────────────────
//  ShopPoints — MySQL-backed points store.
//
//  Tables (created automatically on first connect):
//    players      (steam_id PK, points INT)
//    transactions (id, ts, type, steam_id, target_id, item_id,
//                  amount, points_before, points_after)
//    vip_players  (steam_id PK, expires DATETIME, tier, notes)
// ─────────────────────────────────────────────────────────────────

namespace CustomShop {

class ShopPoints {
public:
    static ShopPoints& Get();
    ~ShopPoints();

    // Connects to MySQL and creates tables. Called once during Plugin_Init.
    bool Open();

    // Expose the live connection so ShopVip can share it.
    MYSQL* GetDb() const { return db_; }

    // Returns the current point balance. Inserts player with StartingPoints
    // if they don't exist yet.
    int  GetPoints(const std::string& steam_id);

    // Overwrites the balance unconditionally.
    bool SetPoints(const std::string& steam_id, int points);

    // Adds delta (positive or negative); balance clamped to 0.
    bool AddPoints(const std::string& steam_id, int delta);

    // Deducts cost only if balance >= cost. Returns false if insufficient.
    bool SpendPoints(const std::string& steam_id, int cost);

    // Appends a row to the transactions table.
    void LogTransaction(const std::string& type,
                        const std::string& steam_id,
                        const std::string& target_id,
                        const std::string& item_id,
                        int amount,
                        int points_before,
                        int points_after);

private:
    ShopPoints() = default;

    // Runs a fire-and-forget SQL statement; logs on error.
    bool Exec(const char* sql);

    // INSERT IGNORE player row with starting_points if not present.
    void EnsurePlayer(const std::string& steam_id, int starting_points);

    MYSQL* db_ = nullptr;
};

} // namespace CustomShop
