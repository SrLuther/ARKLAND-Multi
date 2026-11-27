#pragma once
#include <API/ARK/Ark.h>
#include "StructureLimitsConfig.h"
#include "InventoryJournal.h"
namespace StructureLimits {
void StartLiveInventory(const PluginConfiguration& config, DurableOutbox& outbox, LimitEngine& engine);
void StopLiveInventory();
void SuspendLiveInventory();
void ObserveCompletedPlacement(APrimalStructure* structure, APlayerController* player);
void ObserveLiveDestruction(APrimalStructure* structure);
}
