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
    if (it == data_.end() || !(*it).contains("resources") || !(*it)["resources"].is_object()) return out;
    for (auto r = (*it)["resources"].begin(); r != (*it)["resources"].end(); ++r) {
        PlayerResource value;
        value.stock = std::max<int64_t>(0, r.value().value("stock", int64_t{0}));
        value.last_accrual_utc = r.value().value("last_accrual_utc", int64_t{0});
        value.active = r.value().value("active", false);
        out.resources[r.key()] = value;
    }
    return out;
}
}
