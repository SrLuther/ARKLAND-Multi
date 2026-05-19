#pragma once

#include "pch.h"

// ─────────────────────────────────────────────────────────────────
//  TimedPoints — awards shop points to every online player on a
//  configurable interval, with per-permission-group amounts.
//
//  Config section (config.json):
//  "TimedPointsReward": {
//    "Enabled": true,
//    "Interval": 30,          // minutes
//    "StackRewards": true,    // add all groups the player is in
//    "Groups": {
//      "Default":     { "Amount": 25  },
//      "VIPBronze":   { "Amount": 20  },
//      "VIPPrata":    { "Amount": 30  },
//      "VIPOuro":     { "Amount": 50  },
//      "VIPDiamante": { "Amount": 75  },
//      "VIPDoacao":   { "Amount": 100 },
//      "Staff":       { "Amount": 1000}
//    }
//  }
//
//  With StackRewards=true a Staff + VIPOuro player receives
//  Default(25) + VIPOuro(50) + Staff(1000) = 1075 pts per tick.
//  With StackRewards=false they receive only the highest value (1000).
// ─────────────────────────────────────────────────────────────────

namespace CustomShop {
namespace TimedPoints {

// Register the recurring timer.  Call once in Plugin_Init after
// ShopConfig and ShopPoints are initialised.
void Start();

} // namespace TimedPoints
} // namespace CustomShop
