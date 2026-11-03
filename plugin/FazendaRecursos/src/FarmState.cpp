#include "FarmState.h"
#include "FarmConfig.h"

namespace FazendaRecursos {
FarmState& FarmState::Get() { static FarmState value; return value; }
std::string FarmState::Path() const {
    return ArkApi::Tools::GetCurrentDir() + "/ArkApi/Plugins/FazendaRecursos/data/farms.json";
}
void FarmState::Load() {
    std::lock_guard<std::mutex> lock(mutex_);
    std::error_code ec;
    std::filesystem::create_directories(std::filesystem::path(Path()).parent_path(), ec);
    std::ifstream in(Path());
    if (!in) { data_ = nlohmann::json::object(); return; }
    try { in >> data_; if (!data_.is_object()) data_ = nlohmann::json::object(); }
    catch (const std::exception& e) {
        Log::GetLog()->error("FazendaRecursos: estado inválido; não será sobrescrito: {}", e.what());
        throw;
    }
}
bool FarmState::Save() {
    std::lock_guard<std::mutex> lock(mutex_);
    return SaveLocked();
}
bool FarmState::SaveLocked() {
    const auto path = std::filesystem::path(Path());
    std::error_code ec;
    std::filesystem::create_directories(path.parent_path(), ec);
    if (ec) return false;
    const auto temp = path.wstring() + L".tmp";
    { std::ofstream out(temp, std::ios::binary | std::ios::trunc); if (!out) return false;
      out << data_.dump(2); out.flush(); if (!out) return false; }
    if (!MoveFileExW(temp.c_str(), path.wstring().c_str(),
                     MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        std::filesystem::remove(temp, ec);
        return false;
    }
    return true;
}
void FarmState::Accrue(const std::string& steam_id,
                       const std::vector<ResourceDefinition>& definitions, int64_t now) {
    if (steam_id.empty()) return;
    std::lock_guard<std::mutex> lock(mutex_);
    auto& player = data_[steam_id];
    if (!player.is_object()) player = nlohmann::json::object();
    auto& resources = player["resources"];
    if (!resources.is_object()) resources = nlohmann::json::object();
    for (const auto& def : definitions) {
        if (!def.enabled) continue;
        auto& state = resources[def.id];
        if (!state.is_object()) state = nlohmann::json::object();
        int64_t stock = std::max<int64_t>(0, state.value("stock", int64_t{0}));
        int64_t last = std::max<int64_t>(0, state.value("last_accrual_utc", int64_t{0}));
        const bool active = state.value("active", false);
        if (!last) last = now;
        if (active && now > last && def.interval_seconds > 0) {
            const int64_t periods = (now - last) / def.interval_seconds;
            const int64_t capacity = def.capacity;
            const int64_t produced = std::min<int64_t>(periods * def.output_quantity, std::max<int64_t>(0, capacity - stock));
            stock += produced;
            last += periods * def.interval_seconds;
        }
        state["stock"] = stock;
        state["last_accrual_utc"] = last;
        state["active"] = active;
    }
}
PlayerFarm FarmState::GetPlayer(const std::string& steam_id) {
    std::lock_guard<std::mutex> lock(mutex_);
    PlayerFarm out;
    const auto it = data_.find(steam_id);
    if (it == data_.end()) return out;
    if ((*it).contains("resources") && (*it)["resources"].is_object()) {
        for (auto r = (*it)["resources"].begin(); r != (*it)["resources"].end(); ++r) {
            PlayerResource value;
            value.stock = std::max<int64_t>(0, r.value().value("stock", int64_t{0}));
            value.last_accrual_utc = r.value().value("last_accrual_utc", int64_t{0});
            value.active = r.value().value("active", false);
            out.resources[r.key()] = value;
        }
    }
    if ((*it).contains("souls") && (*it)["souls"].is_object()) {
        for (auto r = (*it)["souls"].begin(); r != (*it)["souls"].end(); ++r) {
            if (!r.value().is_object()) continue;
            PlayerFarm::UploadedSoul soul;
            soul.id = r.key();
            soul.item_class = r.value().value("item_class", std::string{});
            soul.species_blueprint = r.value().value("species_blueprint", std::string{});
            soul.display_name = r.value().value("display_name", std::string{});
            soul.blob_file = r.value().value("blob_file", std::string{});
            soul.status = r.value().value("status", std::string("pending"));
            soul.uploaded_utc = r.value().value("uploaded_utc", int64_t{0});
            soul.blob_size = r.value().value("blob_size", uint64_t{0});
            out.souls[soul.id] = std::move(soul);
        }
    }
    if ((*it).contains("uploaded_resources") && (*it)["uploaded_resources"].is_object()) {
        for (auto r = (*it)["uploaded_resources"].begin(); r != (*it)["uploaded_resources"].end(); ++r) {
            if (!r.value().is_object()) continue;
            PlayerFarm::UploadedResource resource;
            resource.id = r.key();
            resource.resource_id = r.value().value("resource_id", std::string{});
            resource.resource_name = r.value().value("resource_name", resource.resource_id);
            resource.item_class = r.value().value("item_class", std::string{});
            resource.display_name = r.value().value("display_name", std::string{});
            resource.blob_file = r.value().value("blob_file", std::string{});
            resource.status = r.value().value("status", std::string("pending"));
            resource.uploaded_utc = r.value().value("uploaded_utc", int64_t{0});
            resource.blob_size = r.value().value("blob_size", uint64_t{0});
            resource.item_quantity = r.value().value("item_quantity", int64_t{1});
            out.uploaded_resources[resource.id] = std::move(resource);
        }
    }
    return out;
}

std::vector<std::string> FarmState::PlayerIds() {
    std::lock_guard<std::mutex> lock(mutex_);
    std::vector<std::string> ids;
    ids.reserve(data_.size());
    for (auto it = data_.begin(); it != data_.end(); ++it)
        if (it.value().is_object()) ids.push_back(it.key());
    return ids;
}

std::string FarmState::SoulDirectory(const std::string& steam_id) const {
    return ArkApi::Tools::GetCurrentDir() + "/ArkApi/Plugins/FazendaRecursos/data/souls/" + steam_id;
}
std::string FarmState::ResourceDirectory(const std::string& steam_id) const {
    return ArkApi::Tools::GetCurrentDir() + "/ArkApi/Plugins/FazendaRecursos/data/resources/" + steam_id;
}

bool FarmState::HasSoul(const std::string& steam_id, const std::string& species_blueprint) {
    std::lock_guard<std::mutex> lock(mutex_);
    const auto player = data_.find(steam_id);
    if (player == data_.end() || !player->contains("souls") || !(*player)["souls"].is_object()) return false;
    for (auto it = (*player)["souls"].begin(); it != (*player)["souls"].end(); ++it) {
        if (it.value().value("species_blueprint", std::string{}) == species_blueprint &&
            it.value().value("status", std::string{}) != "rolled_back") return true;
    }
    return false;
}

bool FarmState::AddPendingSoul(const std::string& steam_id, const PlayerFarm::UploadedSoul& soul) {
    if (steam_id.empty() || soul.id.empty() || soul.species_blueprint.empty() || soul.blob_file.empty()) return false;
    std::lock_guard<std::mutex> lock(mutex_);
    auto& player = data_[steam_id];
    if (!player.is_object()) player = nlohmann::json::object();
    auto& souls = player["souls"];
    if (!souls.is_object()) souls = nlohmann::json::object();
    for (auto it = souls.begin(); it != souls.end(); ++it)
        if (it.value().value("species_blueprint", std::string{}) == soul.species_blueprint &&
            it.value().value("status", std::string{}) != "rolled_back") return false;
    souls[soul.id] = {
        {"item_class", soul.item_class}, {"species_blueprint", soul.species_blueprint}, {"display_name", soul.display_name},
        {"blob_file", soul.blob_file}, {"status", "pending_consumption"},
        {"uploaded_utc", soul.uploaded_utc}, {"blob_size", soul.blob_size}
    };
    if (SaveLocked()) return true;
    souls.erase(soul.id);
    return false;
}

bool FarmState::CommitSoul(const std::string& steam_id, const std::string& soul_id) {
    std::lock_guard<std::mutex> lock(mutex_);
    auto player = data_.find(steam_id);
    if (player == data_.end() || !player->contains("souls") || !(*player)["souls"].contains(soul_id)) return false;
    auto& record = (*player)["souls"][soul_id];
    const auto old_status = record.value("status", std::string("pending_consumption"));
    record["status"] = "active";
    if (SaveLocked()) return true;
    record["status"] = old_status;
    return false;
}

bool FarmState::RemoveSoul(const std::string& steam_id, const std::string& soul_id) {
    std::lock_guard<std::mutex> lock(mutex_);
    auto player = data_.find(steam_id);
    if (player == data_.end() || !player->contains("souls") || !(*player)["souls"].contains(soul_id)) return false;
    auto old = (*player)["souls"][soul_id];
    (*player)["souls"].erase(soul_id);
    if (SaveLocked()) return true;
    (*player)["souls"][soul_id] = std::move(old);
    return false;
}

bool FarmState::HasActiveResource(const std::string& steam_id, const std::string& resource_id) {
    std::lock_guard<std::mutex> lock(mutex_);
    const auto player = data_.find(steam_id);
    if (player == data_.end() || !player->contains("resources") ||
        !(*player)["resources"].is_object() || !(*player)["resources"].contains(resource_id)) return false;
    return (*player)["resources"][resource_id].value("active", false);
}

bool FarmState::AddPendingResource(const std::string& steam_id, const PlayerFarm::UploadedResource& resource) {
    if (steam_id.empty() || resource.id.empty() || resource.resource_id.empty() || resource.blob_file.empty()) return false;
    std::lock_guard<std::mutex> lock(mutex_);
    auto& player = data_[steam_id];
    if (!player.is_object()) player = nlohmann::json::object();
    auto& uploads = player["uploaded_resources"];
    if (!uploads.is_object()) uploads = nlohmann::json::object();
    for (auto it = uploads.begin(); it != uploads.end(); ++it)
        if (it.value().value("resource_id", std::string{}) == resource.resource_id &&
            it.value().value("status", std::string{}) != "rolled_back") return false;
    uploads[resource.id] = {
        {"resource_id", resource.resource_id}, {"resource_name", resource.resource_name},
        {"item_class", resource.item_class},
        {"display_name", resource.display_name}, {"blob_file", resource.blob_file},
        {"status", "pending_consumption"}, {"uploaded_utc", resource.uploaded_utc},
        {"blob_size", resource.blob_size}, {"item_quantity", resource.item_quantity}
    };
    if (SaveLocked()) return true;
    uploads.erase(resource.id);
    return false;
}

bool FarmState::CommitResource(const std::string& steam_id, const std::string& resource_id,
                              const std::string& upload_id, int64_t now) {
    std::lock_guard<std::mutex> lock(mutex_);
    auto player = data_.find(steam_id);
    if (player == data_.end() || !player->contains("uploaded_resources") ||
        !(*player)["uploaded_resources"].contains(upload_id)) return false;
    auto& upload = (*player)["uploaded_resources"][upload_id];
    const auto old_status = upload.value("status", std::string("pending_consumption"));
    const bool had_resource = player->contains("resources") && (*player)["resources"].is_object() &&
                              (*player)["resources"].contains(resource_id);
    nlohmann::json old_resource = had_resource ? (*player)["resources"][resource_id] : nlohmann::json{};
    auto& state = (*player)["resources"][resource_id];
    if (!state.is_object()) state = nlohmann::json::object();
    state["stock"] = std::max<int64_t>(0, state.value("stock", int64_t{0}));
    state["last_accrual_utc"] = now;
    state["active"] = true;
    upload["status"] = "active";
    if (SaveLocked()) return true;
    upload["status"] = old_status;
    if (had_resource) (*player)["resources"][resource_id] = std::move(old_resource);
    else (*player)["resources"].erase(resource_id);
    return false;
}

bool FarmState::RemoveResource(const std::string& steam_id, const std::string& upload_id) {
    std::lock_guard<std::mutex> lock(mutex_);
    auto player = data_.find(steam_id);
    if (player == data_.end() || !player->contains("uploaded_resources") ||
        !(*player)["uploaded_resources"].contains(upload_id)) return false;
    auto old = (*player)["uploaded_resources"][upload_id];
    (*player)["uploaded_resources"].erase(upload_id);
    if (SaveLocked()) return true;
    (*player)["uploaded_resources"][upload_id] = std::move(old);
    return false;
}

bool FarmState::BeginResourceRestore(const std::string& steam_id, const std::string& upload_id) {
    std::lock_guard<std::mutex> lock(mutex_);
    auto player = data_.find(steam_id);
    if (player == data_.end() || !player->contains("uploaded_resources") ||
        !(*player)["uploaded_resources"].contains(upload_id)) return false;
    auto& row = (*player)["uploaded_resources"][upload_id];
    if (row.value("status", std::string{}) != "active") return false;
    row["status"] = "restoring";
    if (SaveLocked()) return true;
    row["status"] = "active";
    return false;
}

bool FarmState::FinishResourceRestore(const std::string& steam_id, const std::string& upload_id, bool restored) {
    std::lock_guard<std::mutex> lock(mutex_);
    auto player = data_.find(steam_id);
    if (player == data_.end() || !player->contains("uploaded_resources") ||
        !(*player)["uploaded_resources"].contains(upload_id)) return false;
    auto& row = (*player)["uploaded_resources"][upload_id];
    if (row.value("status", std::string{}) != "restoring") return false;
    row["status"] = restored ? "recovered" : "active";
    if (restored) {
        const auto resource_id = row.value("resource_id", std::string{});
        if (!resource_id.empty() && player->contains("resources") &&
            (*player)["resources"].is_object() && (*player)["resources"].contains(resource_id)) {
            auto& resource = (*player)["resources"][resource_id];
            resource["active"] = false;
            resource["stock"] = 0;
        }
    }
    if (SaveLocked()) return true;
    row["status"] = "restoring";
    return false;
}

bool FarmState::RollbackResourceUpload(const std::string& steam_id, const std::string& upload_id) {
    std::lock_guard<std::mutex> lock(mutex_);
    auto player = data_.find(steam_id);
    if (player == data_.end() || !player->contains("uploaded_resources") ||
        !(*player)["uploaded_resources"].contains(upload_id)) return false;
    auto& upload = (*player)["uploaded_resources"][upload_id];
    const auto old_upload = upload;
    const auto resource_id = upload.value("resource_id", std::string{});
    const bool had_resource = !resource_id.empty() && player->contains("resources") &&
        (*player)["resources"].is_object() && (*player)["resources"].contains(resource_id);
    const auto old_resource = had_resource ? (*player)["resources"][resource_id] : nlohmann::json{};
    upload["status"] = "rolled_back";
    if (had_resource) {
        (*player)["resources"][resource_id]["active"] = false;
        (*player)["resources"][resource_id]["stock"] = 0;
    }
    if (SaveLocked()) return true;
    upload = old_upload;
    if (had_resource) (*player)["resources"][resource_id] = old_resource;
    return false;
}
}
