#pragma once
#include <API/ARK/Ark.h>
#include "StructureLimitsConfig.h"
#include "InventoryJournal.h"

namespace StructureLimits {
void StartPlacementRuntime(const PluginConfiguration&, LimitEngine&, InventoryJournal&);
void StopPlacementRuntime();
void SuspendPlacementRuntime(const std::string& reason);
int CheckPlacementGate(APrimalStructure*, APlayerController*, const FVector&, bool finalPlacement, int originalResult);
void CompletePlacementGate(APrimalStructure*, APlayerController*, bool placed);
void RemovePlacementGate(APrimalStructure*);
void ReleasePlacementCount(const std::string& structureId);
nlohmann::json PlacementRuntimeStatus();
std::string PlacementPilotMessage(const std::string& steamId);
}
