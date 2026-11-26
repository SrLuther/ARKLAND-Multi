#pragma once
#include "StructureLimitsCore.h"
#include <map>
#include <optional>
#include <set>

namespace StructureLimits {
struct ObservedStructure {
    std::string id, blueprint, steamId, tribeId;
    std::string actorName, actorFullName;
    std::uint32_t observedSources = 0;
    int targetingTeam = 0;
    int playerId = 0;
    double x = 0, y = 0, z = 0, latitude = 0, longitude = 0;
    bool hasCoordinates = false;
    bool placementConfirmed = false;
};
// A lower-bound live ledger. Missing from a resident scan is NEVER a removal.
// This type cannot produce a validated WorldSnapshot or enable enforcement.
class ObservedInventory {
public:
    enum class Change { None, Added, Updated, Conflict, Tombstoned, Invalid };
    Change Observe(ObservedStructure value);
    std::optional<ObservedStructure> Remove(const std::string& id);
    const std::map<std::string, ObservedStructure>& Records() const { return records_; }
    LimitsSummary Summary(const Owner& owner, const Configuration& config) const;
    std::size_t Conflicts() const { return conflicts_; }
    std::size_t RemovedCount() const { return tombstones_.size(); }
private:
    std::map<std::string, ObservedStructure> records_;
    std::set<std::string> tombstones_;
    std::size_t conflicts_ = 0;
};
}
