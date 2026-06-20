#include "pch.h"
#include "ShopMarket.h"
#include "ShopBridge.h"
#include "ShopCloudInventory.h"
#include "ShopCryoReader.h"
#include "HttpClient.h"

#include <chrono>
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

void SendMsg(AShooterPlayerController* c, const FLinearColor& color, const std::string& msg) {
    if (c && !msg.empty())
        ArkApi::GetApiUtils().SendServerMessage(c, color, msg.c_str());
}

bool ProfileCommerceReady(const std::string& steam_id, std::string* error_out) {
    const std::string resp = HttpClient::Get("/api/market/plugin/profile/" + steam_id);
    nlohmann::json json;
    try {
        json = nlohmann::json::parse(resp);
    } catch (...) {
        if (error_out) *error_out = "Comercio indisponivel (web)";
        return false;
    }
    if (!json.value("ok", false) || !json.value("commerce_ready", false)) {
        if (error_out)
            *error_out = json.value("error", std::string("Defina nome de exibicao em Minha Area (web)."));
        return false;
    }
    return true;
}

void ReleaseClaims(const std::string& steam_id, const std::vector<int>& claim_ids) {
    if (claim_ids.empty()) return;
    nlohmann::json body{{"steam_id", steam_id}, {"claim_ids", nlohmann::json::array()}};
    for (int id : claim_ids)
        body["claim_ids"].push_back(id);
    HttpClient::PostJson("/api/market/claims/release", body.dump());
}

} // anonymous namespace

namespace CustomShop {

void ShopMarket::RegisterCommands() {
    ArkApi::GetCommands().AddChatCommand("/enviar", &ShopMarket::CmdEnviar);
    ArkApi::GetCommands().AddChatCommand("/confirmar", &ShopMarket::CmdConfirmar);
    ArkApi::GetCommands().AddChatCommand("/resgatarmercado", &ShopMarket::CmdResgatarMercado);
}

void ShopMarket::UnregisterCommands() {
    ArkApi::GetCommands().RemoveChatCommand("/enviar");
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
        SendMsg(player, FColorList::Red, "Nenhuma cryopod com dino encontrada no inventario.");
        return;
    }

    CryoParsedMetadata meta;
    std::string err;
    if (!ParseCryopodItem(cryo, meta, &err)) {
        SendMsg(player, FColorList::Red, "Cryopod invalida: " + err);
        return;
    }
    if (meta.imprint_pct < 0.999f) {
        SendMsg(player, FColorList::Red, "Imprint 100% obrigatorio para o Comercio.");
        return;
    }

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
    if (meta.had_timer) {
        SendMsg(player, FColorList::Yellow,
                "Cryopod com timer detectada — ao /confirmar o timer sera removido permanentemente.");
    }
    SendMsg(player, FColorList::Yellow,
            "Digite /confirmar em ate 2 minutos para enviar ao Comercio (cryopod sera removida).");
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

    const bool had_timer = CryopodHasTimer(cryo);
    if (had_timer) {
        if (!StripCryopodTimer(cryo)) {
            SendMsg(player, FColorList::Red,
                    "Falha ao remover timer da cryopod. Tente outra cryopod ou contate admin.");
            return;
        }
        pending.meta.had_timer = true;
        SendMsg(player, FColorList::Yellow, "Timer removido — cryopod padrao (sem limite) pronta para envio.");
    }

    FCustomItemByteArray bytes;
    cryo->GetItemBytes(&bytes.Bytes);
    if (bytes.Bytes.Num() <= 0) {
        SendMsg(player, FColorList::Red, "Falha ao serializar cryopod.");
        return;
    }

    UPrimalItem* probe = UPrimalItem::CreateFromBytes(&bytes.Bytes);
    if (!probe) {
        SendMsg(player, FColorList::Red, "Cryopod corrompida — envio cancelado.");
        return;
    }

    const std::string hex = HexEncode(bytes.Bytes);
    const std::string upload_id = NewUploadId();

    UPrimalInventoryComponent* inv = player->GetPlayerInventoryComponent();
    if (!inv || !inv->RemoveItemFromInventory(cryo, false, false, false)) {
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
        UPrimalItem* restored = UPrimalItem::CreateFromBytes(bytes.Bytes);
        if (restored && inv) {
            inv->AddItemObject(restored);
            SendMsg(player, FColorList::Yellow,
                    "Falha no servidor — cryopod devolvida. Motivo: "
                    + json.value("error", std::string("erro desconhecido")));
        } else {
            SendMsg(player, FColorList::Red,
                    "FALHA CRITICA: cryopod removida mas upload falhou. Contate admin.");
        }
        return;
    }

    SendMsg(player, FColorList::Green,
            "Dino enviado ao Comercio! Listing #" + std::to_string(json.value("listing_id", 0))
            + " — defina preco na web.");
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
            SendMsg(player, FColorList::Red, "Blob invalido — resgate cancelado.");
            return;
        }

        TArray<unsigned char> arr = HexDecode(hex);
        UPrimalItem* item = UPrimalItem::CreateFromBytes(&arr);
        if (!item || !inv->AddItemObject(item)) {
            ReleaseClaims(sid, claimed_ids);
            SendMsg(player, FColorList::Red,
                    "Inventario cheio — libere espaco e tente /resgatarmercado.");
            return;
        }
        if (CryopodHasTimer(item))
            StripCryopodTimer(item);

        nlohmann::json done{{"steam_id", sid}, {"claim_id", claim_id}};
        HttpClient::PostJson("/api/market/claims/delivered", done.dump());
        ++delivered;
    }

    SendMsg(player, FColorList::Green,
            std::to_string(delivered) + " cryopod(s) entregue(s) do Comercio.");
}

} // namespace CustomShop
