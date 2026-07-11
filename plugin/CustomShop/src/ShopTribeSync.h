#pragma once

#include "pch.h"

namespace CustomShop {
namespace TribeSync {

/// Envia snapshot de tribo do jogador para POST /api/tribe/presence.
/// Chamado no HandleNewPlayer (com delay) para o painel Minha Tribo vincular o mapa.
void SyncPlayer(AShooterPlayerController* player);

} // namespace TribeSync
} // namespace CustomShop
