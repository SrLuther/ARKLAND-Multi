#pragma once

#include "pch.h"

namespace ArkEventHunt {
namespace Lifecycle {

void Start();
void Stop();

// Best-effort: lista instâncias ALIVE da API para este server/mapa e rebind local.
void ReconcileOrphans();

} // namespace Lifecycle
} // namespace ArkEventHunt
