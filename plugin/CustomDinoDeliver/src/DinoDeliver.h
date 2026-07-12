#pragma once

#include "pch.h"

namespace CustomDinoDeliver {

struct DinoIdentityCapture {
    uint32_t dino_id1 = 0;
    uint32_t dino_id2 = 0;
    nlohmann::json ancestors = nlohmann::json::array();
};

struct DeliverCustomDinoResult {
    bool ok = false;
    DinoIdentityCapture identity;
    // Motivo curto para logs/HTTP quando ok=false (ex.: spawn_exact_not_found).
    std::string failure_reason;
};

DeliverCustomDinoResult DeliverCustomDino(AShooterPlayerController* controller,
                                          const nlohmann::json& payload);

} // namespace CustomDinoDeliver
