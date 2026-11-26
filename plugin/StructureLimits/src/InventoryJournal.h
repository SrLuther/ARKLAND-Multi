#pragma once
#include "DurableOutbox.h"
#include <json.hpp>
#include <atomic>
#include <condition_variable>
#include <deque>
#include <mutex>
#include <map>
#include <optional>
#include <thread>

namespace StructureLimits {
// Owns no game pointers. All disk I/O runs on its worker. Event failures retain
// the head of the queue; snapshots are derived data and may be coalesced.
class InventoryJournal {
public:
    InventoryJournal(DurableOutbox& outbox, std::filesystem::path stateFile);
    ~InventoryJournal();
    bool Event(nlohmann::json payload);
    void State(nlohmann::json payload);
    void Record(const std::string& id,nlohmann::json payload);
    bool Healthy() const { return healthy_; }
    std::size_t Pending() const;
private:
    void Run();
    DurableOutbox& outbox_;
    std::filesystem::path stateFile_;
    mutable std::mutex mutex_;
    std::condition_variable wake_;
    std::deque<OutboxEvent> events_;
    std::optional<nlohmann::json> state_;
    std::map<std::string,nlohmann::json> recordUpdates_;
    std::thread thread_;
    std::atomic<bool> healthy_{true};
    bool stopping_ = false;
    std::string boot_;
    std::uint64_t sequence_ = 0;
};
}
