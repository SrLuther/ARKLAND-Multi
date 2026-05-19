#include "pch.h"
#include "Commands.h"
#include "ShopBridge.h"
#include "ShopConfig.h"
#include "ShopData.h"
#include "ShopPoints.h"
#include "ShopStore.h"
#include "ShopVip.h"

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
    if (CustomShop::ShopConfig::Get().Kits().contains(id))
        success = CustomShop::Store::BuyKit(controller, id);
    else
        success = CustomShop::Store::BuyItem(controller, id, amount);

    CustomShop::Data::SendBuyResult(controller, steam_id, id, amount, success);
    CustomShop::Data::SendPoints(controller);
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

void CmdGetPoints(APlayerController* pc, FString*, bool) {
    auto* c = static_cast<AShooterPlayerController*>(pc);
    if (c) CustomShop::Data::SendPoints(c);
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

        const auto& pcs =
            ArkApi::GetApiUtils().GetWorld()->PlayerControllerListField();
        for (TWeakObjectPtr<APlayerController> wpc : pcs) {
            auto* sc = static_cast<AShooterPlayerController*>(wpc.Get());
            if (!sc) continue;
            CustomShop::Data::SendShopItems(sc);
            CustomShop::Data::SendKits(sc);
            CustomShop::Data::SendReload(sc);
        }

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

    const bool ok = CustomShop::Store::GiveKit(target, kit_id);
    if (ok) {
        CustomShop::ShopPoints::Get().LogTransaction(
            "give_kit", target_id, "", kit_id, 1, 0, 0);
        if (admin) SendMsg(admin, FColorList::Green,
                           "Kit '" + kit_id + "' delivered to " + target_id);
        Log::GetLog()->info("GiveKit: kit='{}' → player='{}'", kit_id, target_id);
    } else {
        if (admin) SendMsg(admin, FColorList::Red,
                           "Failed to deliver kit '" + kit_id + "'.");
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

} // anonymous namespace

namespace CustomShop {
namespace Commands {

void Register() {
    // Mod-facing (called automatically by the MX-E UI mod)
    ArkApi::GetCommands().AddConsoleCommand("BuyItem",      &CmdBuyItem);
    ArkApi::GetCommands().AddConsoleCommand("GetShopItems", &CmdGetShopItems);
    ArkApi::GetCommands().AddConsoleCommand("GetPoints",    &CmdGetPoints);
    ArkApi::GetCommands().AddConsoleCommand("GetKits",      &CmdGetKits);
    ArkApi::GetCommands().AddConsoleCommand("PlayerKits",   &CmdPlayerKits);

    // Player trade (called by mod when TradeButton is used)
    ArkApi::GetCommands().AddConsoleCommand("Shop.Trade",   &CmdTrade);

    // Admin (RCON or in-game cheat console)
    ArkApi::GetCommands().AddConsoleCommand("Shop.AddPoints",  &CmdAdminAddPoints);
    ArkApi::GetCommands().AddConsoleCommand("Shop.SetPoints",  &CmdAdminSetPoints);
    ArkApi::GetCommands().AddConsoleCommand("Shop.GetPoints",  &CmdAdminGetPoints);
    ArkApi::GetCommands().AddConsoleCommand("Shop.Reload",     &CmdAdminReload);
    ArkApi::GetCommands().AddConsoleCommand("Shop.GiveKit",    &CmdAdminGiveKit);
    ArkApi::GetCommands().AddConsoleCommand("Shop.AddVip",     &CmdAdminAddVip);
    ArkApi::GetCommands().AddConsoleCommand("Shop.RemoveVip",  &CmdAdminRemoveVip);
    ArkApi::GetCommands().AddConsoleCommand("Shop.ListVip",    &CmdAdminListVip);
}

void Unregister() {
    ArkApi::GetCommands().RemoveConsoleCommand("BuyItem");
    ArkApi::GetCommands().RemoveConsoleCommand("GetShopItems");
    ArkApi::GetCommands().RemoveConsoleCommand("GetPoints");
    ArkApi::GetCommands().RemoveConsoleCommand("GetKits");
    ArkApi::GetCommands().RemoveConsoleCommand("PlayerKits");
    ArkApi::GetCommands().RemoveConsoleCommand("Shop.Trade");
    ArkApi::GetCommands().RemoveConsoleCommand("Shop.AddPoints");
    ArkApi::GetCommands().RemoveConsoleCommand("Shop.SetPoints");
    ArkApi::GetCommands().RemoveConsoleCommand("Shop.GetPoints");
    ArkApi::GetCommands().RemoveConsoleCommand("Shop.Reload");
    ArkApi::GetCommands().RemoveConsoleCommand("Shop.GiveKit");
    ArkApi::GetCommands().RemoveConsoleCommand("Shop.AddVip");
    ArkApi::GetCommands().RemoveConsoleCommand("Shop.RemoveVip");
    ArkApi::GetCommands().RemoveConsoleCommand("Shop.ListVip");
}

} // namespace Commands
} // namespace CustomShop
