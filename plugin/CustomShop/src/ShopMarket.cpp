#include "pch.h"
#include "ShopMarket.h"
#include "ShopBridge.h"
#include "ShopCloudInventory.h"
#include "ShopCryoReader.h"
#include "ShopConfig.h"
#include "ShopEngrams.h"
#include "ShopNotes.h"
#include "ShopPoints.h"
#include "ShopPerms.h"
#include "HttpClient.h"

#include <chrono>
#include <cmath>
#include <mutex>
#include <random>
#include <sstream>
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
                "Como calculamos â€” sugerido: " + FormatAmbar(total) + " Ambar");
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

/** Chat in-game nao suporta UTF-8 â€” mensagens da web precisam ir em ASCII. */

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

bool TryGiveBonusSoulTrap(AShooterPlayerController* player, const std::string& blueprint) {
    if (!player || blueprint.empty()) return false;
    UPrimalInventoryComponent* inv = player->GetPlayerInventoryComponent();
    if (!inv) return false;

    FString fblueprint(blueprint.c_str());
    UClass* item_class = UVictoryCore::BPLoadClass(&fblueprint);
    if (!item_class) return false;

    UPrimalItem* created = UPrimalItem::AddNewItem(
        TSubclassOf<UPrimalItem>(item_class),
        inv,
        false,
        false,
        0.f,
        true,
        1,
        false,
        0.f,
        false,
        TSubclassOf<UPrimalItem>(),
        0.f,
        false,
        false);
    return created != nullptr;
}

std::vector<std::string> SplitChatArgs(FString* cmd_str) {
    std::vector<std::string> parts;
    if (!cmd_str) return parts;
    std::string line = cmd_str->ToString();
    std::istringstream iss(line);
    std::string token;
    while (iss >> token)
        parts.push_back(token);
    return parts;
}

bool IsMarketModerator(AShooterPlayerController* player, const std::string& sid) {
    if (!player) return false;
    if (player->bIsAdmin()()) return true;
    uint64_t steam_id = 0;
    try {
        steam_id = std::stoull(sid);
    } catch (...) {
        return false;
    }
    static const char* kGroups[] = {"Moderacao", "Mod", "MOD", "STAFF"};
    for (const char* grp : kGroups) {
        if (CustomShop::Perms::IsInGroup(steam_id, grp)) return true;
    }
    return false;
}

constexpr const char* kDinoLabBlockMsg =
    "este dino ou sua linhagem pertence ao Dino Lab e nao pode ser vendido.";

nlohmann::json BuildDinoIdentityPairsBody(const CustomShop::DinoIdentity& identity) {
    nlohmann::json pairs = nlohmann::json::array();
    pairs.push_back(nlohmann::json::array({identity.dino_id1, identity.dino_id2}));
    for (const auto& pair : identity.ancestor_pairs)
        pairs.push_back(nlohmann::json::array({pair.first, pair.second}));
    return nlohmann::json{{"dino_id_pairs", pairs}};
}

std::string FormatDinoIdHex(uint32_t id) {
    char buf[16];
    snprintf(buf, sizeof(buf), "%08X", id);
    return buf;
}

struct DinoLabBlockCheckResult {
    bool blocked = false;
    bool check_failed = false;
    std::string order_id;
    std::string canonical_id;
    uint32_t matched_id1 = 0;
    uint32_t matched_id2 = 0;
};

DinoLabBlockCheckResult CheckDinoLabBlockedHttp(const CustomShop::DinoIdentity& identity) {
    DinoLabBlockCheckResult result;
    if (identity.dino_id1 == 0 && identity.dino_id2 == 0) {
        result.check_failed = true;
        return result;
    }
    const std::string resp = CustomShop::HttpClient::PostJson(
        "/api/market/plugin/check-dino-blocked",
        BuildDinoIdentityPairsBody(identity).dump());
    if (resp.empty()) {
        result.check_failed = true;
        return result;
    }
    try {
        const nlohmann::json json = nlohmann::json::parse(resp);
        if (!json.value("ok", true) && !json.contains("blocked")) {
            result.check_failed = true;
            return result;
        }
        result.blocked = json.value("blocked", false);
        if (!result.blocked)
            return result;
        result.order_id = json.value("order_id", "");
        result.canonical_id = json.value("canonical_id", "");
        const auto& mp = json.value("matched_pair", nlohmann::json::array());
        if (mp.is_array() && mp.size() >= 2) {
            result.matched_id1 = mp[0].get<uint32_t>();
            result.matched_id2 = mp[1].get<uint32_t>();
        }
    } catch (...) {
        result.check_failed = true;
        return result;
    }
    return result;
}

void LogDinoLabBlockHit(const char* stage,
                        const std::string& steam_id,
                        const CustomShop::DinoIdentity& identity,
                        const DinoLabBlockCheckResult& check) {
    Log::GetLog()->warn(
        "[DinoLabBlock] {} steam={} self={}:{} ancestors={} matched={}:{} order={} canon={}",
        stage,
        steam_id,
        FormatDinoIdHex(identity.dino_id1),
        FormatDinoIdHex(identity.dino_id2),
        identity.ancestor_pairs.size(),
        FormatDinoIdHex(check.matched_id1),
        FormatDinoIdHex(check.matched_id2),
        check.order_id,
        check.canonical_id);
}

bool NotifyIfDinoLabBlocked(AShooterPlayerController* player,
                            UPrimalItem* cryo,
                            const char* stage) {
    const std::string sid = CustomShop::Bridge::GetSteamId(player);
    CustomShop::DinoIdentity identity;
    if (!CustomShop::ExtractDinoIdentityFromCryopod(cryo, player, identity)) {
        Log::GetLog()->warn(
            "[DinoLabBlock] {} steam={} identity extract failed — blocking",
            stage, sid);
        SendMsg(player, FColorList::Red,
                "Nao foi possivel validar a identidade do dino para o Comercio. "
                "Tente novamente.");
        return true;
    }
    const DinoLabBlockCheckResult check = CheckDinoLabBlockedHttp(identity);
    if (check.check_failed) {
        Log::GetLog()->warn(
            "[DinoLabBlock] {} steam={} self={}:{} HTTP check failed — blocking",
            stage, sid,
            FormatDinoIdHex(identity.dino_id1),
            FormatDinoIdHex(identity.dino_id2));
        SendMsg(player, FColorList::Red,
                "Falha ao validar bloqueio Dino Lab. Tente novamente.");
        return true;
    }
    if (!check.blocked)
        return false;
    LogDinoLabBlockHit(stage, sid, identity, check);
    SendMsg(player, FColorList::Red, kDinoLabBlockMsg);
    return true;
}

void CmdRastrearDebugImpl(AShooterPlayerController* player) {
    if (!player) return;
    const std::string sid = CustomShop::Bridge::GetSteamId(player);

    UPrimalItem* cryo = CustomShop::FindCryopodInInventory(player, -1);
    if (!cryo) {
        SendMsg(player, FColorList::Red,
                "Nenhuma cryopod valida no inventario.");
        return;
    }

    CustomShop::DinoIdentity identity;
    if (!CustomShop::ExtractDinoIdentityFromCryopod(cryo, player, identity)) {
        SendMsg(player, FColorList::Red,
                "Nao foi possivel ler a identidade desta cryopod.");
        Log::GetLog()->warn("[DinoLabBlock] rastreardebug steam={} identity extract failed", sid);
        return;
    }

    SendMsg(player, FColorList::Yellow,
            "ID self " + FormatDinoIdHex(identity.dino_id1) + "-"
            + FormatDinoIdHex(identity.dino_id2)
            + " anc=" + std::to_string(identity.ancestor_pairs.size()));

    const DinoLabBlockCheckResult check = CheckDinoLabBlockedHttp(identity);
    if (check.blocked) {
        SendMsg(player, FColorList::Red,
                "BLOQUEADO order=" + check.order_id
                + " match=" + FormatDinoIdHex(check.matched_id1) + "-"
                + FormatDinoIdHex(check.matched_id2));
        LogDinoLabBlockHit("rastreardebug", sid, identity, check);
        return;
    }

    SendMsg(player, FColorList::Green, "Sem bloqueio Dino Lab (HTTP ok).");
    Log::GetLog()->info(
        "[DinoLabBlock] rastreardebug steam={} self={}:{} ancestors={} blocked=0",
        sid,
        FormatDinoIdHex(identity.dino_id1),
        FormatDinoIdHex(identity.dino_id2),
        identity.ancestor_pairs.size());
}

void AttachDinoIdentityToMetadata(nlohmann::json& metadata,
                                  UPrimalItem* cryo,
                                  AShooterPlayerController* player) {
    CustomShop::DinoIdentity identity;
    if (CustomShop::ExtractDinoIdentityFromCryopod(cryo, player, identity))
        metadata["dino_identity"] = CustomShop::DinoIdentityToJson(identity);
}

} // anonymous namespace

namespace CustomShop {

void ShopMarket::RegisterCommands() {
    ArkApi::GetCommands().AddChatCommand("/enviar", &ShopMarket::CmdEnviar);
    ArkApi::GetCommands().AddChatCommand("/enviardebug", &ShopMarket::CmdEnviarDebug);
    ArkApi::GetCommands().AddChatCommand("/confirmar", &ShopMarket::CmdConfirmar);
    ArkApi::GetCommands().AddChatCommand("/rastrear", &ShopMarket::CmdRastrear);
    ArkApi::GetCommands().AddChatCommand("/rastreardebug", &ShopMarket::CmdRastrearDebug);
    ArkApi::GetCommands().AddChatCommand("/mercado", &ShopMarket::CmdResgatarMercado);
    ArkApi::GetCommands().AddChatCommand("/mercado_admin", &ShopMarket::CmdMercadoAdmin);
}

void ShopMarket::UnregisterCommands() {
    ArkApi::GetCommands().RemoveChatCommand("/enviar");
    ArkApi::GetCommands().RemoveChatCommand("/enviardebug");
    ArkApi::GetCommands().RemoveChatCommand("/confirmar");
    ArkApi::GetCommands().RemoveChatCommand("/rastrear");
    ArkApi::GetCommands().RemoveChatCommand("/rastreardebug");
    ArkApi::GetCommands().RemoveChatCommand("/mercado");
    ArkApi::GetCommands().RemoveChatCommand("/mercado_admin");
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

    if (NotifyIfDinoLabBlocked(player, cryo, "enviar"))
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
    AttachDinoIdentityToMetadata(preview_body["metadata"], cryo, player);
    const std::string preview_resp = HttpClient::PostJson("/api/market/plugin/preview", preview_body.dump());
    nlohmann::json preview_json;
    try {
        preview_json = nlohmann::json::parse(preview_resp);
    } catch (...) {
        preview_json = nlohmann::json::object();
    }
    if (preview_json.value("blocked", false)) {
        {
            std::lock_guard<std::mutex> lock(g_pending_mutex);
            g_pending.erase(sid);
        }
        const std::string block_msg = preview_json.value(
            "message", std::string(kDinoLabBlockMsg));
        SendMsg(player, FColorList::Red, block_msg);
        return;
    }
    if (preview_json.value("ok", false)) {
        const int suggested = preview_json.value("computed_base_value", 0);
        if (suggested > 0) {
            SendEconomyBreakdown(player, preview_json);
            const int ceiling = preview_json.value("price_ceiling", 0);
            if (ceiling > 0) {
                SendMsg(player, FColorList::Yellow,
                        "Teto maximo de preco no Comercio: " + FormatAmbar(ceiling) + " Ambar");
            }
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

void ShopMarket::CmdRastrear(AShooterPlayerController* player, FString*, EChatSendMode::Type) {
    if (!player) return;

    UPrimalItem* cryo = FindCryopodInInventory(player, -1);
    if (!cryo) {
        SendMsg(player, FColorList::Red,
                "Nenhuma cryopod valida no inventario. Equipe uma cryo preenchida "
                "legivel (cryos vazias ou corrompidas sao ignoradas).");
        return;
    }

    DinoIdentity identity;
    if (!ExtractDinoIdentityFromCryopod(cryo, player, identity)) {
        SendMsg(player, FColorList::Red,
                "Nao foi possivel ler a identidade desta cryopod.");
        return;
    }

    if (CheckDinoLabBlockedHttp(identity).blocked) {
        SendMsg(player, FColorList::Red, kDinoLabBlockMsg);
        return;
    }

    SendMsg(player, FColorList::Green,
            "Este dino pode ser vendido no Comercio (sem bloqueio Dino Lab detectado).");
}

void ShopMarket::CmdRastrearDebug(AShooterPlayerController* player, FString*, EChatSendMode::Type) {
    CmdRastrearDebugImpl(player);
}

void ShopMarket::CmdConfirmar(AShooterPlayerController* player, FString*, EChatSendMode::Type) {
    if (!player) return;
    const std::string sid = Bridge::GetSteamId(player);

    if (Engrams::HasPendingUnlock(sid)) {
        int unlocked = 0;
        int price = 0;
        int balance = 0;
        const auto result = Engrams::ConfirmUnlockAll(
            sid, player, &unlocked, &price, &balance);

        if (result == Engrams::EngramConfirmResult::Expired) {
            SendMsg(player, FColorList::Red,
                    "Confirmacao de engramas expirada. Use /engramas novamente.");
            return;
        }
        if (result == Engrams::EngramConfirmResult::PaymentFailed) {
            SendMsg(player, FColorList::Red,
                    "Saldo insuficiente. Voce tem " + std::to_string(balance)
                    + " ambares, mas sao necessarios " + std::to_string(price)
                    + " para /engramas.");
            return;
        }
        if (result == Engrams::EngramConfirmResult::UnlockFailed) {
            SendMsg(player, FColorList::Red,
                    "Nao foi possivel desbloquear os engramas. Voce precisa estar vivo.");
            return;
        }
        if (result != Engrams::EngramConfirmResult::Ok) {
            SendMsg(player, FColorList::Red,
                    "Nenhuma confirmacao de engramas pendente. Use /engramas primeiro.");
            return;
        }

        std::string msg = "Todos os engramas foram desbloqueados com sucesso!";
        if (unlocked > 0)
            msg += " (" + std::to_string(unlocked) + " novos)";
        if (price > 0)
            msg += " â€” " + std::to_string(price) + " ambares debitados.";
        SendMsg(player, FColorList::Green, msg);
        return;
    }

    // Ordem de despacho /confirmar (pending por steam_id):
    //   1 engramas → 2 notas → 3 marco (Teams::HasPendingDeposit) → 4 mercado
    // Spec Modo Equipe §5.5.4 — nao misturar kinds; mensagens especificas por ramo.
    // TODO: if (Teams::HasPendingDeposit(sid)) { ConfirmDeposit(...); return; }

    if (Notes::HasPendingUnlock(sid)) {
        int price = 0;
        int balance = 0;
        const auto result = Notes::ConfirmUnlockAll(sid, player, &price, &balance);

        if (result == Notes::NotesConfirmResult::Expired) {
            SendMsg(player, FColorList::Red,
                    "Confirmacao de notas expirada. Use /notas novamente.");
            return;
        }
        if (result == Notes::NotesConfirmResult::PaymentFailed) {
            SendMsg(player, FColorList::Red,
                    "Saldo insuficiente. Voce tem " + std::to_string(balance)
                    + " ambares, mas sao necessarios " + std::to_string(price)
                    + " para /notas.");
            return;
        }
        if (result == Notes::NotesConfirmResult::UnlockFailed) {
            SendMsg(player, FColorList::Red,
                    "Nao foi possivel desbloquear as notas. Voce precisa estar vivo.");
            return;
        }
        if (result == Notes::NotesConfirmResult::Disabled) {
            SendMsg(player, FColorList::Red,
                    "O comando /notas esta desativado no momento.");
            return;
        }
        if (result != Notes::NotesConfirmResult::Ok) {
            SendMsg(player, FColorList::Red,
                    "Nenhuma confirmacao de notas pendente. Use /notas primeiro.");
            return;
        }

        std::string msg =
            "Todas as notas de explorador (+10 niveis) e as 200 runas de Fjordur (+10 niveis) foram desbloqueadas!";
        if (price > 0)
            msg += " — " + std::to_string(price) + " ambares debitados.";
        SendMsg(player, FColorList::Green, msg);
        return;
    }

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

    if (NotifyIfDinoLabBlocked(player, cryo, "confirmar"))
        return;

    const float min_days = ShopConfig::Get().MarketCryoMinDaysRemaining();
    if (!ValidateMarketCryoTimer(player, cryo, sid, "confirmar_timer", min_days)) {
        std::lock_guard<std::mutex> lock(g_pending_mutex);
        g_pending[sid] = pending;
        return;
    }

    ApplyCryoTimerFieldsToMetadata(cryo, pending.meta);

    const bool stripped = StripCryopodTimer(cryo);
    RefreshCryopodEncapsulationWorldTime(cryo);
    if (stripped) {
        pending.meta.had_timer = true;
        pending.meta.timer_remaining_days = -1.f;
    }

    FCustomItemByteArray bytes;
    cryo->GetItemBytes(&bytes.Bytes);
    if (bytes.Bytes.Num() <= 0) {
        SendMsg(player, FColorList::Red, "Falha ao serializar cryopod.");
        {
            std::lock_guard<std::mutex> lock(g_pending_mutex);
            g_pending[sid] = pending;
        }
        return;
    }

    UPrimalItem* probe = UPrimalItem::CreateFromBytes(&bytes.Bytes);
    std::string probe_err;
    if (!probe || !PrepareMarketCryopodForDelivery(probe, player, &probe_err)) {
        Log::GetLog()->warn(
            "ShopMarket: confirmar probe falhou steam={} err={}", sid, probe_err);
        SendMsg(player, FColorList::Red,
                "Cryopod invalida apos normalizacao: "
                + SanitizeForGameChat(probe_err.empty() ? std::string("dados ilegiveis")
                                                        : probe_err));
        SendCryoDebugReport(player, sid, "confirmar_probe_fail", true);
        ReleaseTransientCryopod(probe);
        {
            std::lock_guard<std::mutex> lock(g_pending_mutex);
            g_pending[sid] = pending;
        }
        return;
    }
    ReleaseTransientCryopod(probe);

    UPrimalInventoryComponent* inv = player->GetPlayerInventoryComponent();
    const std::string hex = HexEncode(bytes.Bytes);
    const std::string upload_id = NewUploadId();

    if (!inv || !ShopCloudInventory::Get().RemovePlayerItem(cryo, inv, player)) {
        SendMsg(player, FColorList::Red, "Falha ao remover cryopod do inventario.");
        {
            std::lock_guard<std::mutex> lock(g_pending_mutex);
            g_pending[sid] = pending;
        }
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
    AttachDinoIdentityToMetadata(body["metadata"], cryo, player);
    if (stripped)
        body["metadata"]["timer_stripped_on_upload"] = true;

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
    const int ceiling = json.value("price_ceiling", 0);
    if (ceiling > 0) {
        SendMsg(player, FColorList::Yellow,
                "Teto maximo de preco: " + FormatAmbar(ceiling) + " Ambar (defina na web).");
    }
}

void ShopMarket::CmdMercadoAdmin(AShooterPlayerController* player, FString* cmd_str,
                                 EChatSendMode::Type) {
    if (!player) return;
    const std::string sid = Bridge::GetSteamId(player);
    if (!IsMarketModerator(player, sid)) {
        SendMsg(player, FColorList::Red,
                "Sem permissao. Apenas admin/moderacao ou SteamID na lista de admins da web.");
        return;
    }

    const auto parts = SplitChatArgs(cmd_str);
    if (parts.size() < 2) {
        SendMsg(player, FColorList::Yellow,
                "Uso: /mercado_admin remover <id> | preco <id> <valor> | flag <id> [motivo]");
        return;
    }

    const std::string action = parts[0];
    int listing_id = 0;
    try {
        listing_id = std::stoi(parts[1]);
    } catch (...) {
        SendMsg(player, FColorList::Red, "ID de anuncio invalido.");
        return;
    }

    nlohmann::json body;
    body["admin_steam_id"] = sid;
    body["listing_id"] = listing_id;

    if (action == "remover" || action == "remove") {
        body["action"] = "remover";
        if (parts.size() > 2)
            body["reason"] = parts[2];
    } else if (action == "preco" || action == "price") {
        if (parts.size() < 3) {
            SendMsg(player, FColorList::Red, "Uso: /mercado_admin preco <id> <valor>");
            return;
        }
        body["action"] = "preco";
        try {
            body["price_absolute"] = std::stoi(parts[2]);
        } catch (...) {
            SendMsg(player, FColorList::Red, "Valor de preco invalido.");
            return;
        }
    } else if (action == "flag" || action == "flaggar") {
        body["action"] = "flag";
        if (parts.size() > 2) {
            std::string reason;
            for (size_t i = 2; i < parts.size(); ++i) {
                if (!reason.empty()) reason += ' ';
                reason += parts[i];
            }
            body["reason"] = reason;
        }
    } else {
        SendMsg(player, FColorList::Red,
                "Acao invalida. Use remover, preco ou flag.");
        return;
    }

    const std::string resp = HttpClient::PostJson("/api/market/plugin/admin", body.dump());
    nlohmann::json json;
    try {
        json = nlohmann::json::parse(resp);
    } catch (...) {
        json = nlohmann::json{{"ok", false}, {"error", "resposta invalida"}};
    }

    if (!json.value("ok", false)) {
        SendMsg(player, FColorList::Red,
                SanitizeForGameChat(json.value("error", std::string("falha"))));
        return;
    }

    std::string msg = "OK listing #" + std::to_string(listing_id);
    if (json.contains("message"))
        msg = SanitizeForGameChat(json.value("message", msg));
    SendMsg(player, FColorList::Green, msg);
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
        SendMsg(player, FColorList::Yellow,
                "Nenhum dino pendente no Comercio (ou resgate expirado â€” reembolso automatico).");
        return;
    }

    double min_hours = 9999.0;
    for (const auto& c : claims) {
        const double hrs = c.value("hours_remaining", 24.0);
        if (hrs < min_hours) min_hours = hrs;
    }
    if (min_hours < 9999.0) {
        const int shown = static_cast<int>(std::ceil(min_hours));
        SendMsg(player, FColorList::Yellow,
                "Voce tem " + std::to_string(shown > 0 ? shown : 1)
                + " hora(s) para resgatar com /mercado.");
    }

    UPrimalInventoryComponent* inv = player->GetPlayerInventoryComponent();
    if (!inv) {
        SendMsg(player, FColorList::Red, "Inventario indisponivel.");
        return;
    }

    int delivered = 0;
    int spawned = 0;
    std::vector<int> claimed_ids;
    const bool deliver_as_spawn = ShopConfig::Get().MarketDeliverAsSpawn();
    const std::string soul_trap_bp = ShopConfig::Get().MarketSpawnBonusSoulTrapBlueprint();

    for (const auto& c : claims) {
        const int claim_id = c.value("claim_id", 0);
        if (claim_id <= 0) continue;

        nlohmann::json claim_one{{"steam_id", sid}, {"claim_ids", nlohmann::json::array({claim_id})}};
        const std::string claim_resp =
            HttpClient::PostJson("/api/market/claims/claim", claim_one.dump());
        nlohmann::json claim_json;
        try {
            claim_json = nlohmann::json::parse(claim_resp);
        } catch (...) {
            claim_json = nlohmann::json::object();
        }
        if (!claim_json.value("ok", true)) {
            ReleaseClaims(sid, {});
            SendMsg(player, FColorList::Red,
                    SanitizeForGameChat(claim_json.value(
                        "error",
                        std::string("Resgate expirado ou indisponivel â€” reembolso automatico."))));
            return;
        }
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
        if (!item) {
            ReleaseClaims(sid, claimed_ids);
            claimed_ids.clear();
            Log::GetLog()->error(
                "ShopMarket: mercado CreateFromBytes falhou steam={} claim_id={}",
                sid, claim_id);
            SendMsg(player, FColorList::Red,
                    "Cryopod corrompida no vault - resgate cancelado. Contate admin.");
            return;
        }

        std::string prep_err;
        if (!PrepareMarketCryopodForDelivery(item, player, &prep_err)) {
            ReleaseClaims(sid, claimed_ids);
            claimed_ids.clear();
            Log::GetLog()->error(
                "ShopMarket: mercado delivery invalido steam={} claim_id={} err={} max={:.0f} saved={:.0f}",
                sid,
                claim_id,
                prep_err,
                item->ItemDurabilityField(),
                item->SavedDurabilityField());
            SendCryoDebugReport(player, sid, "mercado_delivery_fail",
                                ShopConfig::Get().MarketCryoDebug());
            SendMsg(player, FColorList::Red,
                    "Cryopod invalida no Comercio (vazia ou sem carga). "
                    "Resgate liberado - contate admin se persistir.");
            return;
        }

        if (deliver_as_spawn) {
            std::string spawn_err;
            if (!SpawnMarketDinoFromCryopod(item, player, nullptr, &spawn_err)) {
                ReleaseClaims(sid, claimed_ids);
                claimed_ids.clear();
                Log::GetLog()->error(
                    "ShopMarket: mercado spawn falhou steam={} claim_id={} err={}",
                    sid, claim_id, spawn_err);
                SendCryoDebugReport(player, sid, "mercado_spawn_fail",
                                    ShopConfig::Get().MarketCryoDebug());
                if (spawn_err.find("duplicado") != std::string::npos
                    || spawn_err.find("retries") != std::string::npos) {
                    SendMsg(player, FColorList::Red,
                            "Falha ao spawnar dino (ID duplicado). "
                            "Resgate liberado â€” tente novamente ou contate admin.");
                } else {
                    SendMsg(player, FColorList::Red,
                            "Falha ao spawnar dino do Comercio. "
                            "Resgate liberado - tente novamente ou contate admin.");
                }
                ReleaseTransientCryopod(item);
                return;
            }

            // Spawn consumiu/invalidou a cryopod transiente â€” nao destruir de novo.
            item = nullptr;

            bool soul_trap_ok = false;
            if (!soul_trap_bp.empty()) {
                soul_trap_ok = TryGiveBonusSoulTrap(player, soul_trap_bp);
                if (!soul_trap_ok) {
                    Log::GetLog()->warn(
                        "ShopMarket: Soul Trap bonus falhou steam={} bp={}",
                        sid, soul_trap_bp);
                }
            }

            nlohmann::json done{{"steam_id", sid}, {"claim_id", claim_id}};
            HttpClient::PostJson("/api/market/claims/delivered", done.dump());
            ++delivered;
            ++spawned;
            if (soul_trap_ok) {
                SendMsg(player, FColorList::Green,
                        "Dino spawnado ao seu lado + 1 Soul Trap vazia no inventario.");
            } else if (!soul_trap_bp.empty()) {
                SendMsg(player, FColorList::Yellow,
                        "Dino spawnado ao seu lado (Soul Trap bonus indisponivel â€” libere espaco?).");
            } else {
                SendMsg(player, FColorList::Green, "Dino spawnado ao seu lado.");
            }
            continue;
        }

        if (!inv->AddItemObject(item)) {
            ReleaseClaims(sid, claimed_ids);
            SendMsg(player, FColorList::Red,
                    "Inventario cheio - libere espaco e tente /mercado.");
            return;
        }

        nlohmann::json done{{"steam_id", sid}, {"claim_id", claim_id}};
        HttpClient::PostJson("/api/market/claims/delivered", done.dump());
        ++delivered;
    }

    if (delivered <= 0) return;

    if (spawned > 0 && spawned == delivered) {
        if (delivered == 1) return;
        SendMsg(player, FColorList::Green,
                std::to_string(delivered) + " dino(s) spawnado(s) do Comercio.");
        return;
    }

    SendMsg(player, FColorList::Green,
            std::to_string(delivered) + " cryopod(s) entregue(s) do Comercio.");
}

} // namespace CustomShop
