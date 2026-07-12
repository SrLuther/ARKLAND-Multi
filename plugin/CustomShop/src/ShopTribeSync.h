#pragma once

#include "pch.h"

namespace CustomShop {
namespace TribeSync {

/// Envia snapshot de tribo do jogador para POST /api/tribe/presence.
/// Retorna true se a presença foi aceite pela API (tribo válida + HTTP ok).
bool SyncPlayer(AShooterPlayerController* player);

/// Agenda várias tentativas pós-login (tribo pode demorar a carregar).
void ScheduleSyncAfterLogin(AShooterPlayerController* player);

/// Sincroniza todos os jogadores online (poll / Shop.Reload / Shop.TribeSync).
/// Agenda um POST por segundo (não bloqueia N pedidos no mesmo tick).
void SyncAllOnlinePlayers();

} // namespace TribeSync
} // namespace CustomShop
