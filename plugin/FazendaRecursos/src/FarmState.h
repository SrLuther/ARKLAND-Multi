#pragma once
#include "FarmConfig.h"

namespace FazendaRecursos {
struct PlayerResource {
    int64_t stock = 0;
    int64_t last_accrual_utc = 0;
    bool active = false;
};
struct PlayerFarm {
    std::map<std::string, PlayerResource> resources;
};

class FarmState {
public:
    static FarmState& Get();
    void Load();
    bool Save();
    void Accrue(const std::string& steam_id, const std::vector<ResourceDefinition>& definitions, int64_t now);
    PlayerFarm GetPlayer(const std::string& steam_id);
private:
    std::mutex mutex_;
    nlohmann::json data_ = nlohmann::json::object();
    std::string Path() const;
};
}
