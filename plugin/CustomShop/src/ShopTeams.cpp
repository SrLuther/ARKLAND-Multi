#include "pch.h"
#include "ShopTeams.h"
#include "ShopBridge.h"
#include "ShopCloudInventory.h"
#include "HttpClient.h"

#include <algorithm>
#include <chrono>
#include <mutex>
#include <random>
#include <sstream>
#include <unordered_map>
#include <vector>

namespace CustomShop {
namespace Teams {
namespace {

// Catálogo alinhado a TEAM_WAREHOUSE_RESOURCES (team_service.py).
// Match: substring da class name (mais específico antes do genérico).
struct CatalogEntry {
    const char* key;
    const char* label_pt;
    const char* class_token;
};

constexpr CatalogEntry kWarehouseCatalog[] = {
    {"element_ore", "Minerio de Elemento", "PrimalItemResource_ElementOre"},
    {"black_pearl", "Perola Negra", "PrimalItemResource_BlackPearl"},
    // SubstrateAbsorbent antes de Polymer_* genericos.
    {"substrate_absorbent", "Substrato Absorvente", "PrimalItemResource_SubstrateAbsorbent"},
    {"organic_polymer", "Polimero Organico", "PrimalItemResource_Polymer_Organic"},
    {"hard_polymer", "Polimero Duro", "PrimalItemResource_Polymer"},
    {"sand", "Areia", "PrimalItemResource_Sand"},
    {"silica_pearls", "Perolas de Silica", "PrimalItemResource_Silicon"},
    {"deathworm_horn", "Chifre de Deathworm", "PrimalItemResource_KeratinSpike"},
    {"ammonite_bile", "Bilis de Amonite", "PrimalItemResource_AmmoniteBlood"},
    {"element_dust", "Po de Elemento", "PrimalItemResource_ElementDust"},
};

constexpr size_t kCatalogCount = sizeof(kWarehouseCatalog) / sizeof(kWarehouseCatalog[0]);

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
    ArkApi::GetApiUtils().SendChatMessage(c, kSender, msg.c_str());
}

std::string MakeSessionId(const std::string& steam_id) {
    static thread_local std::mt19937_64 rng{std::random_device{}()};
    std::uniform_int_distribution<uint64_t> dist;
    const auto now = std::chrono::duration_cast<std::chrono::milliseconds>(
                         std::chrono::system_clock::now().time_since_epoch())
                         .count();
    std::ostringstream oss;
    oss << steam_id << "-" << now << "-" << std::hex << dist(rng);
    return oss.str();
}

const CatalogEntry* MatchCatalog(const std::string& full_name) {
    for (size_t i = 0; i < kCatalogCount; ++i) {
        if (full_name.find(kWarehouseCatalog[i].class_token) != std::string::npos)
            return &kWarehouseCatalog[i];
    }
    return nullptr;
}

std::string ItemClassName(UPrimalItem* item) {
    if (!item) return {};
    UClass* cls = item->ClassField();
    if (!cls) return {};
    FString class_name;
    cls->GetFullName(&class_name, nullptr);
    return class_name.ToString();
}

std::vector<MarcoLine> ScanWarehouseInventory(AShooterPlayerController* controller) {
    std::vector<MarcoLine> lines;
    if (!controller) return lines;

    UPrimalInventoryComponent* inv = controller->GetPlayerInventoryComponent();
    if (!inv) return lines;

    std::unordered_map<std::string, int> totals;
    std::unordered_map<std::string, std::string> labels;

    const auto collect = [&](TArray<UPrimalItem*> items) {
        for (int i = 0; i < items.Num(); ++i) {
            UPrimalItem* item = items[i];
            if (!item) continue;
            if (item->bIsEngram().Get()) continue;
            const int qty = item->GetItemQuantity();
            if (qty <= 0) continue;
            const auto* entry = MatchCatalog(ItemClassName(item));
            if (!entry) continue;
            totals[entry->key] += qty;
            labels[entry->key] = entry->label_pt;
        }
    };

    collect(inv->InventoryItemsField());
    collect(inv->ItemSlotsField());
    // Nao incluir EquippedItems — recursos raros nao se equipam; evita falso positivo.

    for (size_t i = 0; i < kCatalogCount; ++i) {
        const auto& cat = kWarehouseCatalog[i];
        const auto it = totals.find(cat.key);
        if (it == totals.end() || it->second <= 0) continue;
        MarcoLine line;
        line.resource_key = cat.key;
        line.label_pt = labels.count(cat.key) ? labels[cat.key] : cat.label_pt;
        line.amount = it->second;
        lines.push_back(std::move(line));
    }
    return lines;
}

struct MembershipInfo {
    bool active = false;
    int marco_preview_ttl_sec = kMarcoConfirmTtlSeconds;
};

MembershipInfo FetchMembership(const std::string& steam_id) {
    MembershipInfo info;
    if (steam_id.empty()) return info;
    const std::string resp =
        HttpClient::Get("/api/teams/plugin/membership/" + steam_id);
    if (resp.empty()) return info;
    try {
        const auto json = nlohmann::json::parse(resp);
        if (!json.value("ok", false)) return info;
        const nlohmann::json& data =
            (json.contains("data") && json["data"].is_object()) ? json["data"] : json;
        info.active = data.value("active", false);
        int ttl = data.value("marco_preview_ttl_sec", kMarcoConfirmTtlSeconds);
        if (ttl < 15) ttl = 15;
        if (ttl > 600) ttl = 600;
        info.marco_preview_ttl_sec = ttl;
    } catch (...) {
        return info;
    }
    return info;
}

bool PlayerHasActiveTeam(const std::string& steam_id) {
    return FetchMembership(steam_id).active;
}

bool ConsumeWarehouseItems(AShooterPlayerController* controller,
                           const std::vector<MarcoLine>& to_take) {
    if (!controller) return false;
    UPrimalInventoryComponent* inv = controller->GetPlayerInventoryComponent();
    if (!inv) return false;

    auto& cloud = ShopCloudInventory::Get();

    for (const auto& line : to_take) {
        if (line.amount <= 0) continue;
        int remaining = line.amount;

        std::vector<UPrimalItem*> stacks;
        const auto collect = [&](TArray<UPrimalItem*> items) {
            for (int i = 0; i < items.Num(); ++i) {
                UPrimalItem* item = items[i];
                if (!item || item->bIsEngram().Get()) continue;
                const auto* entry = MatchCatalog(ItemClassName(item));
                if (!entry || entry->key != line.resource_key) continue;
                stacks.push_back(item);
            }
        };
        collect(inv->InventoryItemsField());
        collect(inv->ItemSlotsField());

        for (UPrimalItem* item : stacks) {
            if (remaining <= 0) break;
            if (!item) continue;
            const int qty = item->GetItemQuantity();
            if (qty <= 0) continue;

            if (qty <= remaining) {
                if (!cloud.RemovePlayerItem(item, inv, controller)) {
                    Log::GetLog()->error(
                        "ShopTeams: failed to remove stack key={} qty={}",
                        line.resource_key, qty);
                    return false;
                }
                remaining -= qty;
            } else {
                const int left = qty - remaining;
                item->SetQuantity(left, /*ShowHUDNotification=*/false);
                inv->NotifyItemQuantityUpdated(item, -remaining);
                inv->NotifyClientsItemStatus(
                    item, /*bEquippedItem=*/false, /*bRemovedItem=*/false,
                    /*bOnlyUpdateQuantity=*/true, false, false,
                    nullptr, nullptr, false, false, false);
                remaining = 0;
            }
        }

        if (remaining > 0) {
            Log::GetLog()->warn(
                "ShopTeams: shortfall after consume key={} remaining={}",
                line.resource_key, remaining);
            return false;
        }
    }

    (void)inv;
    return true;
}

bool PostDepositLines(const std::string& steam_id,
                      const std::string& session_id,
                      const std::vector<MarcoLine>& lines) {
    bool all_ok = true;
    for (const auto& line : lines) {
        if (line.amount <= 0) continue;
        nlohmann::json body;
        body["steam_id"] = steam_id;
        body["resource_key"] = line.resource_key;
        body["amount"] = line.amount;
        body["idempotency_key"] = "marco:" + session_id + ":" + line.resource_key;
        body["note"] = "/marco";

        const std::string resp =
            HttpClient::PostJson("/api/teams/bank/deposit-resource", body.dump());
        bool ok = false;
        try {
            if (!resp.empty()) {
                const auto json = nlohmann::json::parse(resp);
                ok = json.value("ok", false);
            }
        } catch (...) {
            ok = false;
        }
        if (!ok) {
            Log::GetLog()->error(
                "ShopTeams: deposit-resource failed key={} amount={} resp={}",
                line.resource_key, line.amount, resp);
            all_ok = false;
        }
    }
    return all_ok;
}

void CmdMarco(AShooterPlayerController* player, FString*, EChatSendMode::Type) {
    if (!player) return;
    RequestDepositPreview(player);
}

} // anonymous namespace

std::string FormatPreviewMessage(const std::vector<MarcoLine>& lines, int ttl_sec) {
    if (ttl_sec < 15) ttl_sec = kMarcoConfirmTtlSeconds;
    std::ostringstream oss;
    oss << "[+Equipe] Voce esta prestes a alimentar o armazem com:"
        << FormatBulletList(lines)
        << "\n" << kMsgNoRefundWarning
        << "\nDigite /confirmar para enviar (expira em "
        << ttl_sec << "s).";
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
    if (!controller) return false;
    const std::string sid = Bridge::GetSteamId(controller);
    if (sid.empty()) return false;

    const MembershipInfo mem = FetchMembership(sid);
    if (!mem.active) {
        SendEquipeMsg(controller, kMsgNoTeam);
        return false;
    }
    const int ttl = mem.marco_preview_ttl_sec > 0
                        ? mem.marco_preview_ttl_sec
                        : kMarcoConfirmTtlSeconds;

    auto lines = ScanWarehouseInventory(controller);
    if (lines.empty()) {
        SendEquipeMsg(controller, kMsgNoValidResources);
        return false;
    }

    PendingMarco pending;
    pending.expires = std::chrono::steady_clock::now()
                      + std::chrono::seconds(ttl);
    pending.lines = lines;
    pending.session_id = MakeSessionId(sid);

    {
        std::lock_guard<std::mutex> lock(g_marco_pending_mutex);
        g_marco_pending[sid] = pending;
    }

    SendEquipeMsg(controller, FormatPreviewMessage(lines, ttl));
    Log::GetLog()->info(
        "ShopTeams: /marco preview steam={} lines={} session={} ttl={}s",
        sid, lines.size(), pending.session_id, ttl);
    return true;
}

MarcoConfirmResult ConfirmDeposit(const std::string& steam_id,
                                  AShooterPlayerController* controller,
                                  std::vector<MarcoLine>* out_lines) {
    if (steam_id.empty() || !controller) return MarcoConfirmResult::NoPending;

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

    if (!PlayerHasActiveTeam(steam_id))
        return MarcoConfirmResult::NoTeam;

    // Revalidar: usar min(pending, disponivel). Se nada sobrar → mismatch.
    const auto available = ScanWarehouseInventory(controller);
    std::unordered_map<std::string, int> avail_map;
    for (const auto& a : available)
        avail_map[a.resource_key] = a.amount;

    std::vector<MarcoLine> to_take;
    to_take.reserve(pending.lines.size());
    for (const auto& line : pending.lines) {
        const int have = avail_map.count(line.resource_key)
                             ? avail_map[line.resource_key]
                             : 0;
        const int take = std::min(line.amount, have);
        if (take <= 0) continue;
        MarcoLine adjusted = line;
        adjusted.amount = take;
        to_take.push_back(std::move(adjusted));
    }

    if (to_take.empty())
        return MarcoConfirmResult::InventoryMismatch;

    if (!ConsumeWarehouseItems(controller, to_take))
        return MarcoConfirmResult::InventoryMismatch;

    if (!PostDepositLines(steam_id, pending.session_id, to_take))
        return MarcoConfirmResult::ApiFailed;

    if (out_lines) *out_lines = to_take;
    Log::GetLog()->info(
        "ShopTeams: /confirmar marco OK steam={} lines={} session={}",
        steam_id, to_take.size(), pending.session_id);
    return MarcoConfirmResult::Ok;
}

void RegisterCommands() {
    ArkApi::GetCommands().AddChatCommand("/marco", &CmdMarco);
    Log::GetLog()->info(
        "ShopTeams: /marco registado (preview → /confirmar, TTL {}s)",
        kMarcoConfirmTtlSeconds);
}

void UnregisterCommands() {
    ArkApi::GetCommands().RemoveChatCommand("/marco");
}

} // namespace Teams
} // namespace CustomShop
