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
    int capacity = 200;
    bool enabled = false;
};

class FarmConfig {
public:
    static FarmConfig& Get();
    void Load();
    void Reload();
    bool Enabled() const { return enabled_; }
    const std::string& LicenseGroup() const { return license_group_; }
    int TickSeconds() const { return tick_seconds_; }
    int PreviewLifetimeSeconds() const { return preview_lifetime_seconds_; }
    int InitialCapacity() const { return initial_capacity_; }
    const std::vector<std::string>& AdminGroups() const { return admin_groups_; }
    const std::vector<ResourceDefinition>& Resources() const { return resources_; }
    std::string Message(const std::string& key, const std::string& fallback = {}) const;
private:
    nlohmann::json root_, messages_;
    bool enabled_ = true;
    std::string license_group_ = "keyfarm";
    int tick_seconds_ = 60, preview_lifetime_seconds_ = 120, initial_capacity_ = 200;
    std::vector<std::string> admin_groups_;
    std::vector<ResourceDefinition> resources_;
};
}
