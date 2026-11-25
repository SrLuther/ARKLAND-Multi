#include "OutboxSynchronizer.h"

#include <stdexcept>
#include <utility>

namespace StructureLimits {

OutboxSynchronizer::OutboxSynchronizer(DurableOutbox& outbox, Sender sender,
                                       std::chrono::milliseconds interval)
    : outbox_(outbox), sender_(std::move(sender)), interval_(interval) {
    if (!sender_) throw std::invalid_argument("Outbox sender is required");
    if (interval_ <= std::chrono::milliseconds::zero())
        throw std::invalid_argument("Outbox polling interval must be positive");
}

OutboxSynchronizer::~OutboxSynchronizer() { Stop(); }

bool OutboxSynchronizer::Start(std::string* error) {
    bool expected = false;
    if (!running_.compare_exchange_strong(expected, true)) {
        if (error) *error = "Outbox synchronizer is already running";
        return false;
    }
    try {
        outbox_.Initialize();
        worker_ = std::thread(&OutboxSynchronizer::Run, this);
    } catch (const std::exception& e) {
        running_.store(false);
        if (error) *error = e.what();
        return false;
    }
    if (error) error->clear();
    return true;
}

void OutboxSynchronizer::Stop() noexcept {
    running_.store(false);
    wake_.notify_all();
    if (worker_.joinable()) worker_.join();
}

std::string OutboxSynchronizer::LastError() const {
    std::lock_guard<std::mutex> lock(stateMutex_);
    return lastError_;
}

void OutboxSynchronizer::SetLastError(std::string message) {
    std::lock_guard<std::mutex> lock(stateMutex_);
    lastError_ = std::move(message);
}

void OutboxSynchronizer::Run() noexcept {
    while (running_.load()) {
        std::string pendingError;
        const auto events = outbox_.Pending(&pendingError);
        if (!pendingError.empty()) SetLastError(pendingError);

        for (const auto& event : events) {
            if (!running_.load()) break;
            try {
                std::string sendError;
                if (!sender_(event, sendError)) {
                    SetLastError(sendError.empty() ? "Outbox sender rejected event" : sendError);
                    break; // Preserve order and retry the pending event next cycle.
                }
                std::string ackError;
                if (!outbox_.Acknowledge(event.eventId, &ackError)) {
                    SetLastError(ackError.empty() ? "Unable to acknowledge delivered event" : ackError);
                    break; // At-least-once delivery; sender must be idempotent.
                }
                delivered_.fetch_add(1);
                SetLastError({});
            } catch (const std::exception& e) {
                SetLastError(e.what());
                break;
            } catch (...) {
                SetLastError("Unknown error while synchronizing outbox");
                break;
            }
        }

        std::unique_lock<std::mutex> lock(stateMutex_);
        wake_.wait_for(lock, interval_, [this] { return !running_.load(); });
    }
}

} // namespace StructureLimits
