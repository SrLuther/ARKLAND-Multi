#pragma once

#include "DurableOutbox.h"

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <functional>
#include <mutex>
#include <string>
#include <thread>

namespace StructureLimits {

// Runs a caller-supplied bounded I/O sink away from the game thread. The sink
// must be idempotent by event ID because delivery can be repeated if the remote
// commit succeeds but local acknowledgement is interrupted.
class OutboxSynchronizer {
public:
    using Sender = std::function<bool(const OutboxEvent&, std::string&)>;

    OutboxSynchronizer(DurableOutbox& outbox, Sender sender,
                       std::chrono::milliseconds interval = std::chrono::seconds(5));
    ~OutboxSynchronizer();

    OutboxSynchronizer(const OutboxSynchronizer&) = delete;
    OutboxSynchronizer& operator=(const OutboxSynchronizer&) = delete;

    bool Start(std::string* error = nullptr);
    void Stop() noexcept;
    bool IsRunning() const noexcept { return running_.load(); }
    std::string LastError() const;
    std::uint64_t DeliveredCount() const noexcept { return delivered_.load(); }

private:
    void Run() noexcept;
    void SetLastError(std::string message);

    DurableOutbox& outbox_;
    Sender sender_;
    std::chrono::milliseconds interval_;
    std::atomic<bool> running_{false};
    std::atomic<std::uint64_t> delivered_{0};
    mutable std::mutex stateMutex_;
    std::condition_variable wake_;
    std::string lastError_;
    std::thread worker_;
};

} // namespace StructureLimits
