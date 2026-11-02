#include "FarmConfig.h"

namespace FazendaRecursos {
FarmConfig& FarmConfig::Get() { static FarmConfig value; return value; }

void FarmConfig::Reload() {
    FarmConfig candidate;
    candidate.Load(); // parse/validate completely before replacing live settings
    root_ = std::move(candidate.root_);
    messages_ = std::move(candidate.messages_);
    enabled_ = candidate.enabled_;
    license_group_ = std::move(candidate.license_group_);
    tick_seconds_ = candidate.tick_seconds_;
    preview_lifetime_seconds_ = candidate.preview_lifetime_seconds_;
    initial_capacity_ = candidate.initial_capacity_;
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
    enabled_ = FRJsonBool(root_, "Enabled", true);
    license_group_ = FRJsonString(root_, "LicenseGroup", "keyfarm");
    if (license_group_.empty() || license_group_ == "keyvault")
        throw std::runtime_error("LicenseGroup deve ser keyfarm e não pode reutilizar keyvault");
    initial_capacity_ = std::clamp(FRJsonInt(root_, "InitialCapacityPerResource", 200), 1, 1000000);
    tick_seconds_ = std::clamp(FRJsonInt(root_, "TickSeconds", 60), 10, 3600);
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
    if (messages_.contains(key) && messages_[key].is_string()) return messages_[key].get<std::string>();
    return fallback;
}
}
