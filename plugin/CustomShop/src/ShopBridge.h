#pragma once

#include "pch.h"

// ─────────────────────────────────────────────────────────────────
//  ShopBridge — communication layer between the C++ plugin and the
//  MX-E Ark Shop UI mod (Steam Workshop ID 2693727499).
//
//  Protocol: the plugin applies a permanent "shop buff"
//  (Blueprint'/KinyShop/BP_Shop_Buff.BP_Shop_Buff') to the player's
//  character. That buff has a UE4 event "ClientReceiveCallback(FString)"
//  that, when called via ProcessEvent(), transmits a JSON payload to
//  the client-side mod.
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

// Returns true if the mod is loaded on the client (buff RPC reachable).
bool CanUseMod(AShooterPlayerController* controller);

// Serialises payload to JSON and fires ClientReceiveCallback on the buff.
bool SendPayload(AShooterPlayerController* controller,
                 const nlohmann::json& payload);

bool SendPayload(const std::string& steam_id,
                 const nlohmann::json& payload);

} // namespace Bridge
} // namespace CustomShop
