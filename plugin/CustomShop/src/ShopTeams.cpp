#include "pch.h"
#include "ShopTeams.h"
#include "ShopBridge.h"
#include "HttpClient.h"

#include <chrono>
#include <mutex>
#include <sstream>
#include <unordered_map>

namespace CustomShop {
namespace Teams {
namespace {

// Catálogo alinhado a TEAM_WAREHOUSE_RESOURCES (team_service.py).
// Match no inventário: substring da class name (ex. PrimalItemResource_BlackPearl).
struct CatalogEntry {
    const char* key;
    const char* label_pt;
    const char* class_token; // fragmento de GetFullName / BP
};

constexpr CatalogEntry kWarehouseCatalog[] = {
    {"element_ore", "Minerio de Elemento", "PrimalItemResource_ElementOre"},
    {"black_pearl", "Perola Negra", "PrimalItemResource_BlackPearl"},
    // Match do mais especifico para o generico (Polymer_* antes de Polymer).
    {"absorbent_polymer", "Polimero Absorvente", "PrimalItemResource_Polymer_Absorbant"},
    {"organic_polymer", "Polimero Organico", "PrimalItemResource_Polymer_Organic"},
    {"hard_polymer", "Polimero Duro", "PrimalItemResource_Polymer"},
    {"sand", "Areia", "PrimalItemResource_Sand"},
    {"silica_pearls", "Perolas de Silica", "PrimalItemResource_Silicon"},
    {"deathworm_horn", "Chifre de Deathworm", "PrimalItemResource_ApexDrop_DeathWorm"},
    {"ammonite_bile", "Bilis de Amonite", "PrimalItemResource_AmmoniteBlood"},
    {"element_dust", "Poeira de Elemento", "PrimalItemResource_ElementDust"},
};

std::mutex g_marco_pending_mutex;
std::unordered_map<std::string, PendingMarco> g_marco_pending;

std::string FormatBulletList(const std::vector<MarcoLine>& lines) {
    std::ostringstream oss;
    for (const auto& line : lines) {
        if (line.amount <= 0) continue;
        oss << "\n• " << line.amount << " " << line.label_pt;
    }
    return oss.str();
}

void SendEquipeMsg(AShooterPlayerController* c, const std::string& msg) {
    if (!c || msg.empty()) return;
    static const FString kSender(L"Equipe");
    // Chat ASE: preferir ASCII; Sanitize no call site se necessario.
    ArkApi::GetApiUtils().SendChatMessage(c, kSender, msg.c_str());
}

void CmdMarco(AShooterPlayerController* player, FString*, EChatSendMode::Type) {
    if (!player) return;
    // TODO: membership check via API + ScanInventory ∩ kWarehouseCatalog.
    // Enquanto o scan nao existir, nao criar pending fantasma.
    Log::GetLog()->info("ShopTeams: /marco invoked steam_id={} (stub — scan TODO)",
                        Bridge::GetSteamId(player));
    SendEquipeMsg(player,
                  "Comando /marco em preparacao. Em breve: preview + /confirmar "
                  "(sem reembolso de depositos).");
}

} // anonymous namespace

std::string FormatPreviewMessage(const std::vector<MarcoLine>& lines) {
    std::ostringstream oss;
    oss << "[+Equipe] Voce esta prestes a alimentar o armazem com:"
        << FormatBulletList(lines)
        << "\n" << kMsgNoRefundWarning
        << "\nDigite /confirmar para enviar (expira em "
        << kMarcoConfirmTtlSeconds << "s).";
    return oss.str();
}

std::string FormatSuccessMessage(const std::vector<MarcoLine>& lines) {
    std::ostringstream oss;
    oss << "[+Equipe] Voce alimentou o armazem de sua equipe com:"
        << FormatBulletList(lines);
    return oss.str();
}

bool HasPendingDeposit(const std::string& steam_id) {
    if (steam_id.empty()) return false;
    std::lock_guard<std::mutex> lock(g_marco_pending_mutex);
    const auto it = g_marco_pending.find(steam_id);
    if (it == g_marco_pending.end()) return false;
    if (std::chrono::steady_clock::now() > it->second.expires) {
        g_marco_pending.erase(it);
        return false;
    }
    return true;
}

void ClearPendingDeposit(const std::string& steam_id) {
    if (steam_id.empty()) return;
    std::lock_guard<std::mutex> lock(g_marco_pending_mutex);
    g_marco_pending.erase(steam_id);
}

bool RequestDepositPreview(AShooterPlayerController* controller) {
    (void)controller;
    // TODO: scan + set g_marco_pending[sid] com expires = now + 60s
    // + SendEquipeMsg(FormatPreviewMessage(lines)) incluindo kMsgNoRefundWarning
    return false;
}

MarcoConfirmResult ConfirmDeposit(const std::string& steam_id,
                                  AShooterPlayerController* controller,
                                  std::vector<MarcoLine>* out_lines) {
    (void)controller;
    (void)out_lines;
    if (steam_id.empty()) return MarcoConfirmResult::NoPending;

    PendingMarco pending;
    {
        std::lock_guard<std::mutex> lock(g_marco_pending_mutex);
        auto it = g_marco_pending.find(steam_id);
        if (it == g_marco_pending.end())
            return MarcoConfirmResult::NoPending;
        if (std::chrono::steady_clock::now() > it->second.expires) {
            g_marco_pending.erase(it);
            return MarcoConfirmResult::Expired;
        }
        pending = it->second;
        g_marco_pending.erase(it);
    }

    // TODO: revalidar inventário vs pending.lines
    // TODO: consumir stacks (RemovePlayerItem / qty)
    // TODO: por cada line → HttpClient::PostJson("/api/teams/bank/deposit-resource", …)
    //       idempotency_key = "marco:" + session_id + ":" + resource_key
    (void)pending;
    (void)kWarehouseCatalog;
    return MarcoConfirmResult::NoPending;
}

void RegisterCommands() {
    // Nao registar /marco no build ate o scan estar pronto (evita UX a meio).
    // Quando pronto:
    //   ArkApi::GetCommands().AddChatCommand("/marco", &CmdMarco);
    (void)&CmdMarco;
    Log::GetLog()->info(
        "ShopTeams: modulo carregado (stub). /marco ainda nao registado. "
        "Preview deve incluir: '{}'",
        kMsgNoRefundWarning);
}

void UnregisterCommands() {
    // ArkApi::GetCommands().RemoveChatCommand("/marco");
}

} // namespace Teams
} // namespace CustomShop
