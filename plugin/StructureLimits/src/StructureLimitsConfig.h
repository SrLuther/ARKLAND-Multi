#pragma once

#include "StructureLimitsCore.h"

#include <filesystem>

namespace StructureLimits {

struct PluginConfiguration {
    bool enabled = false;
    bool observationProbeEnabled = false;
    bool lifecycleObservationEnabled = false;
    bool lifecycleBeginPlayObservationEnabled = false;
    bool residentInventoryProbeEnabled = false;
    bool liveInventoryEnabled = false;
    bool enforcementRequiresValidatedInventory = true;
    std::string mapName;
    std::string instancePath;
    Configuration limits;
    std::filesystem::path localSnapshotFile;
    std::filesystem::path localOutboxDirectory;
    std::filesystem::path offlineOwnersFile;

    MapIdentity Identity() const;
};

PluginConfiguration ParsePluginConfiguration(const std::string& jsonText);
PluginConfiguration LoadPluginConfiguration(const std::filesystem::path& path);

} // namespace StructureLimits
