#pragma once

#include "pch.h"

// ─────────────────────────────────────────────────────────────────
//  ShopData — assembles JSON payloads and dispatches them to the
//  mod client via ShopBridge::SendPayload.
//
//  Every function corresponds to one "Command" the mod understands:
//    GetShopItems, GetPoints, GetKits, PlayerKits,
//    BuyItem, UpdatePoints, Reload
// ─────────────────────────────────────────────────────────────────

namespace CustomShop {
namespace Data {

// Sends the item catalogue. Pass type_filter="" to send everything.
bool SendShopItems(AShooterPlayerController* controller,
                   const std::string& type_filter = "");

// Sends the current point balance for the player.
bool SendPoints(AShooterPlayerController* controller);

// Sends the full kit catalogue.
bool SendKits(AShooterPlayerController* controller);

// Sends the per-player kit amounts (redeem counts).
bool SendPlayerKits(AShooterPlayerController* controller,
                    const std::string& steam_id);

// Sends the result of a buy/kit action.
bool SendBuyResult(AShooterPlayerController* controller,
                   const std::string& steam_id,
                   const std::string& item_id,
                   int amount,
                   bool success);

// Sends the result of a trade (points transfer) to both parties.
bool SendTradeResult(AShooterPlayerController* sender,
                     AShooterPlayerController* receiver,
                     const std::string& sender_id,
                     const std::string& receiver_id,
                     int amount,
                     bool success);

// Notifies the mod that the shop data was reloaded server-side.
bool SendReload(AShooterPlayerController* controller);

// Runs the full init sequence when a player connects:
// buff → items → points → kits → player-kits.
void InitPlayer(AShooterPlayerController* controller);

} // namespace Data
} // namespace CustomShop
