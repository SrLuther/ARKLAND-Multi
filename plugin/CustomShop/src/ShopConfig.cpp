#include "pch.h"
#include "ShopConfig.h"
#include "ShopDebug.h"

namespace CustomShop {

namespace {

const char* kSharedCatalogKeys[] = {
    "Items",
    "ShopItems",
    "Kits",
    "TimedPointsReward",
    "Messages",
    "Downloads",
    "PointPackages",
    "FeaturedMaps",
    // CrossChat: merged specially (ServerId from local)
};

} // namespace

ShopConfig& ShopConfig::Get() {
    static ShopConfig instance;
    return instance;
}

std::string ShopConfig::DefaultLocalConfigPath() {
    return ArkApi::Tools::GetCurrentDir() +
           "/ArkApi/Plugins/CustomShop/config.json";
}

bool ShopConfig::FileStamp(const std::string& path, int64_t& mtime, uint64_t& size) {
    WIN32_FILE_ATTRIBUTE_DATA fad{};
    if (!GetFileAttributesExA(path.c_str(), GetFileExInfoStandard, &fad)) {
        mtime = 0;
        size = 0;
        return false;
    }
    ULARGE_INTEGER t{};
    t.LowPart = fad.ftLastWriteTime.dwLowDateTime;
    t.HighPart = fad.ftLastWriteTime.dwHighDateTime;
    mtime = static_cast<int64_t>(t.QuadPart);
    ULARGE_INTEGER s{};
    s.LowPart = fad.nFileSizeLow;
    s.HighPart = fad.nFileSizeHigh;
    size = s.QuadPart;
    return true;
}

bool ShopConfig::ReadJsonFile(const std::string& path, nlohmann::json& out, std::string& err) {
    std::ifstream file(path);
    if (!file.is_open()) {
        err = "Cannot open: " + path;
        return false;
    }
    try {
        file >> out;
    } catch (const nlohmann::json::exception& e) {
        err = std::string("parse error (") + path + "): " + e.what();
        return false;
    }
    return true;
}

bool ShopConfig::IsSharedCatalogKey(const std::string& key) {
    for (const char* k : kSharedCatalogKeys) {
        if (key == k) return true;
    }
    return false;
}

std::string ShopConfig::ResolveSharedPath(const nlohmann::json& local) {
    // 1) Env override (ops / emergência)
    char env_buf[MAX_PATH * 2] = {};
    const DWORD env_n = GetEnvironmentVariableA(
        "ARKLAND_CUSTOMSHOP_CATALOG", env_buf, static_cast<DWORD>(sizeof(env_buf)));
    if (env_n > 0 && env_n < sizeof(env_buf)) {
        std::string from_env(env_buf, env_n);
        if (!from_env.empty())
            return from_env;
    }

    // 2) Campo no config local (TEK preenche no deploy/sync)
    if (local.is_object()) {
        if (local.contains("SharedCatalogPath") && local["SharedCatalogPath"].is_string()) {
            const std::string p = local["SharedCatalogPath"].get<std::string>();
            if (!p.empty()) return p;
        }
        if (local.contains("shared_catalog_path") && local["shared_catalog_path"].is_string()) {
            const std::string p = local["shared_catalog_path"].get<std::string>();
            if (!p.empty()) return p;
        }
    }
    return {};
}

nlohmann::json ShopConfig::MergeLocalOverShared(
    const nlohmann::json& shared,
    const nlohmann::json& local) {
    nlohmann::json merged = shared.is_object() ? shared : nlohmann::json::object();
    if (!local.is_object())
        return merged;

    // Catálogo partilhado vence em Items/Kits/… — não deep-merge por ID.
    for (auto it = local.begin(); it != local.end(); ++it) {
        const std::string& key = it.key();
        if (key == "SharedCatalogPath" || key == "shared_catalog_path" ||
            key == "shared_config_path") {
            continue;
        }
        if (IsSharedCatalogKey(key))
            continue;

        if (key == "CrossChat") {
            nlohmann::json cc = merged.value("CrossChat", nlohmann::json::object());
            if (it.value().is_object()) {
                for (auto cit = it.value().begin(); cit != it.value().end(); ++cit) {
                    cc[cit.key()] = cit.value();
                }
            }
            merged["CrossChat"] = std::move(cc);
            continue;
        }

        if (key == "Settings") {
            nlohmann::json st = merged.value("Settings", nlohmann::json::object());
            if (it.value().is_object()) {
                for (auto sit = it.value().begin(); sit != it.value().end(); ++sit) {
                    st[sit.key()] = sit.value();
                }
            }
            merged["Settings"] = std::move(st);
            continue;
        }

        // Database, Debug, e quaisquer extras locais
        merged[key] = it.value();
    }
    return merged;
}

void ShopConfig::ApplyMergedConfig(nlohmann::json merged) {
    config_ = std::move(merged);

    if (config_.contains("Items"))
        items_ = config_.at("Items");
    else if (config_.contains("ShopItems"))
        items_ = config_.at("ShopItems");
    else
        items_ = nlohmann::json::object();
    kits_          = config_.value("Kits",              nlohmann::json::object());
    settings_      = config_.value("Settings",          nlohmann::json::object());
    db_cfg_        = config_.value("Database",          nlohmann::json::object());
    timed_points_  = config_.value("TimedPointsReward", nlohmann::json::object());
    cross_chat_    = config_.value("CrossChat",         nlohmann::json::object());
    debug_cfg_     = config_.value("Debug",             nlohmann::json::object());

    if (!config_.contains("Debug")) {
        debug_cfg_ = {
            {"Enabled", false},
            {"Level", "INFO"},
            {"Categories", nlohmann::json::array({"*"})},
            {"RingBufferSize", 500},
            {"MaxFileBytes", 10485760},
            {"MaxFiles", 5},
            {"MySqlPersist", true},
            {"MySqlMinLevel", "WARN"},
            {"MySqlCategories", nlohmann::json::array({
                "TribeSync", "Http", "MySQL", "License", "Permissions", "Identity"})}
        };
    }
    Debug::Configure(debug_cfg_);
}

void ShopConfig::CaptureStamps() {
    stamps_valid_ = FileStamp(local_path_, local_mtime_, local_size_);
    if (using_shared_ && !shared_path_.empty()) {
        int64_t sm = 0;
        uint64_t ss = 0;
        if (FileStamp(shared_path_, sm, ss)) {
            shared_mtime_ = sm;
            shared_size_ = ss;
        } else {
            shared_mtime_ = 0;
            shared_size_ = 0;
        }
    } else {
        shared_mtime_ = 0;
        shared_size_ = 0;
    }
}

void ShopConfig::Load() {
    local_path_ = DefaultLocalConfigPath();
    shared_path_.clear();
    using_shared_ = false;

    nlohmann::json local;
    std::string err;
    if (!ReadJsonFile(local_path_, local, err))
        throw std::runtime_error(err);

    const std::string shared_candidate = ResolveSharedPath(local);
    nlohmann::json merged;

    if (!shared_candidate.empty()) {
        nlohmann::json shared;
        std::string shared_err;
        if (ReadJsonFile(shared_candidate, shared, shared_err)) {
            shared_path_ = shared_candidate;
            using_shared_ = true;
            merged = MergeLocalOverShared(shared, local);
            Log::GetLog()->info(
                "ShopConfig: shared catalog OK → {}", shared_path_);
        } else {
            Log::GetLog()->warn(
                "ShopConfig: SharedCatalogPath inválido/ausente ({}), fallback monolítico local — {}",
                shared_candidate, shared_err);
            merged = local;
        }
    } else {
        merged = local;
        Log::GetLog()->info(
            "ShopConfig: sem SharedCatalogPath — modo legado (tudo no config local)");
    }

    ApplyMergedConfig(std::move(merged));
    CaptureStamps();

    Log::GetLog()->info(
        "ShopConfig: loaded ({} items, {} kits, shared={}, DeliverDinosInCryopods={})",
        items_.size(), kits_.size(),
        using_shared_ ? "yes" : "no",
        settings_.value("DeliverDinosInCryopods", true));

    const bool tp_enabled = timed_points_.value("Enabled", false);
    const int tp_interval = timed_points_.value("Interval", 30);
    const auto& tp_groups = timed_points_.value("Groups", nlohmann::json::object());
    std::string grp_summary;
    for (const auto& [name, val] : tp_groups.items()) {
        const int amt = val.value("Amount", 0);
        if (amt <= 0) continue;
        if (!grp_summary.empty()) grp_summary += ", ";
        grp_summary += name + "=" + std::to_string(amt);
    }
    Log::GetLog()->info(
        "ShopConfig: TimedPointsReward enabled={} interval={}min groups=[{}]",
        tp_enabled ? "yes" : "no",
        tp_interval,
        grp_summary.empty() ? "(none)" : grp_summary);

    Log::GetLog()->info(
        "ShopConfig: chat commands /engramas price={} /notas enabled={} price={}",
        settings_.value("EngramasCommandPrice", 5000),
        settings_.value("NotasCommandEnabled", true) ? "yes" : "no",
        settings_.value("NotasCommandPrice", 5000));
}

bool ShopConfig::MaybeReloadIfChanged() {
    if (local_path_.empty())
        local_path_ = DefaultLocalConfigPath();

    int64_t lm = 0;
    uint64_t ls = 0;
    const bool local_ok = FileStamp(local_path_, lm, ls);

    // Re-ler path do shared a partir do local sem parse completo: se stamps
    // válidos e ficheiros iguais, skip. Se local mudou, Load() completo.
    int64_t sm = shared_mtime_;
    uint64_t ss = shared_size_;
    bool shared_changed = false;
    if (using_shared_ && !shared_path_.empty()) {
        int64_t cur_sm = 0;
        uint64_t cur_ss = 0;
        if (!FileStamp(shared_path_, cur_sm, cur_ss) ||
            cur_sm != shared_mtime_ || cur_ss != shared_size_) {
            shared_changed = true;
        }
        sm = cur_sm;
        ss = cur_ss;
        (void)sm;
        (void)ss;
    }

    const bool local_changed =
        !stamps_valid_ || !local_ok || lm != local_mtime_ || ls != local_size_;

    if (!local_changed && !shared_changed)
        return false;

    Load();
    return true;
}

int ShopConfig::StartingPoints() const {
    return settings_.value("StartingPoints", 0);
}

std::string ShopConfig::ShopName() const {
    return settings_.value("ShopName", "ARKLAND Shop");
}

std::string ShopConfig::UiKey() const {
    return settings_.value("UiKey", "F3");
}

std::string ShopConfig::WebApiUrl() const {
    return settings_.value("WebApiUrl", "http://127.0.0.1:5177");
}

std::string ShopConfig::WebApiKey() const {
    return settings_.value("WebApiKey", "");
}

bool ShopConfig::DisableSell() const {
    return settings_.value("DisableSellButton", true);
}

bool ShopConfig::DisableTrade() const {
    return settings_.value("DisableTradeButton", true);
}

bool ShopConfig::CloudEnabled() const {
    return settings_.value("CloudInventoryEnabled", true);
}

int ShopConfig::CloudMaxItems() const {
    return settings_.value("CloudMaxItems", 250);
}

int ShopConfig::CloudCooldownSeconds() const {
    return settings_.value("CloudCooldownSeconds", 30);
}

bool ShopConfig::CloudRequireLicenseForDownload() const {
    return settings_.value("CloudRequireLicenseForDownload", false);
}

std::string ShopConfig::WebsiteUrl() const {
    return settings_.value("WebsiteUrl", "");
}

bool ShopConfig::DeliverDinosInCryopods() const {
    return settings_.value("DeliverDinosInCryopods", true);
}

std::string ShopConfig::CryoItemPath() const {
    return settings_.value(
        "CryoItemPath",
        "Blueprint'/Game/Extinction/CoreBlueprints/Weapons/"
        "PrimalItem_WeaponEmptyCryopod.PrimalItem_WeaponEmptyCryopod'");
}

bool ShopConfig::CryoLimitedTime() const {
    return settings_.value("CryoLimitedTime", false);
}

bool ShopConfig::MarketCryoDebug() const {
    return settings_.value("MarketCryoDebug", false);
}

float ShopConfig::MarketCryoMinDaysRemaining() const {
    return settings_.value("MarketCryoMinDaysRemaining", 20.f);
}

bool ShopConfig::MarketCryoRequireMinDays() const {
    return settings_.value("MarketCryoRequireMinDays", false);
}

int ShopConfig::EngramasCommandPrice() const {
    return settings_.value("EngramasCommandPrice", 5000);
}

int ShopConfig::NotasCommandPrice() const {
    return settings_.value("NotasCommandPrice", 5000);
}

bool ShopConfig::NotasCommandEnabled() const {
    return settings_.value("NotasCommandEnabled", true);
}

bool ShopConfig::MarketDeliverAsSpawn() const {
    return settings_.value("MarketDeliverAsSpawn", true);
}

bool ShopConfig::MarketAssignNewDinoId() const {
    return settings_.value("MarketAssignNewDinoId", true);
}

std::string ShopConfig::MarketSpawnBonusSoulTrapBlueprint() const {
    return settings_.value(
        "MarketSpawnBonusSoulTrapBlueprint",
        "Blueprint'/Game/Mods/DinoStorage2/SoulTraps_DS.SoulTraps_DS'");
}

std::string ShopConfig::DbHost() const {
    return db_cfg_.value("Host", "127.0.0.1");
}
int ShopConfig::DbPort() const {
    return db_cfg_.value("Port", 3306);
}
std::string ShopConfig::DbUser() const {
    return db_cfg_.value("User", "arkland");
}
std::string ShopConfig::DbPassword() const {
    return db_cfg_.value("Password", "");
}
std::string ShopConfig::DbDatabase() const {
    return db_cfg_.value("Database", "arkland_shop");
}

} // namespace CustomShop
