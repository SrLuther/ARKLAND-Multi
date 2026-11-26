#pragma once
#include "ChatCore.h"
#include <atomic>
#include <condition_variable>
#include <deque>
#include <filesystem>
#include <mutex>
#include <thread>
#include <unordered_set>

namespace ChatArkland {
class Transport {
    std::filesystem::path path_;
    Json document_, local_, snapshot_=Json::array(), identities_=Json::object();
    std::shared_ptr<const SharedState> state_;
    mutable std::mutex mutex_;
    std::condition_variable cv_;
    std::thread worker_;
    std::atomic<bool> stop_{false}, healthy_{false};
    std::deque<Json> outbound_, inbound_, acks_;
    std::unordered_set<std::string> seen_, pending_;
    std::deque<std::string> seen_order_;
    uint64_t cursor_=0;
    bool resume_=false;
    std::string boot_, server_key_;
    void Run();
    Json Request(const Json& body);
    void Persist();
    bool Inbox(Json value);
public:
    explicit Transport(std::filesystem::path path);
    ~Transport();
    void Start();
    void Stop();
    void Snapshot(Json players);
    bool Enqueue(Json event);
    std::vector<Json> Drain(size_t maximum=8);
    void Processed(const Json& delivery,bool delivered);
    std::shared_ptr<const SharedState> State() const;
    bool Healthy()const{return healthy_.load();}
    const std::string& Boot()const{return boot_;}
    const std::string& ServerKey()const{return server_key_;}
    bool ObserveOnly()const{return local_.value("ObserveOnly",true)||GetModuleHandleW(L"KalsCrossChat.dll")!=nullptr;}
    Json Status()const;
};
}
