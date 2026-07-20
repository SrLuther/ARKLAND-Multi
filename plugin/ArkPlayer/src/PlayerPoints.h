#pragma once

#include "pch.h"

namespace ArkPlayer {
namespace Points {

void Init();
bool Available();
int GetPoints(uint64_t steam_id);
bool SpendPoints(uint64_t steam_id, int amount);

} // namespace Points
} // namespace ArkPlayer
