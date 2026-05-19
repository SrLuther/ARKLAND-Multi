#include "pch.h"
#include "ShopData.h"
#include "ShopBridge.h"
#include "ShopConfig.h"
#include "ShopPoints.h"
#include "ShopVip.h"

namespace {

std::string ToLower(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(),
                   [](unsigned char c) {
                       return static_cast<char>(std::tolower(c));
                   });
    return s;
}

nlohmann::json PlayerResult(const std::string& steam_id) {
    return nlohmann::json{ { "SteamID", steam_id } };
}

} // anonymous namespace

namespace CustomShop {
namespace Data {

bool SendShopItems(AShooterPlayerController* controller,
                   const std::string& type_filter) {
    if (!controller) return false;

    const auto& cfg          = ShopConfig::Get().Items();
    const std::string filter = ToLower(type_filter);

    nlohmann::json items = nlohmann::json::array();
    for (auto it = cfg.begin(); it != cfg.end(); ++it) {
        const auto& item = it.value();
        const std::string type = item.value("Type", "item");

        if (!filter.empty() && ToLower(type) != filter)
            continue;

        nlohmann::json entry      = item;          // preserve extra fields
        entry["Id"]               = it.key();
        entry["Type"]             = type;
        entry["Price"]            = item.value("Price",       0);
        entry["Description"]      = item.value("Description", "");
        entry["Blueprint"]        = item.value("Blueprint",   "");

        // If the top-level Blueprint is empty, try first item in Items array
        if (entry["Blueprint"].get<std::string>().empty()) {
            const auto sub = item.value("Items", nlohmann::json::array());
            if (!sub.empty())
                entry["Blueprint"] = sub[0].value("Blueprint", "");
        }

        items.push_back(std::move(entry));
    }

    nlohmann::json payload;
    payload["Command"]        = "GetShopItems";
    payload["Result"]["Data"] = items;
    return Bridge::SendPayload(controller, payload);
}

bool SendPoints(AShooterPlayerController* controller) {
    if (!controller) return false;
    const std::string id = Bridge::GetSteamId(controller);
    if (id.empty()) return false;

    nlohmann::json payload;
    payload["Command"]         = "GetPoints";
    payload["Result"]          = PlayerResult(id);
    payload["Result"]["Point"] = ShopPoints::Get().GetPoints(id);
    return Bridge::SendPayload(controller, payload);
}

bool SendKits(AShooterPlayerController* controller) {
    if (!controller) return false;

    const auto& cfg = ShopConfig::Get().Kits();
    nlohmann::json kits = nlohmann::json::array();
    for (auto it = cfg.begin(); it != cfg.end(); ++it) {
        const auto& k = it.value();
        kits.push_back({
            { "Id",            it.key() },
            { "Items",         k.value("Items",         nlohmann::json::array()) },
            { "Dinos",         k.value("Dinos",         nlohmann::json::array()) },
            { "Commands",      k.value("Commands",      nlohmann::json::array()) },
            { "DefaultAmount", k.value("DefaultAmount", 1)                       },
            { "Price",         k.value("Price",         0)                       },
            { "Description",   k.value("Description",   "")                     }
        });
    }

    nlohmann::json payload;
    payload["Command"] = "GetKits";
    payload["Result"]  = kits;
    return Bridge::SendPayload(controller, payload);
}

bool SendPlayerKits(AShooterPlayerController* controller,
                    const std::string& steam_id) {
    if (!controller) return false;

    const auto& cfg = ShopConfig::Get().Kits();
    nlohmann::json kits_map = nlohmann::json::object();
    for (auto it = cfg.begin(); it != cfg.end(); ++it)
        kits_map[it.key()]["Amount"] = it.value().value("DefaultAmount", 1);

    nlohmann::json payload;
    payload["Command"]        = "PlayerKits";
    payload["Result"]         = PlayerResult(steam_id);
    payload["Result"]["Kits"] = kits_map;
    return Bridge::SendPayload(controller, payload);
}

bool SendBuyResult(AShooterPlayerController* controller,
                   const std::string& steam_id,
                   const std::string& item_id,
                   int amount,
                   bool success) {
    nlohmann::json payload;
    payload["Command"]           = "BuyItem";
    payload["Success"]           = success;
    payload["Result"]            = PlayerResult(steam_id);
    payload["Result"]["ItemId"]  = item_id;
    payload["Result"]["Amount"]  = amount;
    return Bridge::SendPayload(controller, payload);
}

bool SendTradeResult(AShooterPlayerController* sender,
                     AShooterPlayerController* receiver,
                     const std::string& sender_id,
                     const std::string& receiver_id,
                     int amount,
                     bool success) {
    // Notify sender
    {
        nlohmann::json p;
        p["Command"]              = "TradePoints";
        p["Success"]              = success;
        p["Result"]["SteamID"]    = sender_id;
        p["Result"]["TargetID"]   = receiver_id;
        p["Result"]["Amount"]     = amount;
        p["Result"]["Point"]      = ShopPoints::Get().GetPoints(sender_id);
        p["Result"]["IsSender"]   = true;
        Bridge::SendPayload(sender, p);
    }
    // Notify receiver if online
    if (receiver) {
        nlohmann::json p;
        p["Command"]              = "TradePoints";
        p["Success"]              = success;
        p["Result"]["SteamID"]    = receiver_id;
        p["Result"]["TargetID"]   = sender_id;
        p["Result"]["Amount"]     = amount;
        p["Result"]["Point"]      = ShopPoints::Get().GetPoints(receiver_id);
        p["Result"]["IsSender"]   = false;
        Bridge::SendPayload(receiver, p);
    }
    return true;
}

bool SendReload(AShooterPlayerController* controller) {
    nlohmann::json payload;
    payload["Command"] = "Reload";
    payload["Result"]  = nlohmann::json::object();
    return Bridge::SendPayload(controller, payload);
}

void InitPlayer(AShooterPlayerController* controller) {
    if (!controller) return;
    const std::string id = Bridge::GetSteamId(controller);
    if (id.empty()) return;

    // Register player in DB with starting points if new.
    ShopPoints::Get().GetPoints(id);

    // Apply buff — if the character hasn't spawned yet this returns null
    // and the mod will pull data when the hotkey is first pressed.
    Bridge::GetOrAddShopBuff(controller);

    SendShopItems(controller);
    SendPoints(controller);
    SendKits(controller);
    SendPlayerKits(controller, id);
}

} // namespace Data
} // namespace CustomShop
