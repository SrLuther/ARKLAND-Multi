#include "pch.h"
#include "ShopEntitlements.h"
#include "ShopBridge.h"
#include "ShopPerms.h"
#include "ShopDebug.h"
#include "ShopPoints.h"

#include <cctype>
#include <sstream>

namespace {

std::string ToLowerAsciiLocal(std::string value) {
    for (char& ch : value)
        ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
    return value;
}

/** SKU `licenca_delta` / alias → PermissionGroup canónico (`Delta`). */
std::string NormalizeEntitlementGroup(const std::string& group) {
    if (group.empty()) return group;
    for (const char* g : CustomShop::kPaidLicenseGroups) {
        if (group == g) return group;
    }
    if (group == "keyvault" || group == "Moderacao" || group == "STAFF"
        || group == "Default" || group == "Admins") {
        return group;
    }
    if (group == "Mod" || group == "MOD") return "Moderacao";

    const std::string lower = ToLowerAsciiLocal(group);
    std::string suffix = lower;
    if (suffix.rfind("licenca_", 0) == 0) {
        suffix = suffix.substr(8);
        static const char kRenov[] = "_renovacao";
        if (suffix.size() > sizeof(kRenov) - 1
            && suffix.compare(
                   suffix.size() - (sizeof(kRenov) - 1), sizeof(kRenov) - 1, kRenov)
                   == 0) {
            suffix.resize(suffix.size() - (sizeof(kRenov) - 1));
        }
    }
    if (suffix == "delta") return "Delta";
    if (suffix == "gamma" || suffix == "gama") return "Gamma";
    if (suffix == "beta") return "Beta";
    if (suffix == "alfa") return "Alfa";
    if (suffix == "omega") return "Omega";
    if (suffix == "transcendente") return "Transcendente";
    if (suffix == "etereo") return "Etereo";
    if (suffix == "universal") return "Universal";
    if (suffix == "onipotente") return "Onipotente";
    if (suffix == "surreal") return "Surreal";
    if (suffix == "imaterial") return "Imaterial";
    if (suffix == "exotico") return "Exotico";
    if (suffix == "nuvem") return "keyvault";
    return group;
}

std::string PaidSkuAlias(const std::string& group) {
    for (const char* g : CustomShop::kPaidLicenseGroups) {
        if (group == g)
            return "licenca_" + ToLowerAsciiLocal(group);
    }
    return {};
}

bool IsPaidTier(const std::string& group) {
    for (const char* g : CustomShop::kPaidLicenseGroups) {
        if (group == g) return true;
    }
    return false;
}

std::string PaidGroupsInList() {
    std::string in_list;
    for (const char* g : CustomShop::kPaidLicenseGroups) {
        if (!in_list.empty()) in_list += ",";
        in_list += "'";
        in_list += g;
        in_list += "'";
    }
    return in_list;
}

/** Conta tiers pagos activos distintos; se exclude_group estiver activo, não o conta
 *  (para saber quantos *outros* slots estão ocupados ao tentar um novo tier). */
int CountActivePaidLicenses(MYSQL* db, const std::string& steam_escaped,
                            const std::string& exclude_group_escaped = "") {
    if (!db) return 0;
    std::string sql =
        "SELECT COUNT(*) FROM player_entitlements WHERE steam_id = '"
        + steam_escaped + "' AND group_name IN (" + PaidGroupsInList() + ") "
        "AND (expires IS NULL OR expires > NOW())";
    if (!exclude_group_escaped.empty()) {
        sql += " AND group_name != '" + exclude_group_escaped + "'";
    }
    if (mysql_query(db, sql.c_str()) != 0) return 0;
    MYSQL_RES* res = mysql_store_result(db);
    if (!res) return 0;
    MYSQL_ROW row = mysql_fetch_row(res);
    int count = (row && row[0]) ? std::atoi(row[0]) : 0;
    mysql_free_result(res);
    return count;
}

bool HasActivePaidGroup(MYSQL* db, const std::string& steam_escaped,
                        const std::string& group_escaped) {
    if (!db) return false;
    const std::string sql =
        "SELECT 1 FROM player_entitlements WHERE steam_id = '"
        + steam_escaped + "' AND group_name = '" + group_escaped + "' "
        "AND (expires IS NULL OR expires > NOW()) LIMIT 1";
    if (mysql_query(db, sql.c_str()) != 0) return false;
    MYSQL_RES* res = mysql_store_result(db);
    if (!res) return false;
    const bool found = mysql_fetch_row(res) != nullptr;
    mysql_free_result(res);
    return found;
}

std::vector<std::string> ParsePermissionsList(const std::string& perms_str) {
    std::vector<std::string> out;
    std::stringstream ss(perms_str);
    std::string token;
    while (std::getline(ss, token, ',')) {
        const auto first = token.find_first_not_of(" \t");
        if (first == std::string::npos) continue;
        const auto last = token.find_last_not_of(" \t");
        out.push_back(token.substr(first, last - first + 1));
    }
    return out;
}

void RunPermissionConsole(const std::string& steam_id, const std::string& cmd) {
    auto* world = ArkApi::GetApiUtils().GetWorld();
    if (!world) return;
    const auto& controllers = world->PlayerControllerListField();
    AShooterPlayerController* target = nullptr;
    for (TWeakObjectPtr<APlayerController> wpc : controllers) {
        auto* sc = static_cast<AShooterPlayerController*>(wpc.Get());
        if (!sc) continue;
        if (CustomShop::Bridge::GetSteamId(sc) == steam_id) {
            target = sc;
            break;
        }
    }
    if (!target) {
        Log::GetLog()->info(
            "ShopEntitlements: no online player for Permissions sync ({})", steam_id);
        return;
    }
    FString fscmd(cmd.c_str());
    FString result;
    target->ConsoleCommand(&result, &fscmd, true);
    Log::GetLog()->info(
        "ShopEntitlements: Permissions sync cmd='{}' steam_id={} result='{}'",
        cmd, steam_id, result.ToString());
}

} // anonymous namespace

namespace CustomShop {

ShopEntitlements& ShopEntitlements::Get() {
    static ShopEntitlements instance;
    return instance;
}

void ShopEntitlements::SetDb(MYSQL* db) {
    db_ = db;
}

void ShopEntitlements::SyncPermissionsCommand(const std::string& steam_id,
                                            const std::string& group,
                                            int days) {
    std::string cmd;
    if (days <= 0) {
        cmd = "Permissions.Add " + steam_id + " " + group;
    } else {
        const int hours = days * 24;
        cmd = "Permissions.AddTimed " + steam_id + " " + group + " " + std::to_string(hours);
    }
    RunPermissionConsole(steam_id, cmd);
}

int ShopEntitlements::QueryHoursRemaining(const std::string& steam_id,
                                          const std::string& group) {
    if (!db_ || steam_id.empty() || group.empty()) return -1;

    char buf_id[64], buf_grp[64];
    mysql_real_escape_string(db_, buf_id, steam_id.c_str(),
        static_cast<unsigned long>(steam_id.size()));
    mysql_real_escape_string(db_, buf_grp, group.c_str(),
        static_cast<unsigned long>(group.size()));

    const std::string sql =
        "SELECT CASE WHEN expires IS NULL THEN -1 "
        "     ELSE GREATEST(1, TIMESTAMPDIFF(HOUR, NOW(), expires)) END "
        "FROM player_entitlements "
        "WHERE steam_id = '" + std::string(buf_id) + "' "
        "AND group_name = '" + std::string(buf_grp) + "' "
        "AND (expires IS NULL OR expires > NOW()) LIMIT 1;";

    if (mysql_query(db_, sql.c_str()) != 0) return -1;
    MYSQL_RES* res = mysql_store_result(db_);
    if (!res) return -1;
    MYSQL_ROW row = mysql_fetch_row(res);
    int hours = -1;
    if (row && row[0]) hours = std::atoi(row[0]);
    mysql_free_result(res);
    return hours;
}

void ShopEntitlements::SyncPlayerOnJoin(const std::string& steam_id) {
    if (!db_ || steam_id.empty()) return;

    char buf_id[64];
    mysql_real_escape_string(db_, buf_id, steam_id.c_str(),
        static_cast<unsigned long>(steam_id.size()));

    const std::string sql =
        "SELECT group_name, "
        "CASE WHEN expires IS NULL THEN -1 "
        "     ELSE GREATEST(1, TIMESTAMPDIFF(HOUR, NOW(), expires)) END "
        "FROM player_entitlements "
        "WHERE steam_id = '" + std::string(buf_id) + "' "
        "AND (expires IS NULL OR expires > NOW());";

    if (mysql_query(db_, sql.c_str()) != 0) {
        Log::GetLog()->warn(
            "ShopEntitlements::SyncPlayerOnJoin query failed: {}", mysql_error(db_));
        return;
    }

    MYSQL_RES* res = mysql_store_result(db_);
    if (!res) return;

    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res))) {
        if (!row[0] || !row[0][0]) continue;
        const std::string group = row[0];
        const int hours_left = row[1] ? std::atoi(row[1]) : -1;

        if (hours_left < 0) {
            // Permanente: só adiciona se ainda não estiver no grupo.
            uint64_t sid = 0;
            try { sid = std::stoull(steam_id); } catch (...) {}
            if (sid && Perms::IsInGroup(sid, group)) continue;
            RunPermissionConsole(steam_id, "Permissions.Add " + steam_id + " " + group);
        } else {
            // Temporário: sempre realinha ao expires do DB (fonte de verdade).
            // Antes saltava se já estivesse no grupo — Permissions ficava com residual
            // antigo após renovação (ex.: keyvault ~17d em vez de ~30/+residual).
            RunPermissionConsole(
                steam_id,
                "Permissions.AddTimed " + steam_id + " " + group + " "
                    + std::to_string(hours_left));
        }
        Log::GetLog()->info(
            "ShopEntitlements: SyncPlayerOnJoin synced group '{}' for {} (hours={})",
            group, steam_id, hours_left);
    }
    mysql_free_result(res);
}

bool ShopEntitlements::Grant(const std::string& steam_id,
                           const std::string& group,
                           int days,
                           const std::string& source,
                           const std::string& notes) {
    if (!db_ || steam_id.empty() || group.empty()) return false;

    // Nunca gravar SKU de catálogo (`licenca_delta`) — só PermissionGroup TimedPoints.
    const std::string normalized = NormalizeEntitlementGroup(group);
    if (normalized.empty()) return false;
    if (normalized != group) {
        Log::GetLog()->info(
            "ShopEntitlements::Grant normalized '{}' → '{}' for {}",
            group, normalized, steam_id);
    }

    char buf_id[64], buf_grp[64], buf_src[128], buf_notes[512];
    mysql_real_escape_string(db_, buf_id, steam_id.c_str(),
        static_cast<unsigned long>(steam_id.size()));
    mysql_real_escape_string(db_, buf_grp, normalized.c_str(),
        static_cast<unsigned long>(normalized.size()));
    mysql_real_escape_string(db_, buf_src, source.c_str(),
        static_cast<unsigned long>(source.size()));
    mysql_real_escape_string(db_, buf_notes, notes.c_str(),
        static_cast<unsigned long>(notes.size()));

    if (IsPaidTier(normalized)) {
        const bool renewing = HasActivePaidGroup(db_, buf_id, buf_grp);
        if (!renewing) {
            const int others = CountActivePaidLicenses(db_, buf_id, buf_grp);
            if (others >= CustomShop::kMaxActivePaidLicenseTiers) {
                Log::GetLog()->warn(
                    "ShopEntitlements::Grant blocked: {} already has {} paid tiers "
                    "(max {}); cannot activate '{}'",
                    steam_id, others, CustomShop::kMaxActivePaidLicenseTiers,
                    normalized);
                CustomShop::Debug::Fields f;
                f.steam_id = steam_id;
                f.extra = {{"group", normalized}, {"days", days},
                           {"reason", "license_slots_full"}};
                CustomShop::Debug::Error("License", f, "Grant blocked: max 2 paid tiers");
                return false;
            }
        }
    }

    std::string sql;
    if (days <= 0) {
        sql =
            "INSERT INTO player_entitlements (steam_id, group_name, expires, source, notes) VALUES ('"
            + std::string(buf_id) + "', '" + std::string(buf_grp) + "', NULL, '"
            + std::string(buf_src) + "', '" + std::string(buf_notes) + "') "
            "ON DUPLICATE KEY UPDATE "
            "  expires = NULL,"
            "  source  = '" + std::string(buf_src) + "',"
            "  notes   = '" + std::string(buf_notes) + "';";
    } else {
        const std::string insert_expires =
            "DATE_ADD(NOW(), INTERVAL " + std::to_string(days) + " DAY)";
        const std::string update_expires =
            "DATE_ADD(GREATEST(COALESCE(expires, NOW()), NOW()), INTERVAL "
            + std::to_string(days) + " DAY)";
        sql =
            "INSERT INTO player_entitlements (steam_id, group_name, expires, source, notes) VALUES ('"
            + std::string(buf_id) + "', '" + std::string(buf_grp) + "', "
            + insert_expires + ", '" + std::string(buf_src) + "', '"
            + std::string(buf_notes) + "') "
            "ON DUPLICATE KEY UPDATE "
            "  expires = " + update_expires + ","
            "  source  = '" + std::string(buf_src) + "',"
            "  notes   = '" + std::string(buf_notes) + "';";
    }

    if (mysql_query(db_, sql.c_str()) != 0) {
        Log::GetLog()->error("ShopEntitlements::Grant failed: {}", mysql_error(db_));
        CustomShop::Debug::Fields f;
        f.steam_id = steam_id;
        f.extra = {{"group", normalized}, {"days", days},
                   {"mysql_error", mysql_error(db_)}};
        CustomShop::Debug::Error("License", f, "Grant MySQL failed");
        return false;
    }

    // Permissions.AddTimed precisa das horas totais após renovação (DB),
    // não só days*24 — senão residual activo era descartado no plugin.
    if (days <= 0) {
        SyncPermissionsCommand(steam_id, normalized, 0);
    } else {
        int hours = QueryHoursRemaining(steam_id, normalized);
        if (hours < 1) hours = days * 24;
        RunPermissionConsole(
            steam_id,
            "Permissions.AddTimed " + steam_id + " " + normalized + " "
                + std::to_string(hours));
    }
    // Paridade web: renovação / re-grant restaura limites DefaultAmount dos kits do grupo.
    try {
        ShopPoints::Get().ResetDependentKitLimits(steam_id, normalized);
    } catch (...) {
        Log::GetLog()->warn(
            "ShopEntitlements::Grant: kit limits reset failed for {} group '{}'",
            steam_id, normalized);
    }

    {
        CustomShop::Debug::Fields f;
        f.steam_id = steam_id;
        f.extra = {{"group", normalized}, {"days", days}, {"source", source}};
        CustomShop::Debug::Info("License", f, "Grant OK");
    }
    return true;
}

bool ShopEntitlements::Revoke(const std::string& steam_id, const std::string& group) {
    if (!db_ || steam_id.empty() || group.empty()) return false;

    const std::string canonical = NormalizeEntitlementGroup(group);
    const std::string sku = PaidSkuAlias(canonical);

    char buf_id[64];
    mysql_real_escape_string(db_, buf_id, steam_id.c_str(),
        static_cast<unsigned long>(steam_id.size()));

    auto delete_group = [&](const std::string& name) -> bool {
        if (name.empty()) return false;
        char buf_grp[64];
        mysql_real_escape_string(db_, buf_grp, name.c_str(),
            static_cast<unsigned long>(name.size()));
        const std::string sql =
            "DELETE FROM player_entitlements WHERE steam_id = '"
            + std::string(buf_id) + "' AND group_name = '" + std::string(buf_grp)
            + "';";
        if (mysql_query(db_, sql.c_str()) != 0) {
            Log::GetLog()->error("ShopEntitlements::Revoke failed: {}", mysql_error(db_));
            return false;
        }
        return mysql_affected_rows(db_) > 0;
    };

    const bool removed =
        delete_group(canonical) || delete_group(sku) || delete_group(group);
    RunPermissionConsole(steam_id, "Permissions.Remove " + steam_id + " " + canonical);
    if (!sku.empty())
        RunPermissionConsole(steam_id, "Permissions.Remove " + steam_id + " " + sku);
    return removed;
}

bool ShopEntitlements::HasActive(const std::string& steam_id, const std::string& group) {
    if (group == "Default") return true;
    if (steam_id.empty()) return false;

    const std::string canonical = NormalizeEntitlementGroup(group);

    uint64_t sid = 0;
    try { sid = std::stoull(steam_id); } catch (...) {}

    if (sid && Perms::IsInGroup(sid, canonical)) return true;
    const std::string sku = PaidSkuAlias(canonical);
    if (sid && !sku.empty() && Perms::IsInGroup(sid, sku)) return true;

    if (!db_) return false;

    char buf_id[64];
    mysql_real_escape_string(db_, buf_id, steam_id.c_str(),
        static_cast<unsigned long>(steam_id.size()));

    auto query_group = [&](const std::string& name) -> bool {
        if (name.empty()) return false;
        char buf_grp[64];
        mysql_real_escape_string(db_, buf_grp, name.c_str(),
            static_cast<unsigned long>(name.size()));
        const std::string sql =
            "SELECT 1 FROM player_entitlements WHERE steam_id = '"
            + std::string(buf_id) + "' AND group_name = '" + std::string(buf_grp)
            + "' AND (expires IS NULL OR expires > NOW()) LIMIT 1;";
        if (mysql_query(db_, sql.c_str()) != 0) return false;
        MYSQL_RES* res = mysql_store_result(db_);
        if (!res) return false;
        const bool found = mysql_fetch_row(res) != nullptr;
        mysql_free_result(res);
        return found;
    };

    if (query_group(canonical)) return true;
    // Legado: group_name gravado como SKU `licenca_delta` em vez de `Delta`.
    if (!sku.empty() && query_group(sku)) return true;
    return false;
}

bool ShopEntitlements::HasAnyActive(const std::string& steam_id,
                                    const std::vector<std::string>& groups) {
    if (groups.empty()) return true;
    for (const auto& g : groups)
        if (HasActive(steam_id, g)) return true;
    return false;
}

std::vector<std::string> ShopEntitlements::GetActiveGroups(const std::string& steam_id) {
    std::vector<std::string> out;
    if (!db_ || steam_id.empty()) return out;

    char buf_id[64];
    mysql_real_escape_string(db_, buf_id, steam_id.c_str(),
        static_cast<unsigned long>(steam_id.size()));

    const std::string sql =
        "SELECT group_name FROM player_entitlements WHERE steam_id = '"
        + std::string(buf_id) + "' AND (expires IS NULL OR expires > NOW());";

    if (mysql_query(db_, sql.c_str()) != 0) return out;
    MYSQL_RES* res = mysql_store_result(db_);
    if (!res) return out;

    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res))) {
        if (row[0] && row[0][0]) out.emplace_back(row[0]);
    }
    mysql_free_result(res);
    return out;
}

void ShopEntitlements::PruneExpired() {
    if (!db_) return;
    // Mantém linhas expiradas por 8 dias (janela de renovação recente −10% na web).
    const char* sql =
        "DELETE FROM player_entitlements WHERE expires IS NOT NULL "
        "AND expires < DATE_SUB(NOW(), INTERVAL 8 DAY);";
    if (mysql_query(db_, sql) != 0) {
        Log::GetLog()->error("ShopEntitlements::PruneExpired failed: {}", mysql_error(db_));
    }
}

bool ShopEntitlements::CanRedeem(uint64_t steam_id, const nlohmann::json& entry) {
    if (!entry.contains("Permissions")) return true;

    const std::string perms_str = entry.value("Permissions", "");
    if (perms_str.empty()) return true;

    const auto groups = ParsePermissionsList(perms_str);
    if (groups.empty()) return true;

    const std::string mode = entry.value("PermissionsMode", "any");
    const std::string sid = std::to_string(steam_id);

    if (mode == "all") {
        for (const auto& g : groups)
            if (!HasActive(sid, g)) return false;
        return true;
    }
    return HasAnyActive(sid, groups);
}

bool ShopEntitlements::ApplyLicenseGrant(AShooterPlayerController* controller,
                                       const nlohmann::json& entry,
                                       const std::string& kit_or_item_id) {
    if (!entry.contains("LicenseGrant") || !entry.at("LicenseGrant").is_object())
        return false;

    const auto& lic = entry.at("LicenseGrant");
    if (lic.value("Redeemable", true) == false && lic.value("AdminOnly", false))
        return false;

    const std::string group = lic.value("Group", "");
    if (group.empty()) return false;

    const int days = lic.value("Days", 30);
    const std::string sid = controller
        ? Bridge::GetSteamId(controller)
        : std::string();

    if (sid.empty()) return false;

    const std::string notes = "deliver:" + kit_or_item_id;
    return Grant(sid, group, days, notes, notes);
}

} // namespace CustomShop
