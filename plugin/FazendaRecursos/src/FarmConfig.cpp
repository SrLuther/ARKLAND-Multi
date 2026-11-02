#include "FarmConfig.h"

namespace FazendaRecursos {
namespace {
nlohmann::json DefaultOmegaResources() {
    const std::array<std::tuple<const char*, const char*, const char*>, 3> rows = {{
        {"omega_paragon_shard", "Paragon Shard", "PrimalItem_ParagonShard"},
        {"omega_soul_shard", "Soul Shard", "PrimalItem_SoulShard"},
        {"omega_chest_shard", "Chest Shard", "PrimalItem_ChestShard"},
    }};
    nlohmann::json resources = nlohmann::json::array();
    for (const auto& [id, name, asset] : rows) {
        const std::string item_class = std::string(
            "/Game/Mods/ArkOmega/Items/Souls/") + asset + "." + asset + "_C";
        resources.push_back({
            {"Id", id}, {"Name", name}, {"ItemClass", item_class},
            {"InputClass", item_class}, {"InputQuantity", 1},
            {"OutputQuantity", 1}, {"IntervalSeconds", 3600},
            {"Capacity", 200}, {"Enabled", true}
        });
    }
    return resources;
}

bool MigrateFarmDefaults(nlohmann::json& full, nlohmann::json& root,
                         const std::string& path) {
    bool changed = false;
    auto& categories = root["Categories"];
    if (!categories.is_object())
        throw std::runtime_error("Categories precisa ser objeto");
    if (!categories.contains("omega")) {
        categories["omega"] = {{"Enabled", true}, {"Required", false},
            {"DisplayName", "ARK Omega"}, {"Resources", nlohmann::json::array()}};
        changed = true;
    }
    auto& omega = categories["omega"];
    if (!omega.is_object()) throw std::runtime_error("Categories.omega precisa ser objeto");
    if (!omega.contains("Enabled")) { omega["Enabled"] = true; changed = true; }
    if (!omega.contains("Required")) { omega["Required"] = false; changed = true; }
    if (!omega.contains("DisplayName")) { omega["DisplayName"] = "ARK Omega"; changed = true; }
    if (!omega.contains("Resources")) { omega["Resources"] = nlohmann::json::array(); changed = true; }
    if (!omega["Resources"].is_array())
        throw std::runtime_error("Categories.omega.Resources precisa ser array");
    std::set<std::string> known;
    for (const auto& row : omega["Resources"])
        if (row.is_object() && row.contains("Id") && row["Id"].is_string())
            known.insert(row["Id"].get<std::string>());
    for (const auto& resource : DefaultOmegaResources()) {
        const auto id = resource["Id"].get<std::string>();
        if (!known.contains(id)) { omega["Resources"].push_back(resource); changed = true; }
    }
    if (!root.contains("SyncIntervalSeconds")) { root["SyncIntervalSeconds"] = 60; changed = true; }
    if (!root.contains("ServerId")) { root["ServerId"] = "default"; changed = true; }
    if (!changed) return false;
    full["FazendaRecursos"] = root;
    const auto temp_path = std::filesystem::path(path).wstring() + L".tmp";
    {
        std::ofstream out(temp_path, std::ios::binary | std::ios::trunc);
        if (!out) {
            Log::GetLog()->error("FazendaRecursos: não foi possível gravar config.json migrado; padrões ficam ativos somente em memória");
            return false;
        }
        const auto serialized = full.dump(2);
        out.write(serialized.data(), static_cast<std::streamsize>(serialized.size()));
        out.flush();
        if (!out) {
            Log::GetLog()->error("FazendaRecursos: falha ao persistir config.json migrado; padrões ficam ativos somente em memória");
            return false;
        }
    }
    if (!MoveFileExW(temp_path.c_str(), std::filesystem::path(path).wstring().c_str(),
            MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        std::error_code ec;
        std::filesystem::remove(temp_path, ec);
        Log::GetLog()->error("FazendaRecursos: falha ao substituir config.json migrado; padrões ficam ativos somente em memória");
        return false;
    }
    return true;
}
}

FarmConfig& FarmConfig::Get() { static FarmConfig value; return value; }

void FarmConfig::Reload() {
    FarmConfig candidate;
    candidate.Load(); // parse/validate completely before replacing live settings
    std::lock_guard<std::mutex> lock(resources_mutex_);
    root_ = std::move(candidate.root_);
    messages_ = std::move(candidate.messages_);
    enabled_ = candidate.enabled_;
    license_group_ = std::move(candidate.license_group_);
    tick_seconds_ = candidate.tick_seconds_;
    preview_lifetime_seconds_ = candidate.preview_lifetime_seconds_;
    initial_capacity_ = candidate.initial_capacity_;
    sync_interval_seconds_ = candidate.sync_interval_seconds_;
    server_id_ = std::move(candidate.server_id_);
    admin_groups_ = std::move(candidate.admin_groups_);
    resources_ = std::move(candidate.resources_);
}

void FarmConfig::Load() {
    const std::string path = ArkApi::Tools::GetCurrentDir() +
        "/ArkApi/Plugins/FazendaRecursos/config.json";
    std::ifstream in(path);
    if (!in) throw std::runtime_error("config.json não encontrado: " + path);
    nlohmann::json full;
    in >> full;
    root_ = full.value("FazendaRecursos", nlohmann::json::object());
    if (!root_.is_object()) throw std::runtime_error("FazendaRecursos precisa ser objeto");
    const bool migrated = MigrateFarmDefaults(full, root_, path);
    if (migrated) Log::GetLog()->info("FazendaRecursos: config.json migrado sem remover configurações existentes");
    enabled_ = FRJsonBool(root_, "Enabled", true);
    license_group_ = FRJsonString(root_, "LicenseGroup", "keyfarm");
    if (license_group_.empty() || license_group_ == "keyvault")
        throw std::runtime_error("LicenseGroup deve ser keyfarm e não pode reutilizar keyvault");
    initial_capacity_ = std::clamp(FRJsonInt(root_, "InitialCapacityPerResource", 200), 1, 1000000);
    tick_seconds_ = std::clamp(FRJsonInt(root_, "TickSeconds", 60), 10, 3600);
    sync_interval_seconds_ = std::clamp(FRJsonInt(root_, "SyncIntervalSeconds", 60), 30, 600);
    server_id_ = FRJsonString(root_, "ServerId", "default");
    if (server_id_.empty() || server_id_.size() > 64) server_id_ = "default";
    preview_lifetime_seconds_ = std::clamp(FRJsonInt(root_, "PreviewLifetimeSeconds", 120), 15, 600);
    messages_ = root_.value("Messages", nlohmann::json::object());
    admin_groups_.clear();
    auto groups = root_.value("DiagnosticAdminGroups", nlohmann::json::array());
    if (groups.is_array()) for (const auto& g : groups)
        if (g.is_string() && !g.get<std::string>().empty()) admin_groups_.push_back(g.get<std::string>());
    resources_.clear();
    const auto categories = root_.value("Categories", nlohmann::json::object());
    if (!categories.is_object()) throw std::runtime_error("Categories precisa ser objeto");
    for (auto it = categories.begin(); it != categories.end(); ++it) {
        const std::string category = it.key();
        const auto& cat = it.value();
        const bool required = category == "default";
        if (required && !FRJsonBool(cat, "Enabled", true))
            throw std::runtime_error("A categoria default não pode ser desativada");
        const bool category_enabled = required || FRJsonBool(cat, "Enabled", false);
        const auto list = cat.value("Resources", nlohmann::json::array());
        if (!list.is_array()) continue;
        for (const auto& row : list) {
            if (!row.is_object()) continue;
            ResourceDefinition r;
            r.category = category;
            r.id = FRJsonString(row, "Id");
            r.name = FRJsonString(row, "Name", r.id);
            r.item_class = FRJsonString(row, "ItemClass");
            r.input_class = FRJsonString(row, "InputClass");
            r.input_quantity = std::max(1, FRJsonInt(row, "InputQuantity", 1));
            r.output_quantity = std::max(1, FRJsonInt(row, "OutputQuantity", 1));
            r.interval_seconds = std::max(1, FRJsonInt(row, "IntervalSeconds", 3600));
            r.capacity = std::max(1, FRJsonInt(row, "Capacity", initial_capacity_));
            r.enabled = category_enabled && FRJsonBool(row, "Enabled", false);
            if (r.id.empty() || r.item_class.empty()) {
                Log::GetLog()->warn("FazendaRecursos: ignorando recurso sem Id ou ItemClass (categoria={})", category);
                continue;
            }
            resources_.push_back(std::move(r));
        }
    }
    Log::GetLog()->info("FazendaRecursos: {} recurso(s) carregado(s); {} habilitado(s)",
        resources_.size(), std::count_if(resources_.begin(), resources_.end(), [](const auto& r){return r.enabled;}));
}

std::string FarmConfig::Message(const std::string& key, const std::string& fallback) const {
    std::string value = fallback;
    if (messages_.contains(key) && messages_[key].is_string()) value = messages_[key].get<std::string>();
    const std::pair<const char*, const char*> repairs[] = {
        {"Ã¡", "á"}, {"Ã£", "ã"}, {"Ã©", "é"}, {"Ã­", "í"},
        {"Ã³", "ó"}, {"Ãº", "ú"}, {"Ã§", "ç"}, {"Ãª", "ê"},
        {"Ãµ", "õ"}, {"Ã‰", "É"}, {"Ã“", "Ó"}, {"Ã€", "À"}, {"Ã¢", "â"}
    };
    for (const auto& [broken, correct] : repairs) {
        size_t at = 0;
        while ((at = value.find(broken, at)) != std::string::npos) {
            value.replace(at, std::char_traits<char>::length(broken), correct);
            at += std::char_traits<char>::length(correct);
        }
    }
    return value;
}

std::vector<ResourceDefinition> FarmConfig::ResourcesSnapshot() const {
    std::lock_guard<std::mutex> lock(resources_mutex_);
    return resources_;
}

int FarmConfig::SyncIntervalSeconds() const {
    std::lock_guard<std::mutex> lock(resources_mutex_);
    return sync_interval_seconds_;
}

std::string FarmConfig::ServerId() const {
    std::lock_guard<std::mutex> lock(resources_mutex_);
    return server_id_;
}
}
