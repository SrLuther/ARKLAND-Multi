#pragma once

#include "pch.h"

#include <chrono>
#include <string>
#include <vector>

namespace CustomShop {
namespace Teams {

// ─────────────────────────────────────────────────────────────────
//  Modo Equipe — /marco → preview → /confirmar
//  Spec: docs/PROJETO_MODO_EQUIPE.md §5.5
//
//  Decisão produto: /marco NÃO deposita de imediato.
//  Pending kind = "marco" (coexiste com market/engramas/notas).
//  TTL default = 60s. Depósitos de recursos SEM reembolso
//  (aviso obrigatório no preview).
//
//  TODO implementação:
//    1. Scan inventário ∩ catálogo (10 BPs) → PendingMarco
//    2. RegisterCommands: AddChatCommand("/marco", …)
//    3. ShopMarket::CmdConfirmar — ramo HasPendingDeposit
//       (após Notes, antes do pending de Comércio)
//    4. Confirm: revalidar → consumir stacks → POST
//       /api/teams/bank/deposit-resource (por key + idempotency)
// ─────────────────────────────────────────────────────────────────

constexpr int kMarcoConfirmTtlSeconds = 60;

struct MarcoLine {
    std::string resource_key;
    std::string label_pt;
    int amount = 0;
};

struct PendingMarco {
    std::chrono::steady_clock::time_point expires;
    std::vector<MarcoLine> lines;
    std::string session_id; // para idempotency_key
};

// Mensagens travadas (ASCII-safe no chat ASE quando possível).
inline constexpr const char* kMsgNoTeam =
    "[-] Nao pertences a nenhuma equipe.";
inline constexpr const char* kMsgNoValidResources =
    "Sem recursos validos necessarios para sua equipe";
inline constexpr const char* kMsgNoPending =
    "[-] Nenhum envio /marco pendente.";
inline constexpr const char* kMsgExpired =
    "[-] O envio expirou. Usa /marco de novo.";
inline constexpr const char* kMsgApiFail =
    "[-] Falha ao creditar o armazem. Tenta de novo.";
inline constexpr const char* kMsgNoRefundWarning =
    "Atencao: nao ha reembolso de depositos de recursos.";

// Preview: "[+Equipe] Voce esta prestes a alimentar o armazem com:"
// + bullets + kMsgNoRefundWarning + "Digite /confirmar ... (expira em 60s)."
std::string FormatPreviewMessage(const std::vector<MarcoLine>& lines);

// Sucesso: "[+Equipe] Voce alimentou o armazem de sua equipe com:" + bullets
std::string FormatSuccessMessage(const std::vector<MarcoLine>& lines);

bool HasPendingDeposit(const std::string& steam_id);
void ClearPendingDeposit(const std::string& steam_id);

enum class MarcoConfirmResult {
    Ok,
    NoPending,
    Expired,
    InventoryMismatch,
    ApiFailed,
    NoTeam,
};

// /marco passo 1 — scan + pending (sem consumir). Stub: ainda nao implementado.
bool RequestDepositPreview(AShooterPlayerController* controller);

// /confirmar ramo marco — consumir + creditar armazem.
MarcoConfirmResult ConfirmDeposit(const std::string& steam_id,
                                  AShooterPlayerController* controller,
                                  std::vector<MarcoLine>* out_lines = nullptr);

void RegisterCommands();
void UnregisterCommands();

} // namespace Teams
} // namespace CustomShop
