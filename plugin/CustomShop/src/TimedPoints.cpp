#include "pch.h"
#include "TimedPoints.h"
#include "ShopConfig.h"
#include "ShopPoints.h"
#include "ShopBridge.h"
#include "ShopPerms.h"
#include "ShopVip.h"

#include <Timer.h>

namespace {

void Tick() {
    const auto& cfg = CustomShop::ShopConfig::Get().TimedPointsReward();
    if (!cfg.value("Enabled", false)) return;

    const bool stack       = cfg.value("StackRewards", true);
    const auto& groups_cfg = cfg.value("Groups", nlohmann::json::object());
    if (groups_cfg.empty()) return;

    std::vector<std::pair<std::string, int>> group_amounts;
    group_amounts.reserve(groups_cfg.size());
    for (const auto& [grp, val] : groups_cfg.items()) {
        const int amt = val.value("Amount", 0);
        if (amt > 0)
            group_amounts.emplace_back(grp, amt);
    }
    if (group_amounts.empty()) return;

    // Only connected players — no offline accumulation.
    const auto& controllers =
        ArkApi::GetApiUtils().GetWorld()->PlayerControllerListField();

    for (TWeakObjectPtr<APlayerController> wpc : controllers) {
        auto* sc = static_cast<AShooterPlayerController*>(wpc.Get());
        if (!sc) continue;

        const std::string sid = CustomShop::Bridge::GetSteamId(sc);
        if (sid.empty()) continue;

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
                // Base interval reward — every connected player.
                qualifies = true;
            } else if (CustomShop::Perms::IsInGroup(steam_id, grp)) {
                qualifies = true;
            } else {
                // Web-redeemed VIP license (vip_players) matching this tier.
                const std::string tier = CustomShop::ShopVip::Get().GetActiveTier(sid);
                qualifies = (!tier.empty() && tier == grp);
            }

            if (!qualifies) continue;
            total += amt;
            if (amt > best) best = amt;
        }

        const int award = stack ? total : best;
        if (award <= 0) continue;

        CustomShop::ShopPoints::Get().AddPoints(sid, award);
        Log::GetLog()->debug("TimedPoints: {} +{} pts", sid, award);
    }
}

} // anonymous namespace

namespace CustomShop {
namespace TimedPoints {

void Start() {
    const auto& cfg = ShopConfig::Get().TimedPointsReward();
    if (!cfg.value("Enabled", false)) {
        Log::GetLog()->info("TimedPoints: disabled in config — skipped.");
        return;
    }

    const int interval_min  = cfg.value("Interval", 30);
    const int interval_secs = interval_min * 60;

    API::Timer::Get().RecurringExecute(Tick, interval_secs, -1, false);

    Log::GetLog()->info(
        "TimedPoints: started (interval={} min, stack={}, online players only).",
        interval_min,
        cfg.value("StackRewards", true) ? "yes" : "no");
}

} // namespace TimedPoints
} // namespace CustomShop
