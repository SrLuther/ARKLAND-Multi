#include "pch.h"
#include "ShopData.h"
#include "ShopBridge.h"
#include "ShopConfig.h"
#include "ShopPoints.h"

namespace CustomShop {
namespace Data {

bool SendConfig(AShooterPlayerController* /*controller*/) {
    return false;
}

bool SendShopItems(AShooterPlayerController* /*controller*/,
                   const std::string& /*type_filter*/) {
    return false;
}

bool SendPoints(AShooterPlayerController* /*controller*/) {
    return false;
}

bool SendKits(AShooterPlayerController* /*controller*/) {
    return false;
}

bool SendPlayerKits(AShooterPlayerController* /*controller*/,
                    const std::string& /*steam_id*/) {
    return false;
}

bool SendBuyResult(AShooterPlayerController* /*controller*/,
                   const std::string& /*steam_id*/,
                   const std::string& /*item_id*/,
                   int /*amount*/,
                   bool /*success*/) {
    return false;
}

bool SendTradeResult(AShooterPlayerController* /*sender*/,
                     AShooterPlayerController* /*receiver*/,
                     const std::string& /*sender_id*/,
                     const std::string& /*receiver_id*/,
                     int /*amount*/,
                     bool /*success*/) {
    return false;
}

bool SendReload(AShooterPlayerController* /*controller*/) {
    return false;
}

void InitPlayer(AShooterPlayerController* controller) {
    if (!controller) return;
    const std::string id = Bridge::GetSteamId(controller);
    if (id.empty()) return;
    ShopPoints::Get().GetPoints(id);
}

void InitShop(AShooterPlayerController* /*controller*/) {
    // Loja in-game removida — interface web substitui MX-E Ark Shop UI.
}

} // namespace Data
} // namespace CustomShop
