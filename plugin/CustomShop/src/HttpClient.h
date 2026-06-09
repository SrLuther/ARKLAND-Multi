#pragma once
#include <string>
#include "pch.h"

namespace CustomShop {
namespace HttpClient {

/// Configure the arkshop_web endpoint.
/// @param web_url      e.g. "http://127.0.0.1:5177"
/// @param api_key      Value for X-API-Key header (must match ARKSHOP_API_KEY env var)
void Configure(const std::string& web_url, const std::string& api_key = "");

/// Cleanup WinHTTP session.
void Shutdown();

/// Fetch pending orders from arkshop_web for a player and deliver them.
/// Should be called when a player connects (HandleNewPlayer).
/// @return true if at least one pending item was delivered.
bool DeliverPending(AShooterPlayerController* controller);

// Internal — access the configured URL (used by ShopConfig reload)
extern std::string g_web_url;
extern std::string g_api_key;

} // namespace HttpClient
} // namespace CustomShop
