#pragma once

#include "pch.h"

namespace CustomShop {

struct DeliverDinoResult {
    bool ok = false;
    uint32_t dino_id1 = 0;
    uint32_t dino_id2 = 0;
    int level = 0;
    std::string gender;  // catalog Gender → auditoria pública
    std::string public_code;  // Name/TamedName aplicado no spawn (rastreio)
};

// Entrega um dino definido em Dinos[] — spawn no chão ou cryopod conforme config/entry.
// Após spawn com sucesso, captura DinoID1/DinoID2 para auditoria do catálogo.
DeliverDinoResult DeliverDino(AShooterPlayerController* controller,
                              const nlohmann::json& entry);

} // namespace CustomShop
