#pragma once

#include "pch.h"

namespace CustomShop {

class ShopMarket {
public:
    static void RegisterCommands();
    static void UnregisterCommands();

    static void CmdEnviar(AShooterPlayerController* player, FString*, EChatSendMode::Type);
    static void CmdConfirmar(AShooterPlayerController* player, FString*, EChatSendMode::Type);
    static void CmdResgatarMercado(AShooterPlayerController* player, FString*, EChatSendMode::Type);
};

} // namespace CustomShop
