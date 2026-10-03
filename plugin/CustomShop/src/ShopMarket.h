#pragma once

#include "pch.h"

namespace CustomShop {

class ShopMarket {
public:
    static void RegisterCommands();
    static void UnregisterCommands();

    static void CmdEnviar(AShooterPlayerController* player, FString*, EChatSendMode::Type);
    static void CmdEnviarDebug(AShooterPlayerController* player, FString*, EChatSendMode::Type);
    static void CmdConfirmar(AShooterPlayerController* player, FString*, EChatSendMode::Type);
    static void CmdRastrear(AShooterPlayerController* player, FString*, EChatSendMode::Type);
    static void CmdRastrearDebug(AShooterPlayerController* player, FString*, EChatSendMode::Type);
    /** Codigo publico do catalogo (public_code) a partir da cryopod. */
    static void CmdChecar(AShooterPlayerController* player, FString*, EChatSendMode::Type);
    static void CmdResgatarMercado(AShooterPlayerController* player, FString*, EChatSendMode::Type);
    static void CmdMercadoAdmin(AShooterPlayerController* player, FString*, EChatSendMode::Type);

    /** Pending de /enviar (dino) ativo e nao expirado — usado pela Vitrine (1 pending por jogador). */
    static bool HasPendingEnviar(const std::string& steam_id);
};

} // namespace CustomShop
