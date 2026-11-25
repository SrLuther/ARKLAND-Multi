#pragma once

#include "StructureLimitsCore.h"

#include <filesystem>
#include <string>

namespace StructureLimits {

struct SnapshotLoadResult {
    bool found = false;
    bool usable = false;
    bool interruptedWriteFound = false;
    WorldSnapshot candidate;
    std::string error;
};

// Persists the last complete world inventory as a recovery candidate. Loading
// never marks it validated: a fresh live-world reconciliation is still required.
class LocalSnapshotStore {
public:
    LocalSnapshotStore(std::filesystem::path filePath, MapIdentity expectedMap);

    bool Save(const WorldSnapshot& snapshot, std::string* error = nullptr) const;
    SnapshotLoadResult LoadCandidate() const;
    const std::filesystem::path& FilePath() const noexcept { return filePath_; }

private:
    std::filesystem::path filePath_;
    MapIdentity expectedMap_;
};

} // namespace StructureLimits
