#pragma once

#include "pch.h"

namespace ArkPlayer {
namespace Perms {

void Init();
bool IsInGroup(uint64_t steam_id, const std::string& group);

} // namespace Perms
} // namespace ArkPlayer
