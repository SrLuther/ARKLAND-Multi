#pragma once

#include "pch.h"

#include <string>

// ─────────────────────────────────────────────────────────────────
//  Vitrine de Recursos — mercado P2P de recursos (somente Ambar).
//  Contrato da API: docs/VITRINE_RECURSOS_SPEC.md
//
//  /vitrine    -> le o inventario PESSOAL, filtra recursos autorizados (API),
//                 lista no chat e grava pending (1 por jogador, TTL).
//  /confirmar  -> (ramo em ShopMarket::CmdConfirmar, ordem:
//                 engramas -> notas -> marco -> VITRINE -> mercado/enviar)
//                 journal -> remove itens -> POST upload (upload_id idempotente)
//                 -> falhou: cancel + devolve itens; sem resposta: mantem journal.
//  /mercado    -> entrega claims de recursos (BUY e WITHDRAW) junto aos dinos.
//
//  Seguranca dos itens: NUNCA perder nem duplicar. Journal em
//  ArkApi/Plugins/CustomShop/vitrine_journal/<upload_id>.json.
// ─────────────────────────────────────────────────────────────────

namespace CustomShop {
namespace Vitrine {

/** Pending do /vitrine ativo (nao expirado) para o jogador. */
bool HasPending(const std::string& steam_id);
void ClearPending(const std::string& steam_id);

/** Mensagem padrao quando outro fluxo /confirmar impede um novo pending. */
inline constexpr const char* kMsgPendingBlocks =
    "Voce tem um envio da /vitrine aguardando /confirmar. "
    "Digite /confirmar para concluir ou aguarde expirar antes de iniciar outro comando.";

/** /confirmar — ramo da vitrine (chamado quando HasPending(sid)). Envia as proprias mensagens. */
void ConfirmPending(AShooterPlayerController* player);

/**
 * Recupera journals pendentes do jogador (login, /vitrine, /mercado).
 * Seguro de chamar sempre; nao faz nada sem journal.
 */
void RecoverForPlayer(AShooterPlayerController* player);

/** Recupera por SteamID (resolve o controller online; usado em timers de login). */
void RecoverForSteamId(const std::string& steam_id);

/** Varre todos os journals (inicio do mapa): conclui o que nao exige o jogador online. */
void RecoverAll();

/**
 * /mercado — entrega pendencias de recursos (compras e retiradas) do jogador.
 * Anuncia as pendencias no chat; retorna true se havia ao menos uma pendencia
 * (entregue ou nao), para o chamador nao dizer "nada pendente".
 */
bool DeliverMarketClaims(AShooterPlayerController* player);

/** Consulta leve (1 GET) para saber se ha recursos pendentes sem entregar. */
bool HasMarketClaims(const std::string& steam_id);

void RegisterCommands();
void UnregisterCommands();

} // namespace Vitrine
} // namespace CustomShop
