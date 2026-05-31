#pragma once

#include "pch.h"

// ─────────────────────────────────────────────────────────────────
//  ShopBridge — communication layer between the C++ plugin and the
//  MX-E Ark Shop UI mod (Steam Workshop ID 2693727499).
//
//  Protocol (discovered by inspecting ArkShopUI_Buff_FCAS.uasset):
//    Plugin → Mod (server calls on buff via ProcessEvent):
//      SetUiKey(UiKey: FString)              — set hotkey before init
//      OnServerInitFinished()                — signal plugin is ready
//      ROC_ShopDataReceived(ShopDataRaw: FString) — JSON shop+kit data
//      ROC_GetPointsReturn(Points: int32)    — player point balance
//      FCAS_OnPermissionsReceived(Groups: FString) — VIP groups JSON
//      FCAS_OnStashReceived(StashRaw: FString)     — kit stash JSON
//    Mod → Plugin (client fires ROS_ RPCs → plugin console commands):
//      ROS_GetPoints / ROS_GetKitsStash / ROS_OnPurchaseTry / etc.
// ─────────────────────────────────────────────────────────────────

namespace CustomShop {
namespace Bridge {

// Returns the Steam64 ID as a string, or "" on failure.
std::string GetSteamId(AShooterPlayerController* controller);

// Finds an online player by Steam64 ID string.
AShooterPlayerController* FindPlayer(const std::string& steam_id);

// Ensures the shop buff is applied to the player's character.
// Returns the buff instance, or nullptr if the player has no character yet.
APrimalBuff* GetOrAddShopBuff(AShooterPlayerController* controller);

// ── Specific mod RPCs ─────────────────────────────────────────────

// Full init sequence: SetUiKey → OnServerInitFinished →
//   ROC_ShopDataReceived(shop_data) → ROC_GetPointsReturn(points)
// shop_data must be: {"ShopItems":[...], "Kits":[...]}
bool SendInitData(AShooterPlayerController* controller,
                  const nlohmann::json& shop_data,
                  int points);

// Refresh player point balance after buy/sell/trade.
bool SendPointsRefresh(AShooterPlayerController* controller, int points);

// Refresh kit stash after redeem.
bool SendStashRefresh(AShooterPlayerController* controller,
                      const nlohmann::json& stash);

// ── Legacy generic payload (kept for buy/sell result responses) ───
bool SendPayload(AShooterPlayerController* controller,
                 const nlohmann::json& payload);
bool SendPayload(const std::string& steam_id,
                 const nlohmann::json& payload);

// ── Diagnostics ──────────────────────────────────────────────────
// Runs a full diagnostic pipeline for `player` and reports each step
// as a persistent server chat message visible to `admin`.
// Use via RCON: Shop.Debug <steamid>
void DiagnosePlayer(AShooterPlayerController* player,
                    AShooterPlayerController* admin);

} // namespace Bridge
} // namespace CustomShop
