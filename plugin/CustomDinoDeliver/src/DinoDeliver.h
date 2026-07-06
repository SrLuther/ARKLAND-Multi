#pragma once

#include "pch.h"

namespace CustomDinoDeliver {

bool DeliverCustomDino(AShooterPlayerController* controller,
                       const nlohmann::json& payload);

} // namespace CustomDinoDeliver
