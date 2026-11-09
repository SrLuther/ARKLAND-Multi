#include "FarmConfig.h"

namespace FazendaRecursos {
namespace {
nlohmann::json DefaultBaseResources() {
    return nlohmann::json::array({{
        {"Id", "element"}, {"Name", "Element"},
        {"ItemClass", "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_Element.PrimalItemResource_Element_C"},
        {"InputClass", "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_Element.PrimalItemResource_Element_C"},
        {"InputQuantity", 1}, {"OutputQuantity", 1}, {"IntervalSeconds", 3600},
        {"StackSize", 100}, {"Capacity", 200}, {"Enabled", true}
    }});
}

nlohmann::json DefaultOmegaResources() {
    const std::array<std::tuple<const char*, const char*, const char*, int>, 51> rows = {{
        {"omega_paragon_shard", "Paragon Shard", "Souls/PrimalItem_ParagonShard", 25},
        {"omega_soul_shard", "Soul Shard", "Souls/PrimalItem_SoulShard", 25},
        {"omega_chest_shard", "Chest Shard", "Souls/PrimalItem_ChestShard", 25},
        {"omega_paragon_soul", "Paragon Soul", "Souls/GodSouls/PrimalItem_SpeciesSoul", 1},
        {"omega_lucky_soul", "Lucky Soul", "Souls/PrimalItem_LuckySoul", 25},
        {"omega_paragon_breaker", "Paragon Breaker", "Souls/GodSouls/PrimalItem_ParagonBreaker", 1},
        {"omega_ancient_god_soul", "Ancient God Soul", "Souls/GodSouls/PrimalItem_AncientGodSoul", 1},
        {"omega_god_soul", "God Soul", "Souls/GodSouls/PrimalItem_GodSoul", 1},
        {"omega_group_god_soul", "Group God Soul", "Souls/GodSouls/PrimalItem_GroupGodSoul", 1},
        {"omega_unique_god_soul", "Unique God Soul", "Souls/GodSouls/PrimalItem_UniqueGodSoul", 1},
        {"omega_unique_group_god_soul", "Unique Group God Soul", "Souls/GodSouls/PrimalItem_UniqueGroupGodSoul", 1},
        {"omega_zodiac_soul", "Zodiac Soul", "Souls/GodSouls/PrimalItem_ZodiacSoul", 1},
        {"omega_perfect_soul", "Perfect Soul", "Souls/GodSouls/PrimalItem_PerfectSoul", 1},
        {"omega_darkness_soul", "Darkness Soul", "Souls/GodSouls/PrimalItem_DarknessSoul", 1},
        {"omega_perfect_soul_2", "Perfect Soul 2", "Souls/GodSouls/PrimalItem_PerfectSoul2", 1},
        {"omega_deity_soul", "Deity Soul", "Souls/GodSouls/PrimalItem_DeitySoul", 1},
        {"omega_endless_soul", "Endless Soul", "Souls/GodSouls/PrimalItem_EndlessSoul", 1},
        {"omega_unique_token", "Unique Token", "Souls/Tokens/PrimalItem_UniqueToken", 1},
        {"omega_unique_token_craftable", "Unique Token Craftable", "Souls/Tokens/PrimalItem_UniqueTokenCraftable", 1},
        {"omega_cosmic_soul", "Cosmic Soul", "Souls/PrimalItem_CosmicSoul", 25},
        {"omega_elemental_soul", "Elemental Soul", "Souls/PrimalItem_ElementalSoul", 25},
        {"omega_ethereal_soul", "Ethereal Soul", "Souls/PrimalItem_EtherealSoul", 25},
        {"omega_guardian_soul", "Guardian Soul", "Souls/PrimalItem_GuardianSoul", 25},
        {"omega_mythical_soul", "Mythical Soul", "Souls/PrimalItem_MythicalSoul", 25},
        {"omega_nature_soul", "Nature Soul", "Souls/PrimalItem_NatureSoul", 25},
        {"omega_nightmare_soul", "Nightmare Soul", "Souls/PrimalItem_NightmareSoul", 25},
        {"omega_rage_soul", "Rage Soul", "Souls/PrimalItem_RageSoul", 25},
        {"omega_resource_soul", "Resource Soul", "Souls/PrimalItem_ResourceSoul", 25},
        {"omega_summoner_soul", "Summoner Soul", "Souls/PrimalItem_SummonerSoul", 25},
        {"omega_unstable_soul", "Unstable Soul", "Souls/PrimalItem_UnstableSoul", 25},
        {"omega_utility_soul", "Utility Soul", "Souls/PrimalItem_UtilitySoul", 25},
        {"omega_basic_essence", "Basic Essence", "Essence/PrimalItem_BasicEssence", 25},
        {"omega_beta_essence", "Beta Essence", "Essence/PrimalItem_BetaEssence", 25},
        {"omega_alpha_essence", "Alpha Essence", "Essence/PrimalItem_AlphaEssence", 25},
        {"omega_prime_essence", "Prime Essence", "Essence/PrimalItem_PrimeEssence", 25},
        {"omega_ultimate_essence", "Ultimate Essence", "Essence/PrimalItem_UltimateEssence", 25},
        {"omega_omega_essence", "Omega Essence", "Essence/PrimalItem_OmegaEssence", 25},
        {"omega_god_essence", "God Essence", "Essence/PrimalItem_GodEssence", 25},
        {"omega_ancient_essence", "Ancient Essence", "Essence/PrimalItem_AncientEssence", 25},
        {"omega_boss_essence", "Boss Essence", "Essence/PrimalItem_BossEssence", 25},
        {"omega_souls", "Souls", "Souls/PrimalItem_Souls", 25},
        {"omega_boss_soul", "Boss Soul", "Souls/GodSouls/PrimalItem_BossSoul", 1},
        {"omega_omega_soul", "Omega Soul", "Souls/GodSouls/PrimalItem_OmegaSoul", 1},
        {"omega_alpha_unique_token", "Alpha Unique Token", "Souls/Tokens/PrimalItem_AlphaUniqueToken", 1},
        {"omega_ancient_god_token", "Ancient God Token", "Souls/Tokens/PrimalItem_AncientGodToken", 1},
        {"omega_beta_unique_token", "Beta Unique Token", "Souls/Tokens/PrimalItem_BetaUniqueToken", 1},
        {"omega_omega_unique_token", "Omega Unique Token", "Souls/Tokens/PrimalItem_OmegaUniqueToken", 1},
        {"omega_prime_unique_token", "Prime Unique Token", "Souls/Tokens/PrimalItem_PrimeUniqueToken", 1},
        {"omega_ultimate_unique_token", "Ultimate Unique Token", "Souls/Tokens/PrimalItem_UltimateUniqueToken", 1},
        {"omega_unique_god_token", "Unique God Token", "Souls/Tokens/PrimalItem_UniqueGodToken", 1},
        {"omega_unique_saddle_token", "Unique Saddle Token", "Gamble/PrimalItem_UniqueSaddleToken", 1},
    }};
    nlohmann::json resources = nlohmann::json::array();
    for (const auto& [id, name, asset, stack_size] : rows) {
        const std::string asset_path = asset;
        const auto slash = asset_path.find_last_of('/');
        const std::string asset_name = slash == std::string::npos
            ? asset_path : asset_path.substr(slash + 1);
        const std::string item_class = std::string(
            "/Game/Mods/2447186973/Items/") + asset_path + "." + asset_name + "_C";
        resources.push_back({
            {"Id", id}, {"Name", name}, {"ItemClass", item_class},
            {"InputClass", item_class}, {"InputQuantity", 1},
            {"OutputQuantity", 1}, {"IntervalSeconds", 3600},
            {"StackSize", stack_size},
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
    if (!categories.contains("default")) {
        categories["default"] = {{"Enabled", true}, {"Required", true},
            {"DisplayName", "Recursos do jogo base"}, {"Resources", nlohmann::json::array()}};
        changed = true;
    }
    auto& base = categories["default"];
    if (!base.is_object()) throw std::runtime_error("Categories.default precisa ser objeto");
    if (!base.contains("Enabled")) { base["Enabled"] = true; changed = true; }
    if (!base.contains("Required")) { base["Required"] = true; changed = true; }
    if (!base.contains("DisplayName")) { base["DisplayName"] = "Recursos do jogo base"; changed = true; }
    if (!base.contains("Resources")) { base["Resources"] = nlohmann::json::array(); changed = true; }
    if (!base["Resources"].is_array())
        throw std::runtime_error("Categories.default.Resources precisa ser array");
    std::set<std::string> known_base;
    for (const auto& row : base["Resources"])
        if (row.is_object() && row.contains("Id") && row["Id"].is_string())
            known_base.insert(row["Id"].get<std::string>());
    for (const auto& resource : DefaultBaseResources()) {
        const auto id = resource["Id"].get<std::string>();
        if (!known_base.contains(id)) { base["Resources"].push_back(resource); changed = true; }
    }
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
    for (auto category = categories.begin(); category != categories.end(); ++category) {
        if (!category.value().is_object() || !category.value().contains("Resources") ||
            !category.value()["Resources"].is_array()) continue;
        for (auto& resource : category.value()["Resources"]) {
            if (resource.is_object() && !resource.contains("StackSize")) {
                resource["StackSize"] = 25;
                changed = true;
            }
        }
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
    const auto target_path = std::filesystem::path(path).wstring();
    if (!MoveFileExW(temp_path.c_str(), target_path.c_str(),
            MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        const DWORD replace_error = GetLastError();
        // Some server directories grant write access to config files but deny
        // deleting/replacing them. Preserve the original, then try copying the
        // fully flushed migration file over it (same-folder backup first).
        const auto backup_path = target_path + L".farm-migration." +
            std::to_wstring(GetTickCount64()) + L".bak";
        if (CopyFileW(target_path.c_str(), backup_path.c_str(), TRUE)) {
            if (CopyFileW(temp_path.c_str(), target_path.c_str(), FALSE)) {
                DeleteFileW(temp_path.c_str());
                Log::GetLog()->warn("FazendaRecursos: config.json migrado por cópia com backup; MoveFileExW={} backup={}",
                    replace_error, std::filesystem::path(backup_path).string());
                return true;
            }
            const DWORD copy_error = GetLastError();
            Log::GetLog()->error("FazendaRecursos: falha ao substituir config.json migrado (MoveFileExW={}, CopyFileW={}); backup preservado em {}",
                replace_error, copy_error, std::filesystem::path(backup_path).string());
        } else {
            const DWORD backup_error = GetLastError();
            Log::GetLog()->error("FazendaRecursos: falha ao substituir config.json migrado (MoveFileExW={}, backup CopyFileW={}); config={} temp={}",
                replace_error, backup_error, path, std::filesystem::path(temp_path).string());
        }
        std::error_code ec;
        std::filesystem::remove(temp_path, ec);
        Log::GetLog()->error("FazendaRecursos: padrões ficam ativos somente em memória; verifique permissões/arquivo em uso no config.json");
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
    share_key_ = std::move(candidate.share_key_);
    admin_groups_ = std::move(candidate.admin_groups_);
    resources_ = std::move(candidate.resources_);
}

bool FarmConfig::ApplyRemoteConfig(const nlohmann::json& config) {
    if (!config.is_object() || !config.contains("FazendaRecursos") ||
        !config["FazendaRecursos"].is_object()) return false;
    const auto remote_share = FRJsonString(config["FazendaRecursos"], "FarmShareKey", "default");
    if (remote_share != ShareKey()) return false;
    auto mirror = config;
    mirror["FazendaRecursos"]["ServerId"] = ServerId();
    mirror["FazendaRecursos"]["ManagedByWeb"] = true;
    const std::string path = ArkApi::Tools::GetCurrentDir() +
        "/ArkApi/Plugins/FazendaRecursos/config.json";
    std::string previous;
    {
        std::ifstream in(path, std::ios::binary);
        if (in) previous.assign(std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>());
    }
    const auto temp_path = std::filesystem::path(path).wstring() + L".sync.tmp";
    {
        std::ofstream out(temp_path, std::ios::binary | std::ios::trunc);
        if (!out) return false;
        const auto serialized = mirror.dump(2);
        out.write(serialized.data(), static_cast<std::streamsize>(serialized.size()));
        out.flush();
        if (!out) return false;
    }
    if (!MoveFileExW(temp_path.c_str(), std::filesystem::path(path).wstring().c_str(),
            MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        std::error_code ec;
        std::filesystem::remove(temp_path, ec);
        return false;
    }
    try {
        Reload();
        Log::GetLog()->info("Fazenda: config.json sincronizado com a configuração mestre do site (server={})",
            ServerId());
        return true;
    } catch (const std::exception& e) {
        if (!previous.empty()) {
            const auto restore_path = std::filesystem::path(path).wstring() + L".restore.tmp";
            std::ofstream restore(restore_path, std::ios::binary | std::ios::trunc);
            restore.write(previous.data(), static_cast<std::streamsize>(previous.size()));
            restore.flush();
            restore.close();
            MoveFileExW(restore_path.c_str(), std::filesystem::path(path).wstring().c_str(),
                MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH);
        }
        Log::GetLog()->error("Fazenda: configuração mestre rejeitada; config.json anterior restaurado ({})", e.what());
        return false;
    }
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
    share_key_ = FRJsonString(root_, "FarmShareKey", "default");
    if (share_key_.empty() || share_key_.size() > 64) share_key_ = "default";
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
            if (r.input_quantity != 1)
                throw std::runtime_error("InputQuantity deve ser 1 para uploads da Fazenda");
            r.output_quantity = std::max(1, FRJsonInt(row, "OutputQuantity", 1));
            r.interval_seconds = std::max(1, FRJsonInt(row, "IntervalSeconds", 3600));
            r.stack_size = std::clamp(FRJsonInt(row, "StackSize", 25), 1, 1000000);
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
    std::lock_guard<std::mutex> lock(resources_mutex_);
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

std::string FarmConfig::ShareKey() const {
    std::lock_guard<std::mutex> lock(resources_mutex_);
    return share_key_;
}
}
