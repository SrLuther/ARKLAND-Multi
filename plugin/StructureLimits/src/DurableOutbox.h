#pragma once

#include <filesystem>
#include <string>
#include <vector>

namespace StructureLimits {

struct OutboxEvent {
    std::string eventId;
    std::string payload;
};

// File-per-event spool. Acknowledgement is intentionally separate from
// reading so a caller deletes an event only after the remote transaction commits.
class DurableOutbox {
public:
    explicit DurableOutbox(std::filesystem::path directory);

    void Initialize();
    bool Enqueue(const std::string& eventId, const std::string& payload,
                 std::string* error = nullptr);
    std::vector<OutboxEvent> Pending(std::string* error = nullptr) const;
    bool Acknowledge(const std::string& eventId,
                     std::string* error = nullptr);
    const std::filesystem::path& Directory() const noexcept { return directory_; }

private:
    static bool IsSafeEventId(const std::string& eventId);
    std::filesystem::path EventPath(const std::string& eventId) const;

    std::filesystem::path directory_;
};

} // namespace StructureLimits
