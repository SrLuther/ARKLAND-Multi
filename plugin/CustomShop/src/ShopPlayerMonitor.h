#pragma once

#include "pch.h"

namespace CustomShop::PlayerMonitor {

void Start();
void Stop();
void Record(AShooterPlayerController* player, const std::string& event);
void RecordDisconnect(AController* controller);
void HeartbeatOnlinePlayers();

} // namespace CustomShop::PlayerMonitor
