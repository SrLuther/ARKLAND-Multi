#pragma once

#include "pch.h"

namespace CustomShop {
namespace TribeSync {

/// Lê tribo in-game e grava presença (MySQL arkland_shop e/ou HTTP).
/// Retorna true se MySQL ou HTTP aceitou o snapshot.
bool SyncPlayer(AShooterPlayerController* player);

/// Agenda várias tentativas pós-login (tribo pode demorar a carregar).
void ScheduleSyncAfterLogin(AShooterPlayerController* player);

/// Sincroniza todos os jogadores online (poll ~3 min / Shop.Reload / Shop.TribeSync).
/// Agenda um sync por segundo (não bloqueia N pedidos no mesmo tick).
void SyncAllOnlinePlayers();

/// Pull: reclama tribe_sync_requests pending na MySQL para jogadores online
/// e executa SyncPlayer (caminho principal do «Verificar de novo», sem RCON).
void PollPendingSyncRequests();

} // namespace TribeSync
} // namespace CustomShop
