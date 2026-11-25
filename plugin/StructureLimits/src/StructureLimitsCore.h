#pragma once

#include <cstdint>
#include <map>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>

namespace StructureLimits {

struct MapIdentity {
    std::string displayId;
    std::string canonicalInstancePath;
};

MapIdentity MakeMapIdentity(const std::string& mapName,
                            const std::string& instancePath);

// Canonical key shared by ArkApi class names, blueprint paths in config,
// inventory snapshots, and placement decisions.
std::string NormalizeBlueprintKey(const std::string& blueprint);

struct Configuration {
    std::uint64_t globalPrimary = 0;
    std::uint32_t extraPercentage = 25;
    std::map<std::string, std::uint64_t> specificPrimary;

    std::uint64_t GlobalExtra() const;
    std::uint64_t GlobalCapacity() const;
    std::uint64_t SpecificExtra(std::uint64_t primary) const;
    void Validate() const;
};

struct Owner {
    std::string key;
    std::string tribeId;
    std::string steamId;

    static Owner ForPlayer(const std::string& tribeId,
                           const std::string& steamId);
};

struct ExistingStructure {
    std::string structureId;
    Owner owner;
    std::string blueprint;
};

struct WorldSnapshot {
    MapIdentity map;
    bool complete = false;
    bool validated = false;
    bool placementHookValidated = false;
    std::vector<ExistingStructure> structures;
};

enum class PlacementState {
    BypassEnforcement,
    Reserved,
    Denied
};

struct PlacementDecision {
    PlacementState state = PlacementState::BypassEnforcement;
    std::string reason;
    std::string reservationId;
    bool usesGlobalExtra = false;
    bool usesSpecificExtra = false;
};

struct SpecificLimitSummary {
    std::string blueprint;
    std::uint64_t used = 0;
    std::uint64_t primary = 0;
    std::uint64_t remainingPrimary = 0;
};

struct LimitsSummary {
    std::uint64_t globalUsed = 0;
    std::uint64_t globalPrimary = 0;
    std::uint64_t globalRemainingPrimary = 0;
    std::vector<SpecificLimitSummary> specific;
};

std::string FormatPrimaryLimitsMessage(const LimitsSummary& summary);

class LimitEngine {
public:
    LimitEngine(Configuration config, MapIdentity map);

    // Enforcement is fail-open until a complete and independently validated
    // world snapshot for this exact map and instance has been loaded.
    bool ActivateFromSnapshot(const WorldSnapshot& snapshot,
                              std::string* error = nullptr);
    void SuspendEnforcement();
    bool IsEnforcing() const;

    void PutLicense(const std::string& steamId,
                    std::int64_t expiresAtUnixSeconds);
    std::int64_t RenewLicense(const std::string& steamId,
                              std::int64_t nowUnixSeconds);
    bool HasActiveLicense(const std::string& steamId,
                          std::int64_t nowUnixSeconds) const;

    PlacementDecision ReservePlacement(const std::string& tribeId,
                                       const std::string& steamId,
                                       const std::string& blueprint,
                                       std::int64_t nowUnixSeconds);
    bool CommitPlacement(const std::string& reservationId,
                         const std::string& structureId);
    bool CancelPlacement(const std::string& reservationId);
    bool ReleaseStructure(const std::string& structureId);
    bool ReassignStructure(const std::string& structureId,
                           const Owner& newOwner);

    // Tribe merges use only the combined global cap; specific caps and
    // license state intentionally do not participate in this decision.
    bool CanMergeTribes(const std::string& tribeA,
                        const std::string& tribeB) const;

    LimitsSummary GetSummary(const std::string& tribeId,
                             const std::string& steamId) const;
    const MapIdentity& Map() const noexcept { return map_; }

private:
    struct Reservation {
        Owner owner;
        std::string blueprint;
        bool specific = false;
    };
    struct StructureRecord {
        Owner owner;
        std::string blueprint;
    };

    std::uint64_t EffectiveGlobalCount(const std::string& ownerKey) const;
    std::uint64_t EffectiveSpecificCount(const std::string& ownerKey,
                                         const std::string& blueprint) const;
    std::uint64_t CommittedGlobalCount(const std::string& ownerKey) const;
    std::uint64_t CommittedSpecificCount(const std::string& ownerKey,
                                         const std::string& blueprint) const;
    void RemoveReservationCounts(const Reservation& reservation);

    Configuration config_;
    MapIdentity map_;
    mutable std::mutex mutex_;
    bool enforcing_ = false;
    std::unordered_map<std::string, std::uint64_t> globalCounts_;
    std::unordered_map<std::string, std::uint64_t> pendingGlobal_;
    std::unordered_map<std::string,
        std::unordered_map<std::string, std::uint64_t>> specificCounts_;
    std::unordered_map<std::string,
        std::unordered_map<std::string, std::uint64_t>> pendingSpecific_;
    std::unordered_map<std::string, StructureRecord> structures_;
    std::unordered_map<std::string, Reservation> reservations_;
    std::unordered_map<std::string, std::int64_t> licenses_;
    std::uint64_t nextReservation_ = 1;
};

} // namespace StructureLimits
