#include "pch.h"
#include "ShopMarket.h"
#include "ShopBridge.h"
#include "ShopCloudInventory.h"
#include "ShopCryoReader.h"
#include "ShopConfig.h"
#include "HttpClient.h"

#include <chrono>
#include <cmath>
#include <mutex>
#include <random>
#include <unordered_map>

namespace {

std::string HexEncode(const TArray<unsigned char>& bytes) {
    static const char* kHex = "0123456789ABCDEF";
    std::string out;
    const int n = bytes.Num();
    out.reserve(static_cast<size_t>(n) * 2);
    for (int i = 0; i < n; ++i) {
        const unsigned char b = bytes[i];
        out.push_back(kHex[b >> 4]);
        out.push_back(kHex[b & 0x0F]);
    }
    return out;
}

TArray<unsigned char> HexDecode(const std::string& hex) {
    TArray<unsigned char> arr;
    auto nibble = [](char ch) -> int {
        if (ch >= '0' && ch <= '9') return ch - '0';
        if (ch >= 'a' && ch <= 'f') return ch - 'a' + 10;
        if (ch >= 'A' && ch <= 'F') return ch - 'A' + 10;
        return -1;
    };
    for (size_t i = 0; i + 1 < hex.size(); i += 2) {
        const int hi = nibble(hex[i]);
        const int lo = nibble(hex[i + 1]);
        if (hi < 0 || lo < 0) break;
        arr.Add(static_cast<unsigned char>((hi << 4) | lo));
    }
    return arr;
}

std::string NewUploadId() {
    static thread_local std::mt19937 rng{std::random_device{}()};
    std::uniform_int_distribution<int> dist(0, 15);
    std::string out;
    out.reserve(32);
    for (int i = 0; i < 32; ++i)
        out.push_back("0123456789abcdef"[dist(rng)]);
    return out;
}

struct PendingUpload {
    std::chrono::steady_clock::time_point expires;
    CustomShop::CryoParsedMetadata meta;
};

std::mutex g_pending_mutex;
std::unordered_map<std::string, PendingUpload> g_pending;
std::mutex g_confirm_exec_mutex;

std::string SanitizeForGameChat(std::string msg) {
    std::string out;
    out.reserve(msg.size());
    for (unsigned char ch : msg) {
        if (ch >= 32 && ch <= 126)
            out.push_back(static_cast<char>(ch));
    }
    while (!out.empty() && out.back() == ' ')
        out.pop_back();
    return out.empty() ? std::string("Erro desconhecido") : out;
}

void SendMsg(AShooterPlayerController* c, const FLinearColor& /*color*/, const std::string& msg) {
    if (!c || msg.empty()) return;
    static const FString kSender(L"Comercio");
    ArkApi::GetApiUtils().SendChatMessage(c, kSender, SanitizeForGameChat(msg).c_str());
}

std::string FormatAmbar(int value) {
    std::string s = std::to_string(value);
    for (int i = static_cast<int>(s.size()) - 3; i > 0; i -= 3)
        s.insert(static_cast<size_t>(i), ".");
    return s;
}

void SendEconomyBreakdown(AShooterPlayerController* player, const nlohmann::json& json) {
    if (!player || !json.is_object()) return;
    const int total = json.value("computed_base_value", 0);
    if (total > 0)
        SendMsg(player, FColorList::Yellow,
                "Como calculamos — sugerido: " + FormatAmbar(total) + " Ambar");
    const auto& rows = json.value("calculation_breakdown", nlohmann::json::array());
    int lines = 0;
    for (const auto& row : rows) {
        if (lines >= 5) break;
        const std::string kind = row.value("kind", "");
        if (kind != "root" && kind != "bonus_space" && kind != "stat")
            continue;
        const std::string label = SanitizeForGameChat(row.value("label", ""));
        const int sub = row.value("subtotal", 0);
        if (kind == "stat") {
            const int pts = row.value("points", 0);
            const int mult = row.value("multiplier", 0);
            SendMsg(player, FColorList::Yellow,
                    label + ": " + std::to_string(pts) + " pts x " + std::to_string(mult)
                    + " = " + FormatAmbar(sub));
        } else {
            SendMsg(player, FColorList::Yellow, label + ": " + FormatAmbar(sub));
        }
        ++lines;
    }
}

/** Chat in-game nao suporta UTF-8 — mensagens da web precisam ir em ASCII. */

std::string CommerceNotReadyMessage() {
    return "Defina seu nome de exibicao em Minha Area (web) antes de usar /enviar.";
}

bool ProfileCommerceReady(const std::string& steam_id, std::string* error_out) {
    const std::string resp = CustomShop::HttpClient::Get("/api/market/plugin/profile/" + steam_id);
    nlohmann::json json;
    try {
        json = nlohmann::json::parse(resp);
    } catch (...) {
        if (error_out) *error_out = "Comercio indisponivel (web)";
        return false;
    }
    if (!json.value("ok", false) || !json.value("commerce_ready", false)) {
        if (error_out)
            *error_out = CommerceNotReadyMessage();
        return false;
    }
    return true;
}

void ReleaseClaims(const std::string& steam_id, const std::vector<int>& claim_ids) {
    if (claim_ids.empty()) return;
    nlohmann::json body{{"steam_id", steam_id}, {"claim_ids", nlohmann::json::array()}};
    for (int id : claim_ids)
        body["claim_ids"].push_back(id);
    CustomShop::HttpClient::PostJson("/api/market/claims/release", body.dump());
}

void SendCryoDebugReport(AShooterPlayerController* player, const std::string& steam_id,
                         const char* stage, bool to_chat) {
    CustomShop::CryoInventoryDebugReport report;
    CustomShop::BuildCryoInventoryDebugReport(player, report);
    CustomShop::LogCryoInventoryDebugReport(steam_id, stage, report);
    if (!to_chat || !player) return;
    for (const std::string& line : CustomShop::CryoInventoryDebugChatLines(report)) {
        SendMsg(player, FColorList::Yellow, SanitizeForGameChat(line));
    }
}

std::string FormatCryoDaysForChat(float days) {
    if (days < 0.f) return "permanente";
    return std::to_string(static_cast<int>(std::floor(days))) + " dia(s)";
}

bool ValidateMarketCryoTimer(AShooterPlayerController* player, UPrimalItem* cryo,
                             const std::string& sid, const char* stage, float min_days) {
    if (!CustomShop::ShopConfig::Get().MarketCryoRequireMinDays())
        return true;
    if (min_days <= 0.f)
        return true;
    if (CustomShop::CryopodMeetsMarketTimerRequirement(cryo, min_days))
        return true;
    const float rem = CustomShop::GetCryopodRemainingDays(cryo);
    SendMsg(player, FColorList::Red,
            "Cryopod precisa ter pelo menos " + std::to_string(static_cast<int>(min_days))
            + " dias de timer (atual: " + FormatCryoDaysForChat(rem)
            + "). Recarregue o tempo da cryopod no Cryofridge e tente novamente.");
    SendCryoDebugReport(player, sid, stage, CustomShop::ShopConfig::Get().MarketCryoDebug());
    return false;
}

} // anonymous namespace

namespace CustomShop {

void ShopMarket::RegisterCommands() {
    ArkApi::GetCommands().AddChatCommand("/enviar", &ShopMarket::CmdEnviar);
    ArkApi::GetCommands().AddChatCommand("/enviardebug", &ShopMarket::CmdEnviarDebug);
    ArkApi::GetCommands().AddChatCommand("/confirmar", &ShopMarket::CmdConfirmar);
    ArkApi::GetCommands().AddChatCommand("/resgatarmercado", &ShopMarket::CmdResgatarMercado);
}

void ShopMarket::UnregisterCommands() {
    ArkApi::GetCommands().RemoveChatCommand("/enviar");
    ArkApi::GetCommands().RemoveChatCommand("/enviardebug");
    ArkApi::GetCommands().RemoveChatCommand("/confirmar");
    ArkApi::GetCommands().RemoveChatCommand("/resgatarmercado");
}

void ShopMarket::CmdEnviar(AShooterPlayerController* player, FString*, EChatSendMode::Type) {
    if (!player) return;
    const std::string sid = Bridge::GetSteamId(player);
    if (!ShopCloudInventory::Get().HasCloudLicense(sid, true)) {
        SendMsg(player, FColorList::Red,
                "Licenca Nuvem obrigatoria para enviar dinos ao Comercio.");
        return;
    }

    std::string profile_err;
    if (!ProfileCommerceReady(sid, &profile_err)) {
        SendMsg(player, FColorList::Red, profile_err);
        return;
    }

    UPrimalItem* cryo = FindCryopodInInventory(player, -1);
    if (!cryo) {
        SendMsg(player, FColorList::Red,
                "Nenhuma cryopod valida no inventario. Equipe uma cryo preenchida "
                "legivel (cryos vazias ou corrompidas sao ignoradas).");
        SendCryoDebugReport(player, sid, "enviar_no_cryo",
                            ShopConfig::Get().MarketCryoDebug());
        return;
    }

    CryoParsedMetadata meta;
    std::string err;
    if (!ParseCryopodItem(cryo, meta, &err, player)) {
        SendMsg(player, FColorList::Red, "Cryopod invalida: " + err);
        SendCryoDebugReport(player, sid, "enviar_parse_fail", true);
        return;
    }
    if (meta.imprint_pct < 0.999f) {
        SendMsg(player, FColorList::Red, "Imprint 100% obrigatorio para o Comercio.");
        SendCryoDebugReport(player, sid, "enviar_imprint", ShopConfig::Get().MarketCryoDebug());
        return;
    }

    const float min_days = ShopConfig::Get().MarketCryoMinDaysRemaining();
    if (!ValidateMarketCryoTimer(player, cryo, sid, "enviar_timer", min_days))
        return;

    ApplyCryoTimerFieldsToMetadata(cryo, meta);

    PendingUpload pending;
    pending.meta = meta;
    pending.expires = std::chrono::steady_clock::now() + std::chrono::minutes(2);
    {
        std::lock_guard<std::mutex> lock(g_pending_mutex);
        g_pending[sid] = pending;
    }

    SendMsg(player, FColorList::Green,
            "Preview: " + meta.name_map + " | imprint "
            + std::to_string(static_cast<int>(meta.imprint_pct * 100)) + "% | mut "
            + std::to_string(meta.mutations_male) + "/" + std::to_string(meta.mutations_female));
    if (meta.timer_remaining_days >= 0.f) {
        SendMsg(player, FColorList::Yellow,
                "Timer: " + FormatCryoDaysForChat(meta.timer_remaining_days)
                + " restantes (minimo " + std::to_string(static_cast<int>(min_days))
                + " para enviar). Timer sera mantido no Comercio.");
    } else {
        SendMsg(player, FColorList::Yellow, "Cryopod permanente (sem timer de decay).");
    }
    SendMsg(player, FColorList::Yellow,
            "Digite /confirmar em ate 2 minutos para enviar ao Comercio (cryopod sera removida).");

    nlohmann::json preview_body;
    preview_body["metadata"] = CryoMetadataToJson(meta);
    const std::string preview_resp = HttpClient::PostJson("/api/market/plugin/preview", preview_body.dump());
    nlohmann::json preview_json;
    try {
        preview_json = nlohmann::json::parse(preview_resp);
    } catch (...) {
        preview_json = nlohmann::json::object();
    }
    if (preview_json.value("ok", false)) {
        const int suggested = preview_json.value("computed_base_value", 0);
        if (suggested > 0) {
            SendEconomyBreakdown(player, preview_json);
        } else if (preview_json.contains("message")) {
            SendMsg(player, FColorList::Yellow,
                    SanitizeForGameChat(preview_json.value("message", std::string())));
        }
    }
}

void ShopMarket::CmdEnviarDebug(AShooterPlayerController* player, FString*, EChatSendMode::Type) {
    if (!player) return;
    const std::string sid = Bridge::GetSteamId(player);
    SendMsg(player, FColorList::Yellow, "Diagnostico cryopod Comercio (detalhes no log do servidor).");
    SendCryoDebugReport(player, sid, "enviardebug", true);
}

void ShopMarket::CmdConfirmar(AShooterPlayerController* player, FString*, EChatSendMode::Type) {
    if (!player) return;
    const std::string sid = Bridge::GetSteamId(player);

    std::lock_guard<std::mutex> confirm_lock(g_confirm_exec_mutex);

    PendingUpload pending;
    {
        std::lock_guard<std::mutex> lock(g_pending_mutex);
        auto it = g_pending.find(sid);
        if (it == g_pending.end()) {
            SendMsg(player, FColorList::Red, "Nenhum envio pendente. Use /enviar primeiro.");
            return;
        }
        if (std::chrono::steady_clock::now() > it->second.expires) {
            g_pending.erase(it);
            SendMsg(player, FColorList::Red, "Preview expirado. Use /enviar novamente.");
            return;
        }
        pending = it->second;
        g_pending.erase(it);
    }

    UPrimalItem* cryo = FindCryopodMatchingMeta(player, pending.meta);
    if (!cryo) {
        SendMsg(player, FColorList::Red,
                "Cryopod do preview nao encontrada. Use /enviar novamente (mesma cryopod).");
        return;
    }

    const float min_days = ShopConfig::Get().MarketCryoMinDaysRemaining();
    if (!ValidateMarketCryoTimer(player, cryo, sid, "confirmar_timer", min_days)) {
        std::lock_guard<std::mutex> lock(g_pending_mutex);
        g_pending[sid] = pending;
        return;
    }

    ApplyCryoTimerFieldsToMetadata(cryo, pending.meta);

    FCustomItemByteArray bytes;
    cryo->GetItemBytes(&bytes.Bytes);
    if (bytes.Bytes.Num() <= 0) {
        SendMsg(player, FColorList::Red, "Falha ao serializar cryopod.");
        return;
    }

    UPrimalItem* probe = UPrimalItem::CreateFromBytes(&bytes.Bytes);
    if (!probe) {
        SendMsg(player, FColorList::Red, "Cryopod corrompida - envio cancelado.");
        return;
    }

    const std::string hex = HexEncode(bytes.Bytes);
    const std::string upload_id = NewUploadId();

    UPrimalInventoryComponent* inv = player->GetPlayerInventoryComponent();
    if (!inv || !ShopCloudInventory::Get().RemovePlayerItem(cryo, inv, player)) {
        SendMsg(player, FColorList::Red, "Falha ao remover cryopod do inventario.");
        return;
    }

    nlohmann::json body;
    body["steam_id"] = sid;
    body["inventory_removed"] = true;
    body["inventory_verified_empty"] = true;
    body["item_blob_hex"] = hex;
    body["upload_id"] = upload_id;
    body["market_trace_id"] = upload_id;
    body["parser_version"] = "1.0.0";
    body["plugin_version"] = "CustomShop";
    body["metadata"] = CryoMetadataToJson(pending.meta);

    const std::string resp = HttpClient::PostJson("/api/market/upload", body.dump());
    nlohmann::json json;
    try {
        json = nlohmann::json::parse(resp);
    } catch (...) {
        json = nlohmann::json{{"ok", false}, {"error", "resposta invalida"}};
    }

    if (!json.value("ok", false)) {
        Log::GetLog()->warn("ShopMarket: upload failed steam={} resp={}", sid, resp);
        UPrimalItem* restored = UPrimalItem::CreateFromBytes(&bytes.Bytes);
        if (restored && inv) {
            inv->AddItemObject(restored);
            SendMsg(player, FColorList::Yellow,
                    "Falha no servidor - cryopod devolvida. Motivo: "
                    + SanitizeForGameChat(json.value("error", std::string("erro desconhecido"))));
        } else {
            SendMsg(player, FColorList::Red,
                    "FALHA CRITICA: cryopod removida mas upload falhou. Contate admin.");
        }
        return;
    }

    SendMsg(player, FColorList::Green,
            "Dino enviado ao Comercio! Listing #" + std::to_string(json.value("listing_id", 0))
            + " - defina preco na web.");
    SendEconomyBreakdown(player, json);
}

void ShopMarket::CmdResgatarMercado(AShooterPlayerController* player, FString*, EChatSendMode::Type) {
    if (!player) return;
    const std::string sid = Bridge::GetSteamId(player);
    const std::string resp = HttpClient::Get("/api/market/pending/" + sid);
    nlohmann::json json;
    try {
        json = nlohmann::json::parse(resp);
    } catch (...) {
        SendMsg(player, FColorList::Red, "Erro ao consultar resgates do Comercio.");
        return;
    }
    if (!json.value("ok", false)) {
        SendMsg(player, FColorList::Red, "Comercio indisponivel.");
        return;
    }
    const auto& claims = json.value("claims", nlohmann::json::array());
    if (claims.empty()) {
        SendMsg(player, FColorList::Yellow, "Nenhum dino pendente no Comercio.");
        return;
    }

    UPrimalInventoryComponent* inv = player->GetPlayerInventoryComponent();
    if (!inv) {
        SendMsg(player, FColorList::Red, "Inventario indisponivel.");
        return;
    }

    int delivered = 0;
    std::vector<int> claimed_ids;

    for (const auto& c : claims) {
        const int claim_id = c.value("claim_id", 0);
        if (claim_id <= 0) continue;

        nlohmann::json claim_one{{"steam_id", sid}, {"claim_ids", nlohmann::json::array({claim_id})}};
        HttpClient::PostJson("/api/market/claims/claim", claim_one.dump());
        claimed_ids.push_back(claim_id);

        const std::string hex = c.value("item_blob_hex", std::string());
        if (hex.empty()) {
            ReleaseClaims(sid, {claim_id});
            claimed_ids.clear();
            SendMsg(player, FColorList::Red, "Blob invalido - resgate cancelado.");
            return;
        }

        TArray<unsigned char> arr = HexDecode(hex);
        UPrimalItem* item = UPrimalItem::CreateFromBytes(&arr);
        if (!item || !inv->AddItemObject(item)) {
            ReleaseClaims(sid, claimed_ids);
            SendMsg(player, FColorList::Red,
                    "Inventario cheio - libere espaco e tente /resgatarmercado.");
            return;
        }

        nlohmann::json done{{"steam_id", sid}, {"claim_id", claim_id}};
        HttpClient::PostJson("/api/market/claims/delivered", done.dump());
        ++delivered;
    }

    SendMsg(player, FColorList::Green,
            std::to_string(delivered) + " cryopod(s) entregue(s) do Comercio.");
}

} // namespace CustomShop
