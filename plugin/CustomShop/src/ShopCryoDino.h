#pragma once

#include "pch.h"

namespace CustomShop {

// Entrega um dino definido em Dinos[] — spawn no chão ou cryopod conforme config/entry.
bool DeliverDino(AShooterPlayerController* controller,
                 const nlohmann::json& entry);

} // namespace CustomShop
