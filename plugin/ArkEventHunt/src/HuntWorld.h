#pragma once

#include "pch.h"

namespace ArkEventHunt {
namespace World {

int64_t NowUnix();

APrimalDinoCharacter* FindDinoByIds(uint32_t id1, uint32_t id2);

// Despawn limpo (Destroy). Devolve true se o actor foi encontrado e destruído.
bool DespawnDino(uint32_t id1, uint32_t id2);

void BroadcastChat(const std::string& message);

bool IsPersonalTameActor(AActor* actor);

} // namespace World
} // namespace ArkEventHunt
