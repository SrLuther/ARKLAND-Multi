#pragma once
#include "pch.h"

namespace FazendaRecursos {

struct ResourceDefinition {
    std::string category;
    std::string id;
    std::string name;
    std::string item_class;
    std::string input_class;
    int input_quantity = 1;
    int output_quantity = 1;
    int interval_seconds = 3600;
    int stack_size = 25;
    int capacity = 200;
    bool enabled = false;
};

class FarmConfig {
public:
    static FarmConfig& Get();
    void Load();
    void Reload();
    bool ApplyRemoteConfig(const nlohmann::json& config);
    bool Enabled() const { std::lock_guard<std::mutex> lock(resources_mutex_); return enabled_; }
    std::string LicenseGroup() const { std::lock_guard<std::mutex> lock(resources_mutex_); return license_group_; }
    int TickSeconds() const { std::lock_guard<std::mutex> lock(resources_mutex_); return tick_seconds_; }
    int SyncIntervalSeconds() const;
    std::string ServerId() const;
    std::string ShareKey() const;
    int PreviewLifetimeSeconds() const { std::lock_guard<std::mutex> lock(resources_mutex_); return preview_lifetime_seconds_; }
    int InitialCapacity() const { std::lock_guard<std::mutex> lock(resources_mutex_); return initial_capacity_; }
    std::vector<std::string> AdminGroups() const { std::lock_guard<std::mutex> lock(resources_mutex_); return admin_groups_; }
    std::vector<ResourceDefinition> Resources() const { return ResourcesSnapshot(); }
    std::vector<ResourceDefinition> ResourcesSnapshot() const;
    std::string Message(const std::string& key, const std::string& fallback = {}) const;
private:
    nlohmann::json root_, messages_;
    bool enabled_ = true;
    std::string license_group_ = "keyfarm";
    int tick_seconds_ = 60, preview_lifetime_seconds_ = 120, initial_capacity_ = 200;
    int sync_interval_seconds_ = 60;
    std::string server_id_ = "default";
    std::string share_key_ = "default";
    std::vector<std::string> admin_groups_;
    std::vector<ResourceDefinition> resources_;
    mutable std::mutex resources_mutex_;
};
}
