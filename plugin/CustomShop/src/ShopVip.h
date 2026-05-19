#pragma once

#include "pch.h"

// ─────────────────────────────────────────────────────────────────
//  ShopVip — VIP player management backed by the vip_players table.
//
//  Uses the same MYSQL* connection owned by ShopPoints.
//  Call SetDb() after ShopPoints::Open() succeeds.
// ─────────────────────────────────────────────────────────────────

namespace CustomShop {

struct VipEntry {
    std::string steam_id;
    std::string expires;   // "permanent" or ISO datetime "YYYY-MM-DD HH:MM:SS"
    std::string tier;
    std::string notes;
};

class ShopVip {
public:
    static ShopVip& Get();

    // Must be called after ShopPoints::Open() with the live connection.
    void SetDb(MYSQL* db);

    // Adds or updates a VIP row.
    // days == 0  →  permanent (expires = NULL)
    // days >  0  →  NOW() + INTERVAL days DAY
    bool AddVip(const std::string& steam_id,
                int days,
                const std::string& tier  = "vip",
                const std::string& notes = "");

    // Removes a VIP row. Returns false if not found.
    bool RemoveVip(const std::string& steam_id);

    // True if the player has a non-expired VIP row.
    bool IsVip(const std::string& steam_id);

    // Returns all VIP rows (expired ones included, for display).
    std::vector<VipEntry> ListVip();

    // Deletes rows whose expires < NOW().
    void PruneExpired();

private:
    ShopVip() = default;

    MYSQL* db_ = nullptr;
};

} // namespace CustomShop
