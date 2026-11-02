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
    struct UploadedSoul {
        std::string id;
        std::string item_class;
        std::string species_blueprint;
        std::string display_name;
        std::string blob_file;
        std::string status;
        int64_t uploaded_utc = 0;
        uint64_t blob_size = 0;
    };
    std::map<std::string, UploadedSoul> souls;
};

class FarmState {
public:
    static FarmState& Get();
    void Load();
    bool Save();
    void Accrue(const std::string& steam_id, const std::vector<ResourceDefinition>& definitions, int64_t now);
    PlayerFarm GetPlayer(const std::string& steam_id);
    std::vector<std::string> PlayerIds();
    bool HasSoul(const std::string& steam_id, const std::string& species_blueprint);
    bool AddPendingSoul(const std::string& steam_id, const PlayerFarm::UploadedSoul& soul);
    bool CommitSoul(const std::string& steam_id, const std::string& soul_id);
    bool RemoveSoul(const std::string& steam_id, const std::string& soul_id);
    std::string SoulDirectory(const std::string& steam_id) const;
private:
    std::mutex mutex_;
    nlohmann::json data_ = nlohmann::json::object();
    std::string Path() const;
    bool SaveLocked();
};
}
