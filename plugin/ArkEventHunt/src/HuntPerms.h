#pragma once

#include "pch.h"

namespace ArkEventHunt {
namespace Perms {

void Init();

// "Default" sempre true. Sem Permissions.dll → false (excepto Default).
bool IsInGroup(uint64_t steam_id, const std::string& group);
bool IsInAnyGroup(uint64_t steam_id, const std::vector<std::string>& groups);

} // namespace Perms
} // namespace ArkEventHunt
