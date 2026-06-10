#pragma once

#include "pch.h"

// ─────────────────────────────────────────────────────────────────
//  ShopBridge — utilitários do plugin (sem dependência de mod UI).
//
//  A loja é acessada exclusivamente pela interface web (arkshop_web).
//  Entregas pendentes são processadas via HttpClient::DeliverPending.
// ─────────────────────────────────────────────────────────────────

namespace CustomShop {
namespace Bridge {

// Returns the Steam64 ID as a string, or "" on failure.
std::string GetSteamId(AShooterPlayerController* controller);

// Finds an online player by Steam64 ID string.
AShooterPlayerController* FindPlayer(const std::string& steam_id);

// ── Legacy stubs (MX-E removido — mantidos para compatibilidade de build) ───
APrimalBuff* GetOrAddShopBuff(AShooterPlayerController* controller);
bool SendInitData(AShooterPlayerController* controller,
                  const nlohmann::json& shop_data,
                  int points);
bool SendPointsRefresh(AShooterPlayerController* controller, int points);
bool SendStashRefresh(AShooterPlayerController* controller,
                      const nlohmann::json& stash);
bool SendPayload(AShooterPlayerController* controller,
                 const nlohmann::json& payload);
bool SendPayload(const std::string& steam_id,
                 const nlohmann::json& payload);

// ── Diagnostics ──────────────────────────────────────────────────
void DiagnosePlayer(AShooterPlayerController* player,
                    AShooterPlayerController* admin);

} // namespace Bridge
} // namespace CustomShop
