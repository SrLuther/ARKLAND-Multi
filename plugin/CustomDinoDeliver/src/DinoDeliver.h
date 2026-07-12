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

// Admin debug: classe UClass do dino mais próximo (PropagatorDinoBlacklist / mods).
struct DinoClassDump {
    bool ok = false;
    std::string class_name;  // ex.: TekStrider_Character_BP_C
    std::string full_name;   // GetFullName()
    std::string path_hint;   // /Game/... se presente no full name
    float dist = 0.0f;
};

DinoClassDump DumpNearestDinoClass(AShooterPlayerController* controller,
                                   float max_dist = 12000.0f);

} // namespace CustomDinoDeliver
