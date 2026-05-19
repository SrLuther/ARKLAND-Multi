#include "pch.h"
#include "TimedPoints.h"
#include "ShopConfig.h"
#include "ShopPoints.h"
#include "ShopBridge.h"
#include "ShopPerms.h"

#include <Timer.h>

namespace {

void Tick() {
    const auto& cfg = CustomShop::ShopConfig::Get().TimedPointsReward();
    if (!cfg.value("Enabled", false)) return;

    const bool stack       = cfg.value("StackRewards", true);
    const auto& groups_cfg = cfg.value("Groups", nlohmann::json::object());
    if (groups_cfg.empty()) return;

    // Build sorted list of (group_name, amount) — exclude zero-amount entries.
    std::vector<std::pair<std::string, int>> group_amounts;
    group_amounts.reserve(groups_cfg.size());
    for (const auto& [grp, val] : groups_cfg.items()) {
        const int amt = val.value("Amount", 0);
        if (amt > 0)
            group_amounts.emplace_back(grp, amt);
    }
    if (group_amounts.empty()) return;

    // Iterate all connected players.
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

        // Calculate award based on group membership.
        int total = 0;
        int best  = 0;
        for (const auto& [grp, amt] : group_amounts) {
            if (CustomShop::Perms::IsInGroup(steam_id, grp)) {
                total += amt;
                if (amt > best) best = amt;
            }
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

    // -1 = repeat forever; false = run on game thread (safe for Ark API calls).
    API::Timer::Get().RecurringExecute(Tick, interval_secs, -1, false);

    Log::GetLog()->info(
        "TimedPoints: started (interval={} min, stack={}).",
        interval_min,
        cfg.value("StackRewards", true) ? "yes" : "no");
}

} // namespace TimedPoints
} // namespace CustomShop
