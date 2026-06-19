#include "pch.h"
#include "Commands.h"
#include "ShopBridge.h"
#include "ShopConfig.h"
#include "ShopData.h"
#include "ShopPoints.h"
#include "ShopStore.h"
#include "ShopVip.h"
#include "ShopCloudInventory.h"
#include "HttpClient.h"

// Prevent Windows min/max macros from conflicting with std::max
#ifdef max
#undef max
#endif
#ifdef min
#undef min
#endif

namespace {

// Split FString by space using std::string (avoids TCHAR type issues)
std::vector<std::string> SplitCmd(FString* cmd_str) {
    std::vector<std::string> parts;
    if (!cmd_str) return parts;
    const std::string s = cmd_str->ToString();
    std::istringstream ss(s);
    std::string token;
    while (ss >> token)
        parts.push_back(token);
    return parts;
}

void SendMsg(AShooterPlayerController* c, const FLinearColor& color,
             const std::string& msg) {
    ArkApi::GetApiUtils().SendServerMessage(c, color, msg.c_str());
}

std::string FormatCloudMessage(CustomShop::CloudResult result, int count) {
    using CustomShop::CloudResult;
    const auto& cfg = CustomShop::ShopConfig::Get();
    switch (result) {
    case CloudResult::Ok:
        if (count > 0)
            return "Nuvem: operacao concluida com " + std::to_string(count) + " item(ns).";
        return "Nuvem: operacao concluida.";
    case CloudResult::Disabled:
        return "Inventario na nuvem desativado neste servidor.";
    case CloudResult::NoLicense: {
        std::string url = cfg.WebsiteUrl();
        if (url.empty()) url = cfg.WebApiUrl();
        return "Voce precisa de uma Licenca Nuvem ativa para enviar itens. Adquira na loja: " + url;
    }
    case CloudResult::AlreadyStored:
        return "Voce ja possui itens na nuvem. Use /download para recupera-los antes de um novo upload.";
    case CloudResult::EmptyInventory:
        return "Seu inventario esta vazio. Nada para enviar a nuvem.";
    case CloudResult::TooManyItems:
        return "Limite de " + std::to_string(cfg.CloudMaxItems())
             + " itens na nuvem. Reduza seu inventario e tente novamente.";
    case CloudResult::DbError:
        return "Erro ao acessar a nuvem. Tente novamente ou contate um admin.";
    case CloudResult::InventoryFull:
        return "Inventario sem espaco suficiente. Libere slots e use /download novamente.";
    case CloudResult::PartialRestore:
        return "Falha ao restaurar alguns itens. Seu cofre na nuvem foi mantido — tente de novo.";
    case CloudResult::NothingStored:
        return "Nuvem: voce nao possui itens armazenados.";
    case CloudResult::Cooldown:
        return "Aguarde " + std::to_string(cfg.CloudCooldownSeconds())
             + " segundos antes de usar a nuvem novamente.";
    case CloudResult::PlayerBusy:
        return "Voce precisa estar vivo para usar a nuvem.";
    default:
        return "Comando de nuvem indisponivel.";
    }
}

FLinearColor CloudResultColor(CustomShop::CloudResult result) {
    using CustomShop::CloudResult;
    switch (result) {
    case CloudResult::Ok:
        return FColorList::Green;
    case CloudResult::NothingStored:
        return FColorList::Yellow;
    default:
        return FColorList::Red;
    }
}

void CmdCloudUpload(AShooterPlayerController* controller, FString*, EChatSendMode::Type) {
    if (!controller) return;
    const auto result = CustomShop::ShopCloudInventory::Get().Upload(controller);
    const int count = CustomShop::ShopCloudInventory::Get().LastOperationCount();
    std::string msg = FormatCloudMessage(result, count);
    if (result == CustomShop::CloudResult::Ok)
        msg = "Nuvem: " + std::to_string(count)
            + " itens salvos. Seu inventario foi esvaziado.";
    SendMsg(controller, CloudResultColor(result), msg);
}

void CmdCloudDownload(AShooterPlayerController* controller, FString*, EChatSendMode::Type) {
    if (!controller) return;
    const auto result = CustomShop::ShopCloudInventory::Get().Download(controller);
    const int count = CustomShop::ShopCloudInventory::Get().LastOperationCount();
    std::string msg = FormatCloudMessage(result, count);
    if (result == CustomShop::CloudResult::Ok)
        msg = "Nuvem: " + std::to_string(count) + " itens devolvidos ao seu inventario.";
    SendMsg(controller, CloudResultColor(result), msg);
}

void CmdCloudStatus(AShooterPlayerController* controller, FString*, EChatSendMode::Type) {
    if (!controller) return;
    const std::string steam_id = CustomShop::Bridge::GetSteamId(controller);
    const int count = CustomShop::ShopCloudInventory::Get().GetStoredItemCount(steam_id);
    if (count <= 0) {
        SendMsg(controller, FColorList::Yellow,
                "Nuvem: voce nao possui itens armazenados.");
        return;
    }
    SendMsg(controller, FColorList::Green,
            "Nuvem: voce tem " + std::to_string(count) + " item(ns) armazenados.");
}

bool MatchCloudChat(const std::string& msg, const char* cmd) {
    if (msg == cmd) return true;
    const std::string prefix = std::string(cmd) + " ";
    return msg.size() > prefix.size() && msg.compare(0, prefix.size(), prefix) == 0;
}

bool OnCloudChatMessage(AShooterPlayerController* player, FString* message,
                        EChatSendMode::Type mode, bool /*spam_check*/, bool command_executed) {
    if (command_executed || !player || !message)
        return false;
    const std::string msg = message->ToString();
    if (MatchCloudChat(msg, "/upload")) {
        CmdCloudUpload(player, message, mode);
        return true;
    }
    if (MatchCloudChat(msg, "/download")) {
        CmdCloudDownload(player, message, mode);
        return true;
    }
    if (MatchCloudChat(msg, "/nuvem") || MatchCloudChat(msg, "/cloud")) {
        CmdCloudStatus(player, message, mode);
        return true;
    }
    return false;
}

void CmdConsoleCloudUpload(APlayerController* pc, FString*, bool) {
    auto* c = static_cast<AShooterPlayerController*>(pc);
    if (c) CmdCloudUpload(c, nullptr, EChatSendMode::GlobalChat);
}

void CmdConsoleCloudDownload(APlayerController* pc, FString*, bool) {
    auto* c = static_cast<AShooterPlayerController*>(pc);
    if (c) CmdCloudDownload(c, nullptr, EChatSendMode::GlobalChat);
}

void CmdConsoleCloudStatus(APlayerController* pc, FString*, bool) {
    auto* c = static_cast<AShooterPlayerController*>(pc);
    if (c) CmdCloudStatus(c, nullptr, EChatSendMode::GlobalChat);
}

void CmdBuyItem(APlayerController* pc, FString* cmd_str, bool) {
    auto* controller = static_cast<AShooterPlayerController*>(pc);
    if (!controller || !cmd_str) return;

    const auto parts = SplitCmd(cmd_str);
    if (parts.size() < 2) {
        SendMsg(controller, FColorList::Red, "Usage: BuyItem <id> [amount]");
        return;
    }

    const std::string id = parts[1];
    int amount = 1;
    if (parts.size() >= 3) {
        try { amount = std::max(1, std::stoi(parts[2])); }
        catch (...) { amount = 1; }
    }

    const std::string steam_id = CustomShop::Bridge::GetSteamId(controller);

    bool success = false;
    const bool is_kit = CustomShop::ShopConfig::Get().Kits().contains(id);
    if (is_kit)
        success = CustomShop::Store::BuyKit(controller, id);
    else
        success = CustomShop::Store::BuyItem(controller, id, amount);

    CustomShop::Data::SendBuyResult(controller, steam_id, id, amount, success);
    CustomShop::Data::SendPoints(controller);
    if (is_kit && success)
        CustomShop::Data::SendPlayerKits(controller, steam_id);
}

void CmdGetShopItems(APlayerController* pc, FString* cmd_str, bool) {
    auto* controller = static_cast<AShooterPlayerController*>(pc);
    if (!controller) return;

    std::string filter;
    if (cmd_str) {
        const auto parts = SplitCmd(cmd_str);
        if (parts.size() >= 2)
            filter = parts[1];
    }
    CustomShop::Data::SendShopItems(controller, filter);
}

void CmdGetConfig(APlayerController* pc, FString*, bool) {
    // GetConfig is sent by the mod when it initialises — apply buff lazily here
    // so the response can be delivered via ClientReceiveCallback.
    Log::GetLog()->info("ShopBridge: GetConfig command received");
    auto* c = static_cast<AShooterPlayerController*>(pc);
    if (c) CustomShop::Data::InitShop(c);
}

void CmdShop(AShooterPlayerController* controller, FString*, EChatSendMode::Type) {
    if (!controller) return;

    const auto& settings = CustomShop::ShopConfig::Get().Settings();
    std::string url = settings.value("WebsiteUrl", "");
    if (url.empty())
        url = CustomShop::ShopConfig::Get().WebApiUrl();

    if (url.empty()) {
        SendMsg(controller, FColorList::Yellow,
                "Loja web nao configurada. Contate um admin.");
        return;
    }

    SendMsg(controller, FColorList::Green,
            "Acesse a loja em: " + url);
    CustomShop::HttpClient::DeliverPending(controller);
}

void CmdShopDebugSelf(AShooterPlayerController* controller, FString*, EChatSendMode::Type) {
    // Player types /shop debug in chat — runs full diagnostic on themselves.
    // No steamid needed, output goes to their chat and the log file.
    if (!controller) return;
    CustomShop::Bridge::DiagnosePlayer(controller, controller);
}

void CmdGetPoints(APlayerController* pc, FString*, bool) {
    auto* c = static_cast<AShooterPlayerController*>(pc);
    if (c) CustomShop::Data::SendPoints(c);
}

void CmdSellItem(APlayerController* pc, FString*, bool) {
    // Sell is disabled by default (DisableSellButton=true in config).
    // This handler exists as a safety net in case the button is enabled
    // but no sell logic is implemented yet.
    auto* c = static_cast<AShooterPlayerController*>(pc);
    if (!c) return;
    const std::string id = CustomShop::Bridge::GetSteamId(c);
    nlohmann::json payload;
    payload["Command"]         = "SellItem";
    payload["Success"]         = false;
    payload["Result"]["SteamID"] = id;
    CustomShop::Bridge::SendPayload(c, payload);
}

void CmdGetKits(APlayerController* pc, FString*, bool) {
    auto* c = static_cast<AShooterPlayerController*>(pc);
    if (c) CustomShop::Data::SendKits(c);
}

void CmdPlayerKits(APlayerController* pc, FString*, bool) {
    auto* c = static_cast<AShooterPlayerController*>(pc);
    if (!c) return;
    CustomShop::Data::SendPlayerKits(c, CustomShop::Bridge::GetSteamId(c));
}

void CmdAdminAddPoints(APlayerController* pc, FString* cmd_str, bool) {
    auto* admin = static_cast<AShooterPlayerController*>(pc);
    if (!admin || !cmd_str) return;

    const auto parts = SplitCmd(cmd_str);
    if (parts.size() < 3) {
        SendMsg(admin, FColorList::Red, "Usage: Shop.AddPoints <steamid> <delta>");
        return;
    }

    const std::string target = parts[1];
    int delta = 0;
    try { delta = std::stoi(parts[2]); }
    catch (...) {
        SendMsg(admin, FColorList::Red, "Invalid delta value");
        return;
    }

    CustomShop::ShopPoints::Get().AddPoints(target, delta);
    SendMsg(admin, FColorList::Green,
            "Added " + std::to_string(delta) + " pts to " + target);

    if (auto* target_ctrl = CustomShop::Bridge::FindPlayer(target))
        CustomShop::Data::SendPoints(target_ctrl);
}

void CmdAdminSetPoints(APlayerController* pc, FString* cmd_str, bool) {
    auto* admin = static_cast<AShooterPlayerController*>(pc);
    if (!admin || !cmd_str) return;

    const auto parts = SplitCmd(cmd_str);
    if (parts.size() < 3) {
        SendMsg(admin, FColorList::Red, "Usage: Shop.SetPoints <steamid> <points>");
        return;
    }

    const std::string target = parts[1];
    int pts = 0;
    try { pts = std::max(0, std::stoi(parts[2])); }
    catch (...) {
        SendMsg(admin, FColorList::Red, "Invalid points value");
        return;
    }

    CustomShop::ShopPoints::Get().SetPoints(target, pts);
    SendMsg(admin, FColorList::Green,
            "Set " + std::to_string(pts) + " pts for " + target);

    if (auto* target_ctrl = CustomShop::Bridge::FindPlayer(target))
        CustomShop::Data::SendPoints(target_ctrl);
}

void CmdAdminGetPoints(APlayerController* pc, FString* cmd_str, bool) {
    auto* admin = static_cast<AShooterPlayerController*>(pc);
    if (!admin || !cmd_str) return;

    const auto parts = SplitCmd(cmd_str);
    if (parts.size() < 2) {
        SendMsg(admin, FColorList::Red, "Usage: Shop.GetPoints <steamid>");
        return;
    }

    const std::string target = parts[1];
    const int pts = CustomShop::ShopPoints::Get().GetPoints(target);
    SendMsg(admin, FColorList::White,
            target + " has " + std::to_string(pts) + " points");
}

void CmdAdminReload(APlayerController* pc, FString*, bool) {
    auto* admin = static_cast<AShooterPlayerController*>(pc);
    try {
        CustomShop::ShopConfig::Get().Load();

        if (admin)
            SendMsg(admin, FColorList::Green, "CustomShop reloaded");
        Log::GetLog()->info("CustomShop: config reloaded by admin command");
    }
    catch (const std::exception& e) {
        const std::string err = std::string("Reload failed: ") + e.what();
        Log::GetLog()->error("{}", err);
        if (admin) SendMsg(admin, FColorList::Red, err);
    }
}

// ─────────────────────────────────────────────────────────────────
//  Shop.Trade <target_steamid> <amount>
//  Player-to-player point transfer.
// ─────────────────────────────────────────────────────────────────
void CmdTrade(APlayerController* pc, FString* cmd_str, bool) {
    auto* controller = static_cast<AShooterPlayerController*>(pc);
    if (!controller || !cmd_str) return;

    if (CustomShop::ShopConfig::Get().DisableTrade()) {
        SendMsg(controller, FColorList::Red, "Trade is disabled on this server.");
        return;
    }

    const auto parts = SplitCmd(cmd_str);
    if (parts.size() < 3) {
        SendMsg(controller, FColorList::Red,
                "Usage: Shop.Trade <target_steamid> <amount>");
        return;
    }

    const std::string sender_id = CustomShop::Bridge::GetSteamId(controller);
    const std::string target_id = parts[1];
    int amount = 0;
    try { amount = std::max(1, std::stoi(parts[2])); }
    catch (...) {
        SendMsg(controller, FColorList::Red, "Invalid amount.");
        return;
    }

    if (sender_id == target_id) {
        SendMsg(controller, FColorList::Red, "Cannot trade with yourself.");
        return;
    }

    const int before = CustomShop::ShopPoints::Get().GetPoints(sender_id);
    if (before < amount) {
        SendMsg(controller, FColorList::Red,
                "Insufficient points (" + std::to_string(before) + ").");
        CustomShop::Data::SendTradeResult(controller, nullptr,
                                          sender_id, target_id, amount, false);
        return;
    }

    // Atomic transfer: deduct from sender, add to receiver.
    CustomShop::ShopPoints::Get().AddPoints(sender_id, -amount);
    CustomShop::ShopPoints::Get().AddPoints(target_id,  amount);

    const int after_sender   = CustomShop::ShopPoints::Get().GetPoints(sender_id);
    const int after_receiver = CustomShop::ShopPoints::Get().GetPoints(target_id);

    CustomShop::ShopPoints::Get().LogTransaction(
        "trade_send", sender_id, target_id, "", amount, before, after_sender);
    CustomShop::ShopPoints::Get().LogTransaction(
        "trade_recv", target_id, sender_id, "", amount,
        after_receiver - amount, after_receiver);

    auto* receiver = CustomShop::Bridge::FindPlayer(target_id);
    CustomShop::Data::SendTradeResult(controller, receiver,
                                       sender_id, target_id, amount, true);

    Log::GetLog()->info("Trade: {} → {} : {} pts", sender_id, target_id, amount);
}

// ─────────────────────────────────────────────────────────────────
//  Shop.Deliver <steamid> <item_or_kit_id> [amount]
//  Admin/Web: deliver an item or kit without charging points.
//  Intended for use by arkshop_web via RCON after it manages
//  its own order/payment flow independently.
//
//  - If the id exists in Kits  → calls Store::GiveKit  (items+dinos+commands)
//  - If the id exists in Items → calls GiveSingleItem directly (no charge)
//  - amount is only used for Items (multiplies Quantity); kits ignore it.
//
//  Returns "OK <id>" on success, "FAIL <reason>" on failure so that
//  arkshop_web can parse the RCON response and update order status.
// ─────────────────────────────────────────────────────────────────
void CmdAdminDeliver(APlayerController* pc, FString* cmd_str, bool) {
    auto* admin = static_cast<AShooterPlayerController*>(pc);
    if (!cmd_str) return;

    const auto parts = SplitCmd(cmd_str);
    if (parts.size() < 3) {
        if (admin) SendMsg(admin, FColorList::Red,
                           "Usage: Shop.Deliver <steamid> <item_or_kit_id> [amount=1]");
        return;
    }

    const std::string target_id = parts[1];
    const std::string id        = parts[2];
    int amount = 1;
    if (parts.size() >= 4) {
        try { amount = std::max(1, std::stoi(parts[3])); } catch (...) {}
    }

    auto* target = CustomShop::Bridge::FindPlayer(target_id);
    if (!target) {
        const std::string msg = "FAIL player_offline:" + target_id;
        if (admin) SendMsg(admin, FColorList::Red, msg);
        Log::GetLog()->warn("Shop.Deliver: {}", msg);
        return;
    }

    const bool is_kit  = CustomShop::ShopConfig::Get().Kits().contains(id);
    const bool is_item = CustomShop::ShopConfig::Get().Items().contains(id);

    if (!is_kit && !is_item) {
        const std::string msg = "FAIL unknown_id:" + id;
        if (admin) SendMsg(admin, FColorList::Red, msg);
        Log::GetLog()->warn("Shop.Deliver: {}", msg);
        return;
    }

    bool ok = false;
    if (is_kit) {
        ok = CustomShop::Store::GiveKit(target, id);
        CustomShop::Data::SendPlayerKits(target, target_id);
    } else {
        // Deliver item directly without charging points
        const auto& item      = CustomShop::ShopConfig::Get().Items().at(id);
        const std::string bp  = item.value("Blueprint", "");

        if (!bp.empty()) {
            const int   qty   = item.value("Quantity",       1) * amount;
            const float qual  = item.value("Quality",        0.0f);
            const bool  force = item.value("ForceBlueprint", false);

            FString fblueprint(bp.c_str());
            UClass* item_class = UVictoryCore::BPLoadClass(&fblueprint);
            if (item_class) {
                UPrimalInventoryComponent* inv = target->GetPlayerInventoryComponent();
                if (inv) {
                    UPrimalItem::AddNewItem(
                        TSubclassOf<UPrimalItem>(item_class),
                        inv,
                        false, false,
                        qual, !force,
                        qty, force,
                        0.0f, false,
                        TSubclassOf<UPrimalItem>(),
                        0.0f, false, false);
                    ok = true;
                }
            }
        }

        // Also deliver Items array if present (bundle)
        if (item.contains("Items")) {
            for (const auto& entry : item.at("Items")) {
                const std::string bp2  = entry.value("Blueprint",     "");
                const int   qty2       = entry.value("Quantity",      1) * amount;
                const float qual2      = entry.value("Quality",       0.0f);
                const bool  force2     = entry.value("ForceBlueprint",false);
                if (bp2.empty()) continue;
                FString fbp2(bp2.c_str());
                UClass* cls2 = UVictoryCore::BPLoadClass(&fbp2);
                if (!cls2) continue;
                UPrimalInventoryComponent* inv2 = target->GetPlayerInventoryComponent();
                if (!inv2) continue;
                UPrimalItem::AddNewItem(
                    TSubclassOf<UPrimalItem>(cls2),
                    inv2,
                    false, false,
                    qual2, !force2,
                    qty2, force2,
                    0.0f, false,
                    TSubclassOf<UPrimalItem>(),
                    0.0f, false, false);
                ok = true;
            }
        }
    }

    CustomShop::ShopPoints::Get().LogTransaction(
        "web_deliver", target_id, "", id, amount, 0, 0);

    const std::string result_msg = ok ? "OK " + id : "FAIL deliver_error:" + id;
    if (admin) SendMsg(admin, ok ? FColorList::Green : FColorList::Red, result_msg);
    Log::GetLog()->info("Shop.Deliver: steam_id='{}' id='{}' amount={} ok={}",
                        target_id, id, amount, ok);
}

// ─────────────────────────────────────────────────────────────────
//  Shop.GiveKit <steamid> <kit_id>
//  Admin: deliver a kit directly to a player by Steam ID.
// ─────────────────────────────────────────────────────────────────
void CmdAdminGiveKit(APlayerController* pc, FString* cmd_str, bool) {
    auto* admin = static_cast<AShooterPlayerController*>(pc);
    if (!cmd_str) return;

    const auto parts = SplitCmd(cmd_str);
    if (parts.size() < 3) {
        if (admin) SendMsg(admin, FColorList::Red,
                           "Usage: Shop.GiveKit <steamid> <kit_id>");
        return;
    }

    const std::string target_id = parts[1];
    const std::string kit_id    = parts[2];

    auto* target = CustomShop::Bridge::FindPlayer(target_id);
    if (!target) {
        if (admin) SendMsg(admin, FColorList::Red,
                           "Player " + target_id + " is not online.");
        return;
    }

    if (!CustomShop::ShopConfig::Get().Kits().contains(kit_id)) {
        if (admin) SendMsg(admin, FColorList::Red,
                           "Unknown kit_id '" + kit_id + "'.");
        return;
    }

    const bool ok = CustomShop::ShopPoints::Get().AddKitToStash(target_id, kit_id);
    if (ok) {
        CustomShop::ShopPoints::Get().LogTransaction(
            "give_kit", target_id, "", kit_id, 1, 0, 0);
        CustomShop::Data::SendPlayerKits(target, target_id);
        if (admin) SendMsg(admin, FColorList::Green,
                           "Kit '" + kit_id + "' added to stash for " + target_id);
        Log::GetLog()->info("GiveKit: kit='{}' added to stash for player='{}'", kit_id, target_id);
    } else {
        if (admin) SendMsg(admin, FColorList::Red,
                           "Failed to add kit '" + kit_id + "' to stash.");
    }
}

// ─────────────────────────────────────────────────────────────────
//  VIP commands (admin only)
// ─────────────────────────────────────────────────────────────────
void CmdAdminAddVip(APlayerController* pc, FString* cmd_str, bool) {
    auto* admin = static_cast<AShooterPlayerController*>(pc);
    if (!cmd_str) return;

    const auto parts = SplitCmd(cmd_str);
    // Usage: Shop.AddVip <steamid> [days] [tier]
    if (parts.size() < 2) {
        if (admin) SendMsg(admin, FColorList::Red,
                           "Usage: Shop.AddVip <steamid> [days=0] [tier=vip]");
        return;
    }

    const std::string steam_id = parts[1];
    int days = 0;
    if (parts.size() >= 3) {
        try { days = std::max(0, std::stoi(parts[2])); } catch (...) {}
    }
    const std::string tier = (parts.size() >= 4) ? parts[3] : "vip";

    if (CustomShop::ShopVip::Get().AddVip(steam_id, days, tier)) {
        const std::string msg = "VIP granted to " + steam_id +
            (days > 0 ? " for " + std::to_string(days) + " day(s)" : " permanently");
        if (admin) SendMsg(admin, FColorList::Green, msg);
    } else {
        if (admin) SendMsg(admin, FColorList::Red, "Failed to add VIP.");
    }
}

void CmdAdminRemoveVip(APlayerController* pc, FString* cmd_str, bool) {
    auto* admin = static_cast<AShooterPlayerController*>(pc);
    if (!cmd_str) return;

    const auto parts = SplitCmd(cmd_str);
    if (parts.size() < 2) {
        if (admin) SendMsg(admin, FColorList::Red,
                           "Usage: Shop.RemoveVip <steamid>");
        return;
    }

    const bool ok = CustomShop::ShopVip::Get().RemoveVip(parts[1]);
    if (admin)
        SendMsg(admin, ok ? FColorList::Green : FColorList::Red,
                ok ? "VIP removed." : "Player not found in VIP list.");
}

void CmdAdminListVip(APlayerController* pc, FString*, bool) {
    auto* admin = static_cast<AShooterPlayerController*>(pc);
    if (!admin) return;

    const auto list = CustomShop::ShopVip::Get().ListVip();
    if (list.empty()) {
        SendMsg(admin, FColorList::White, "No VIP players.");
        return;
    }
    for (const auto& v : list)
        SendMsg(admin, FColorList::Yellow,
                v.steam_id + " [" + v.tier + "] expires: " + v.expires);
}

// ─────────────────────────────────────────────────────────────────
//  Shop.Debug <steamid>
//  Admin diagnostic: tests every step of the buff/RPC chain for a
//  given player and reports pass/fail as persistent chat messages
//  (visible in RCON output and server log).
// ─────────────────────────────────────────────────────────────────
void CmdAdminDebug(APlayerController* pc, FString* cmd_str, bool) {
    auto* admin = static_cast<AShooterPlayerController*>(pc);
    if (!admin) return;

    const auto parts = SplitCmd(cmd_str);
    if (parts.size() < 2) {
        SendMsg(admin, FColorList::Red, "Usage: Shop.Debug <steamid>");
        return;
    }

    const std::string target_id = parts[1];
    auto* target = CustomShop::Bridge::FindPlayer(target_id);
    if (!target) {
        SendMsg(admin, FColorList::Red,
                "Player '" + target_id + "' is not online.");
        return;
    }

    CustomShop::Bridge::DiagnosePlayer(target, admin);
}

// ─────────────────────────────────────────────────────────────────
//  Shop.Players
//  Lists all online players and their SteamIDs in admin chat.
// ─────────────────────────────────────────────────────────────────
void CmdAdminPlayers(APlayerController* pc, FString*, bool) {
    auto* admin = static_cast<AShooterPlayerController*>(pc);
    if (!admin) return;

    const auto& pcs = ArkApi::GetApiUtils().GetWorld()->PlayerControllerListField();
    int count = 0;
    for (TWeakObjectPtr<APlayerController> wpc : pcs) {
        auto* sc = static_cast<AShooterPlayerController*>(wpc.Get());
        if (!sc) continue;
        const std::string sid = CustomShop::Bridge::GetSteamId(sc);
        const FString name = ArkApi::GetApiUtils().GetSteamName(sc);
        const std::string nameStr = name.ToString();
        SendMsg(admin, FColorList::White, nameStr + "  |  " + sid);
        Log::GetLog()->info("Shop.Players: '{}' = {}", nameStr, sid);
        ++count;
    }
    SendMsg(admin, FColorList::Yellow, std::to_string(count) + " player(s) online.");
}

} // anonymous namespace

namespace CustomShop {
namespace Commands {

void Register() {
    // Jogador — redireciona para a loja web
    ArkApi::GetCommands().AddChatCommand("/shop",          &CmdShop);
    ArkApi::GetCommands().AddChatCommand("/shop debug",    &CmdShopDebugSelf);
    ArkApi::GetCommands().AddChatCommand("/upload",        &CmdCloudUpload);
    ArkApi::GetCommands().AddChatCommand("/download",     &CmdCloudDownload);
    ArkApi::GetCommands().AddChatCommand("/nuvem",         &CmdCloudStatus);
    ArkApi::GetCommands().AddChatCommand("/cloud",         &CmdCloudStatus);
    ArkApi::GetCommands().AddOnChatMessageCallback(
        "CustomShopCloudChat", &OnCloudChatMessage);

    // Admin (RCON ou console in-game)
    ArkApi::GetCommands().AddConsoleCommand("Shop.Upload",     &CmdConsoleCloudUpload);
    ArkApi::GetCommands().AddConsoleCommand("Shop.Download",   &CmdConsoleCloudDownload);
    ArkApi::GetCommands().AddConsoleCommand("Shop.Nuvem",      &CmdConsoleCloudStatus);
    ArkApi::GetCommands().AddConsoleCommand("Shop.Cloud",      &CmdConsoleCloudStatus);
    ArkApi::GetCommands().AddConsoleCommand("Shop.AddPoints",  &CmdAdminAddPoints);
    ArkApi::GetCommands().AddConsoleCommand("Shop.SetPoints",  &CmdAdminSetPoints);
    ArkApi::GetCommands().AddConsoleCommand("Shop.GetPoints",  &CmdAdminGetPoints);
    ArkApi::GetCommands().AddConsoleCommand("Shop.Reload",     &CmdAdminReload);
    ArkApi::GetCommands().AddConsoleCommand("Shop.GiveKit",    &CmdAdminGiveKit);
    ArkApi::GetCommands().AddConsoleCommand("Shop.Deliver",    &CmdAdminDeliver);
    ArkApi::GetCommands().AddConsoleCommand("Shop.AddVip",     &CmdAdminAddVip);
    ArkApi::GetCommands().AddConsoleCommand("Shop.RemoveVip",  &CmdAdminRemoveVip);
    ArkApi::GetCommands().AddConsoleCommand("Shop.ListVip",    &CmdAdminListVip);
    ArkApi::GetCommands().AddConsoleCommand("Shop.Debug",      &CmdAdminDebug);
    ArkApi::GetCommands().AddConsoleCommand("Shop.Players",    &CmdAdminPlayers);
}

void Unregister() {
    ArkApi::GetCommands().RemoveChatCommand("/shop");
    ArkApi::GetCommands().RemoveChatCommand("/shop debug");
    ArkApi::GetCommands().RemoveChatCommand("/upload");
    ArkApi::GetCommands().RemoveChatCommand("/download");
    ArkApi::GetCommands().RemoveChatCommand("/nuvem");
    ArkApi::GetCommands().RemoveOnChatMessageCallback("CustomShopCloudChat");
    ArkApi::GetCommands().RemoveChatCommand("/cloud");
    ArkApi::GetCommands().RemoveConsoleCommand("Shop.Upload");
    ArkApi::GetCommands().RemoveConsoleCommand("Shop.Download");
    ArkApi::GetCommands().RemoveConsoleCommand("Shop.Nuvem");
    ArkApi::GetCommands().RemoveConsoleCommand("Shop.Cloud");
    ArkApi::GetCommands().RemoveConsoleCommand("Shop.AddPoints");
    ArkApi::GetCommands().RemoveConsoleCommand("Shop.SetPoints");
    ArkApi::GetCommands().RemoveConsoleCommand("Shop.GetPoints");
    ArkApi::GetCommands().RemoveConsoleCommand("Shop.Reload");
    ArkApi::GetCommands().RemoveConsoleCommand("Shop.GiveKit");
    ArkApi::GetCommands().RemoveConsoleCommand("Shop.Deliver");
    ArkApi::GetCommands().RemoveConsoleCommand("Shop.AddVip");
    ArkApi::GetCommands().RemoveConsoleCommand("Shop.RemoveVip");
    ArkApi::GetCommands().RemoveConsoleCommand("Shop.ListVip");
    ArkApi::GetCommands().RemoveConsoleCommand("Shop.Debug");
    ArkApi::GetCommands().RemoveConsoleCommand("Shop.Players");
    ArkApi::GetCommands().RemoveChatCommand("/shop debug");
}

} // namespace Commands
} // namespace CustomShop
