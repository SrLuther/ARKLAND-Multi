#pragma once
#include "StructureLimitsCore.h"
#include <filesystem>
#include <functional>
#include <memory>
#include <condition_variable>
#include <thread>

namespace StructureLimits {
struct OwnerSource { std::string name, sha256; std::uint64_t bytes=0; };
struct OwnerDirectory {
    bool valid=false;
    std::string state="disabled", savedDirectory, fingerprint;
    std::map<std::uint32_t,std::string> tribes, solos;
    std::vector<OwnerSource> sources;
};
OwnerDirectory ParseOwnerDirectory(const std::string& text,const MapIdentity& expected);
bool VerifyOwnerSources(OwnerDirectory& directory,const std::function<bool(const OwnerSource&)>& verify);

// No game objects, network or SQL. Hashes are checked only on this worker.
class OwnerDirectoryStore {
public:
    OwnerDirectoryStore(std::filesystem::path index,MapIdentity identity);
    ~OwnerDirectoryStore();
    std::shared_ptr<const OwnerDirectory> Snapshot() const;
private:
    void Run();
    std::filesystem::path index_;
    MapIdentity identity_;
    mutable std::mutex mutex_;
    std::condition_variable wake_;
    std::shared_ptr<const OwnerDirectory> current_;
    bool stopping_=false;
    std::thread worker_;
};
}
