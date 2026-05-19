#pragma once

#include "pch.h"
#include <string>
#include <vector>

// ─────────────────────────────────────────────────────────────────
//  ShopPerms — thin runtime binding to the ArkServerAPI
//  Permissions plugin (Permissions.dll).
//
//  The Permissions plugin is loaded separately on the server and
//  exports "IsPlayerInGroup". We resolve that symbol at runtime so
//  that the shop still works when the plugin is absent (all
//  permission checks will simply return false, i.e. access denied).
//
//  Typical exported signature:
//    bool IsPlayerInGroup(uint64 steam_id, const wchar_t* group_name);
//  Fallback (older builds):
//    bool IsPlayerInGroup(uint64 steam_id, const char* group_name);
// ─────────────────────────────────────────────────────────────────

namespace CustomShop {
namespace Perms {

// Call once in Plugin_Init after config + DB are ready.
void Init();

// Returns true if steam_id belongs to `group`.
// "Default" always returns true (every player is in Default).
// Returns false if Permissions plugin is not available.
bool IsInGroup(uint64_t steam_id, const std::string& group);

// Returns true if steam_id is in ANY of the supplied groups,
// or if groups is empty (no restriction).
bool IsInAnyGroup(uint64_t steam_id, const std::vector<std::string>& groups);

} // namespace Perms
} // namespace CustomShop
