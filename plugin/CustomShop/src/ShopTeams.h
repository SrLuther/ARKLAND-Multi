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
//  /marco NÃO deposita de imediato.
//  Pending kind = "marco" (coexiste com market/engramas/notas).
//  TTL default = 60s. Depósitos de recursos SEM reembolso
//  (aviso obrigatório no preview).
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

// Mensagens travadas (ASCII-safe no chat ASE).
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
inline constexpr const char* kMsgInventoryMismatch =
    "[-] Inventario mudou. Usa /marco de novo.";
inline constexpr const char* kMsgNoRefundWarning =
    "Atencao: nao ha reembolso de depositos de recursos.";

std::string FormatPreviewMessage(const std::vector<MarcoLine>& lines,
                                 int ttl_sec = kMarcoConfirmTtlSeconds);
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

// /marco passo 1 — scan + pending (sem consumir).
bool RequestDepositPreview(AShooterPlayerController* controller);

// /confirmar ramo marco — consumir + creditar armazem.
MarcoConfirmResult ConfirmDeposit(const std::string& steam_id,
                                  AShooterPlayerController* controller,
                                  std::vector<MarcoLine>* out_lines = nullptr);

void RegisterCommands();
void UnregisterCommands();

} // namespace Teams
} // namespace CustomShop
