#pragma once

#include "pch.h"

namespace CustomDinoDeliver {
namespace Bridge {

std::string GetSteamId(AShooterPlayerController* controller);
AShooterPlayerController* FindPlayer(const std::string& steam_id);

} // namespace Bridge
} // namespace CustomDinoDeliver
