#include "pch.h"
#include "TimedPoints.h"
#include "ShopConfig.h"
#include "ShopPoints.h"
#include "ShopBridge.h"
#include "ShopPerms.h"
#include "ShopVip.h"
#include "ShopEntitlements.h"

#include <Timer.h>
#include <sstream>

namespace {

bool g_timer_scheduled = false;

void NotifyTimedReward(AShooterPlayerController* controller,
                       int awarded,
                       int balance) {
    if (!controller || awarded <= 0) return;

    std::ostringstream msg;
    msg << "Foram adicionados +" << awarded
        << " Ambares em sua conta e agora voce tem "
        << balance << " Ambares";

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

        for (const auto& [grp, amt] : group_amounts) {
            bool qualifies = false;
            if (grp == "Default") {
                qualifies = true;
            } else if (CustomShop::ShopEntitlements::Get().HasActive(sid, grp)) {
                qualifies = true;
            } else if (CustomShop::Perms::IsInGroup(steam_id, grp)) {
                qualifies = true;
            } else {
                const std::string tier = CustomShop::ShopVip::Get().GetActiveTier(sid);
                qualifies = (!tier.empty() && tier == grp);
            }

            if (!qualifies) continue;
            total += amt;
            if (amt > best) best = amt;
        }

        const int award = stack ? total : best;
        if (award <= 0) {
            ++skipped_zero;
            continue;
        }

        if (CustomShop::ShopPoints::Get().AddPoints(sid, award)) {
            const int balance =
                CustomShop::ShopPoints::Get().GetPoints(sid);
            NotifyTimedReward(sc, award, balance);
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
