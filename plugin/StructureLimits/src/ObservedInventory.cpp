#include "ObservedInventory.h"
#include <algorithm>
#include <cmath>

namespace StructureLimits {
std::optional<MapPosition> PreciseMapPosition(double x,double y,const MapCalibration& input){
    auto c=input;
    if(c.latitudeScale==0)c.latitudeScale=800;if(c.longitudeScale==0)c.longitudeScale=800;
    if(c.latitudeOrigin==0)c.latitudeOrigin=-400000;if(c.longitudeOrigin==0)c.longitudeOrigin=-400000;
    if(!std::isfinite(x)||!std::isfinite(y)||!std::isfinite(c.latitudeScale)||!std::isfinite(c.longitudeScale)||
       !std::isfinite(c.latitudeOrigin)||!std::isfinite(c.longitudeOrigin))return std::nullopt;
    MapPosition result{(y+std::abs(c.latitudeOrigin))/(10*c.latitudeScale),(x+std::abs(c.longitudeOrigin))/(10*c.longitudeScale)};
    if(!std::isfinite(result.latitude)||!std::isfinite(result.longitude))return std::nullopt;
    return result;
}
bool IsGeneratedDeathCache(bool useDeathCacheCharacterId,double deathCacheCreationTime){
    return useDeathCacheCharacterId&&std::isfinite(deathCacheCreationTime)&&deathCacheCreationTime>0;
}
ObservedInventory::Change ObservedInventory::Observe(ObservedStructure value) {
    value.blueprint = NormalizeBlueprintKey(value.blueprint);
    if (value.id.empty() || value.id == "0" || value.blueprint.empty() ||
        (!value.targetingTeam && !value.playerId && value.steamId.empty())) return Change::Invalid;
    if (value.hasCoordinates && (!std::isfinite(value.x) || !std::isfinite(value.y) ||
        !std::isfinite(value.z) || !std::isfinite(value.latitude) || !std::isfinite(value.longitude)))
        value.hasCoordinates = false;
    if (tombstones_.count(value.id)) return Change::Tombstoned;
    const auto found = records_.find(value.id);
    if (found == records_.end()) { records_.emplace(value.id, std::move(value)); return Change::Added; }
    auto& old = found->second;
    if (old.blueprint != value.blueprint) { ++conflicts_; return Change::Conflict; }
    if (!old.actorFullName.empty() && !value.actorFullName.empty() && old.actorFullName != value.actorFullName) {
        ++conflicts_; return Change::Conflict;
    }
    // Attribution from a current connected controller is stronger than a raw census.
    // A change of team invalidates old owner attribution until proven again.
    if (old.targetingTeam != value.targetingTeam) {
        old.tribeId.clear(); old.steamId.clear();
    }
    if(old.playerId != value.playerId) old.steamId.clear();
    // A changed source file invalidates checkpoint-derived ownership. Never
    // resurrect it through the normal retained attribution fallback below.
    if(old.ownerSource.rfind("offline_checkpoint_",0)==0&&value.ownerSource=="unresolved"){
        old.tribeId.clear();old.steamId.clear();
    }
    if (value.steamId.empty()) value.steamId = old.steamId;
    if (value.tribeId.empty()) value.tribeId = old.tribeId;
    if(value.ownerSource=="unresolved"&&(!value.steamId.empty()||!value.tribeId.empty()))value.ownerSource="retained_native";
    value.placementConfirmed = value.placementConfirmed || old.placementConfirmed;
    value.observedSources |= old.observedSources;
    if(value.actorName.empty()) value.actorName=old.actorName;
    if(value.actorFullName.empty()) value.actorFullName=old.actorFullName;
    if (!value.hasCoordinates && old.hasCoordinates) {
        value.x=old.x; value.y=old.y; value.z=old.z;
        value.latitude=old.latitude; value.longitude=old.longitude; value.hasCoordinates=true;
    }
    const bool changed = old.targetingTeam != value.targetingTeam || old.playerId != value.playerId ||
        old.tribeId != value.tribeId || old.steamId != value.steamId ||
        old.placementConfirmed != value.placementConfirmed || old.hasCoordinates != value.hasCoordinates ||
        old.actorName != value.actorName || old.actorFullName != value.actorFullName || old.observedSources != value.observedSources ||
        old.ownerSource != value.ownerSource ||
        old.x != value.x || old.y != value.y || old.z != value.z;
    old = std::move(value);
    return changed ? Change::Updated : Change::None;
}
std::optional<ObservedStructure> ObservedInventory::Remove(const std::string& id) {
    if (id.empty() || id=="0") return std::nullopt;
    tombstones_.insert(id);
    const auto found=records_.find(id);
    if(found==records_.end()) return std::nullopt;
    auto value=found->second; records_.erase(found); return value;
}
LimitsSummary ObservedInventory::Summary(const Owner& owner, const Configuration& config) const {
    LimitsSummary summary; summary.globalPrimary=config.globalPrimary;
    std::map<std::string,std::uint64_t> counts;
    for(const auto& [id,record]:records_) {
        const bool belongs = !owner.tribeId.empty() ? record.tribeId==owner.tribeId :
            record.tribeId.empty() && !owner.steamId.empty() && record.steamId==owner.steamId;
        if(belongs){++summary.globalUsed; ++counts[record.blueprint];}
    }
    summary.globalRemainingPrimary=summary.globalUsed<summary.globalPrimary?summary.globalPrimary-summary.globalUsed:0;
    for(const auto& [bp,limit]:config.specificPrimary){const auto count=counts[bp];
        summary.specific.push_back({bp,count,limit,count<limit?limit-count:0});}
    return summary;
}
}
