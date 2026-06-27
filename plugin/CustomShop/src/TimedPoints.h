#pragma once

#include "pch.h"

// ─────────────────────────────────────────────────────────────────
//  TimedPoints — awards shop points on a fixed interval to players
//  who are connected on the server. No offline accumulation.
//
//  Default group: base reward for every online player.
//  Other groups: permission group and/or active VIP license (vip_players)
//  from a web-redeemed kit (VipLicense in kit JSON).
//
//  "TimedPointsReward": {
//    "Enabled": true,
//    "Interval": 30,
//    "StackRewards": true,
//    "Groups": {
//      "Default":     { "Amount": 25  },
//      "Gamma":       { "Amount": 25  },
//      "Beta":        { "Amount": 50  },
//      "Alfa":        { "Amount": 75  },
//      ...
//    }
//  }
// ─────────────────────────────────────────────────────────────────

namespace CustomShop {
namespace TimedPoints {

void Start();
void LogStatus();
void OnConfigReload();

} // namespace TimedPoints
} // namespace CustomShop
