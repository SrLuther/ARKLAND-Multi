#pragma once

#include "pch.h"

// ─────────────────────────────────────────────────────────────────
//  ShopStore — buy logic: deducts points then delivers goods.
//
//  Items are delivered via ArkApi::GetApiUtils().GiveItem().
//  Kit commands are executed via the game-mode console.
// ─────────────────────────────────────────────────────────────────

namespace CustomShop {
namespace Store {

// Buy a single item from the "Items" section (with optional multiplied qty).
// Returns false if the player lacks points or the item_id does not exist.
bool BuyItem(AShooterPlayerController* controller,
             const std::string& item_id,
             int amount = 1);

// Redeem a kit from the "Kits" section (amount is always 1 per call).
// Returns false if the player lacks points or the kit_id does not exist.
bool BuyKit(AShooterPlayerController* controller,
            const std::string& kit_id);

// Deliver a kit without charging points (admin / web pending / manual).
// skip_permission_check: true for web pending orders (already paid/authorized).
// skip_limit_check: true for admin manual delivery (ignores DefaultAmount).
// fail_reason: optional out — machine-readable cause when returning false.
// out_dino_records: optional JSON array of {dino_id1,dino_id2,level} per spawn.
bool GiveKit(AShooterPlayerController* controller,
             const std::string& kit_id,
             bool skip_permission_check = false,
             bool skip_limit_check = false,
             std::string* fail_reason = nullptr,
             nlohmann::json* out_dino_records = nullptr);

// Deliver an item without charging points (web store / admin use).
bool GiveItem(AShooterPlayerController* controller,
              const std::string& item_id,
              int amount = 1,
              bool skip_permission_check = false,
              std::string* fail_reason = nullptr,
              nlohmann::json* out_dino_records = nullptr);

} // namespace Store
} // namespace CustomShop
