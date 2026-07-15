#include "pch.h"
#include "TimedPoints.h"
#include "ShopConfig.h"
#include "ShopPoints.h"
#include "ShopBridge.h"
#include "ShopPerms.h"
#include "ShopVip.h"
#include "ShopEntitlements.h"

#include <Timer.h>
#include <chrono>
#include <sstream>

namespace {

bool g_timer_scheduled = false;

std::string TimedMapId() {
    const auto& settings = CustomShop::ShopConfig::Get().Settings();
    std::string id = settings.value("ServerId", "");
    if (!id.empty() && id != "CHANGE_ME" && id != "default")
        return id;
    try {
        auto* gm = ArkApi::GetApiUtils().GetShooterGameMode();
        if (gm) {
            FString map_name;
            gm->GetMapName(&map_name);
            if (!map_name.IsEmpty())
                return map_name.ToString();
        }
    } catch (...) {
    }
    return "unknown";
}

void EnqueueArkbankTimedOutbox(const std::string& steam_id,
                               int amount,
                               const std::string& map_id,
                               const std::string& cycle_key) {
    if (amount <= 0 || steam_id.empty()) return;
    MYSQL* db = CustomShop::ShopPoints::Get().GetDb();
    if (!db) return;

    auto escape = [&](const std::string& s) -> std::string {
        char buf[512];
        unsigned long len = mysql_real_escape_string(
            db, buf, s.c_str(),
            static_cast<unsigned long>(
                s.size() < sizeof(buf) - 1 ? s.size() : sizeof(buf) - 1));
        return std::string("'") + std::string(buf, len) + "'";
    };

    // Tabela criada pelo Flask (ensure_arkbank_schema). INSERT ignora falha
    // se ainda não existir — TimedPoints nunca é bloqueado pelo ARKBANK.
    const std::string sql =
        "INSERT IGNORE INTO arkbank_timed_outbox "
        "(created_at, steam_id, amount, map_id, cycle_key, processed_at) VALUES ("
        "UTC_TIMESTAMP(3),"
        + escape(steam_id) + ","
        + std::to_string(amount) + ","
        + escape(map_id.substr(0, 64)) + ","
        + escape(cycle_key.substr(0, 64)) + ","
        "NULL)";

    if (mysql_query(db, sql.c_str()) != 0) {
        Log::GetLog()->debug(
            "TimedPoints ARKBANK outbox skip: {}", mysql_error(db));
    }
}

void NotifyTimedReward(AShooterPlayerController* controller,
                       int awarded,
                       int balance) {
    if (!controller || awarded <= 0) return;

    std::ostringstream msg;
    msg << "Foram adicionados +" << awarded
        << " Ambares em sua conta e agora voce tem "
        << balance << " Ambares";

    // URL da loja (Settings.WebsiteUrl; fallback WebApiUrl) — mesmo padrão de /upload.
    const auto& shop_cfg = CustomShop::ShopConfig::Get();
    std::string url = shop_cfg.WebsiteUrl();
    if (url.empty())
        url = shop_cfg.WebApiUrl();
    if (!url.empty())
        msg << ". Acesse a loja: " << url;

    static const FString kSender(L"Nuvem");
    std::string safe;
    const std::string raw = msg.str();
    safe.reserve(raw.size());
    for (unsigned char ch : raw) {
        if (ch >= 32 && ch <= 126)
            safe.push_back(static_cast<char>(ch));
    }
    if (safe.empty()) return;

    ArkApi::GetApiUtils().SendChatMessage(controller, kSender, safe.c_str());
}

std::string FormatGroupSummary(const nlohmann::json& groups_cfg) {
    std::ostringstream out;
    bool first = true;
    for (const auto& [grp, val] : groups_cfg.items()) {
        const int amt = val.value("Amount", 0);
        if (amt <= 0) continue;
        if (!first) out << ", ";
        out << grp << "=" << amt;
        first = false;
    }
    return out.str();
}

bool IsStaffModAlias(const std::string& grp) {
    return grp == "Moderacao" || grp == "Mod" || grp == "MOD";
}

bool IsPaidLicenseGroup(const std::string& grp) {
    for (const char* g : CustomShop::kPaidLicenseGroups) {
        if (grp == g) return true;
    }
    return false;
}

bool PlayerQualifiesForTimedGroup(const std::string& sid,
                                  uint64_t steam_id,
                                  const std::string& grp) {
    if (grp == "Default")
        return true;

    std::vector<std::string> candidates;
    candidates.push_back(grp);
    if (IsStaffModAlias(grp))
        candidates = {"Moderacao", "Mod", "MOD"};

    for (const auto& name : candidates) {
        if (CustomShop::ShopEntitlements::Get().HasActive(sid, name))
            return true;
        if (CustomShop::Perms::IsInGroup(steam_id, name))
            return true;
        const std::string tier = CustomShop::ShopVip::Get().GetActiveTier(sid);
        if (!tier.empty() && tier == name)
            return true;
    }
    return false;
}

void LogConfigStatus(const char* context) {
    const auto& cfg = CustomShop::ShopConfig::Get().TimedPointsReward();
    const bool enabled = cfg.value("Enabled", false);
    const int interval_min = cfg.value("Interval", 30);
    const auto& groups_cfg = cfg.value("Groups", nlohmann::json::object());
    const std::string groups = FormatGroupSummary(groups_cfg);

    if (!enabled) {
        Log::GetLog()->info(
            "TimedPoints: {} — disabled (Interval={} min, groups=[{}]). "
            "Enable TimedPointsReward.Enabled and run Shop.Reload.",
            context, interval_min, groups.empty() ? "(none)" : groups);
        return;
    }

    if (groups_cfg.empty()) {
        Log::GetLog()->warn(
            "TimedPoints: {} — enabled but Groups is empty; no rewards will run.",
            context);
        return;
    }

    if (groups.empty()) {
        Log::GetLog()->warn(
            "TimedPoints: {} — enabled but all group Amount values are 0.",
            context);
        return;
    }

    const bool has_default = groups_cfg.contains("Default")
        && groups_cfg["Default"].value("Amount", 0) > 0;

    Log::GetLog()->info(
        "TimedPoints: {} — enabled, interval={} min, stack={}, groups=[{}], Default={}.",
        context,
        interval_min,
        cfg.value("StackRewards", true) ? "yes" : "no",
        groups,
        has_default ? "yes" : "NO (only matching PermissionGroups qualify)");
}

void Tick() {
    const auto& cfg = CustomShop::ShopConfig::Get().TimedPointsReward();
    if (!cfg.value("Enabled", false)) return;

    const bool stack       = cfg.value("StackRewards", true);
    const auto& groups_cfg = cfg.value("Groups", nlohmann::json::object());
    if (groups_cfg.empty()) {
        Log::GetLog()->warn(
            "TimedPoints: tick skipped — Groups is empty while Enabled=true.");
        return;
    }

    std::vector<std::pair<std::string, int>> group_amounts;
    group_amounts.reserve(groups_cfg.size());
    for (const auto& [grp, val] : groups_cfg.items()) {
        const int amt = val.value("Amount", 0);
        if (amt > 0)
            group_amounts.emplace_back(grp, amt);
    }
    if (group_amounts.empty()) {
        Log::GetLog()->warn(
            "TimedPoints: tick skipped — no group with Amount > 0.");
        return;
    }

    const auto cycle_epoch = std::chrono::duration_cast<std::chrono::seconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
    const std::string map_id = TimedMapId();
    const std::string cycle_key = std::to_string(cycle_epoch);

    auto* world = ArkApi::GetApiUtils().GetWorld();
    if (!world) return;

    // Only connected players — no offline accumulation.
    const auto& controllers = world->PlayerControllerListField();

    int online = 0;
    int awarded = 0;
    int skipped_zero = 0;
    int failed_db = 0;

    for (TWeakObjectPtr<APlayerController> wpc : controllers) {
        auto* sc = static_cast<AShooterPlayerController*>(wpc.Get());
        if (!sc) continue;

        const std::string sid = CustomShop::Bridge::GetSteamId(sc);
        if (sid.empty()) continue;

        ++online;

        uint64_t steam_id = 0;
        try {
            steam_id = std::stoull(sid);
        } catch (...) {
            continue;
        }

        int total = 0;
        int best  = 0;
        int best_paid = 0;

        for (const auto& [grp, amt] : group_amounts) {
            if (!PlayerQualifiesForTimedGroup(sid, steam_id, grp))
                continue;
            if (amt > best) best = amt;
            // Entre tiers pagos vence o maior bónus; Default/staff/keyvault empilham.
            if (IsPaidLicenseGroup(grp)) {
                if (amt > best_paid) best_paid = amt;
            } else {
                total += amt;
            }
        }
        if (stack) total += best_paid;
        else total = best;

        const int award = total;
        if (award <= 0) {
            ++skipped_zero;
            continue;
        }

        if (CustomShop::ShopPoints::Get().AddPoints(sid, award)) {
            const int balance =
                CustomShop::ShopPoints::Get().GetPoints(sid);
            NotifyTimedReward(sc, award, balance);
            EnqueueArkbankTimedOutbox(sid, award, map_id, cycle_key);
            ++awarded;
            Log::GetLog()->info(
                "TimedPoints: {} +{} pts (balance={})", sid, award, balance);
        } else {
            ++failed_db;
            Log::GetLog()->warn(
                "TimedPoints: failed to award {} pts to {}", award, sid);
        }
    }

    if (online > 0 && awarded == 0) {
        Log::GetLog()->warn(
            "TimedPoints: {} online player(s), 0 rewarded "
            "(zero_match={}, db_fail={}). Check Default group and PermissionGroups names.",
            online, skipped_zero, failed_db);
    } else if (awarded > 0) {
        Log::GetLog()->info(
            "TimedPoints: cycle done — {} player(s) rewarded ({} online).",
            awarded, online);
    }
}

} // anonymous namespace

namespace CustomShop {
namespace TimedPoints {

void LogStatus() {
    LogConfigStatus("status");
}

void OnConfigReload() {
    LogConfigStatus("config reloaded");
}

void Start() {
    const auto& cfg = ShopConfig::Get().TimedPointsReward();
    const int interval_min  = cfg.value("Interval", 30);
    const int interval_secs = std::max(60, interval_min * 60);

    if (!g_timer_scheduled) {
        API::Timer::Get().RecurringExecute(Tick, interval_secs, -1, false);
        g_timer_scheduled = true;
        LogConfigStatus("timer scheduled");
        return;
    }

    LogConfigStatus("already running");
}

} // namespace TimedPoints
} // namespace CustomShop
