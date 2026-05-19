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

// Deliver a kit without charging points (admin use / manual delivery).
// Returns false if the kit_id does not exist.
bool GiveKit(AShooterPlayerController* controller,
             const std::string& kit_id);

} // namespace Store
} // namespace CustomShop
