#include "pch.h"
#include "ShopStore.h"
#include "ShopBridge.h"
#include "ShopConfig.h"
#include "ShopPoints.h"
#include "ShopPerms.h"

namespace {

// ── Helpers ──────────────────────────────────────────────────────

// Delivers a single item stack using UPrimalItem::AddNewItem.
void GiveSingleItem(AShooterPlayerController* controller,
                    const std::string& blueprint,
                    int quantity,
                    float quality,
                    bool force_blueprint) {
    if (blueprint.empty() || !controller) return;

    FString fblueprint(blueprint.c_str());
    UClass* item_class = UVictoryCore::BPLoadClass(&fblueprint);
    if (!item_class) {
        Log::GetLog()->warn("GiveSingleItem: failed to load class '{}'", blueprint);
        return;
    }

    UPrimalInventoryComponent* inv = controller->GetPlayerInventoryComponent();
    if (!inv) return;

    UPrimalItem::AddNewItem(
        TSubclassOf<UPrimalItem>(item_class),
        inv,
        /*bEquipItem=*/false,
        /*bDontStack=*/false,
        quality,
        /*bForceNoBlueprint=*/!force_blueprint,
        quantity,
        /*bForceBlueprint=*/force_blueprint,
        /*MaxItemDifficultyClamp=*/0.0f,
        /*CreateOnClient=*/false,
        TSubclassOf<UPrimalItem>(),
        /*MinRandomQuality=*/0.0f,
        /*clampStats=*/false,
        /*bIgnoreAbsoluteMaxInventory=*/false);
}

// Delivers all items in an "Items" JSON array.
void GiveItemsArray(AShooterPlayerController* controller,
                    const nlohmann::json& items_array) {
    for (const auto& entry : items_array) {
        GiveSingleItem(controller,
                       entry.value("Blueprint",     ""),
                       entry.value("Quantity",      1),
                       entry.value("Quality",       0.0f),
                       entry.value("ForceBlueprint",false));
    }
}

// Spawns one tamed dino near the player.
void SpawnSingleDino(AShooterPlayerController* controller,
                     const std::string& blueprint,
                     int level,
                     bool force_tame,
                     bool neutered) {
    if (blueprint.empty() || !controller) return;

    FString fbp(blueprint.c_str());
    // location = nullptr → spawn near player
    APrimalDinoCharacter* dino = ArkApi::GetApiUtils().SpawnDino(
        controller, fbp, nullptr, level, force_tame, neutered);

    if (!dino)
        Log::GetLog()->warn("SpawnSingleDino: failed to spawn '{}'", blueprint);
}

// Spawns all dinos in a "Dinos" JSON array.
void SpawnDinosArray(AShooterPlayerController* controller,
                     const nlohmann::json& dinos_array) {
    for (const auto& entry : dinos_array) {
        SpawnSingleDino(controller,
                        entry.value("Blueprint",  ""),
                        entry.value("Level",      150),
                        entry.value("ForceTame",  true),
                        entry.value("Neutered",   false));
    }
}

// Executes kit Commands[], replacing {SteamID} placeholder.
void RunCommands(const nlohmann::json& commands_array,
                 AShooterPlayerController* controller,
                 const std::string& steam_id) {
    for (const auto& cmd_json : commands_array) {
        if (!cmd_json.is_string()) continue;
        std::string cmd = cmd_json.get<std::string>();

        // Replace {SteamID} placeholder
        const std::string token = "{SteamID}";
        size_t pos = 0;
        while ((pos = cmd.find(token, pos)) != std::string::npos) {
            cmd.replace(pos, token.size(), steam_id);
            pos += steam_id.size();
        }

        FString fscmd(cmd.c_str());
        FString result;
        controller->ConsoleCommand(&result, &fscmd, true);
    }
}

} // anonymous namespace

namespace CustomShop {
namespace Store {

bool BuyItem(AShooterPlayerController* controller,
             const std::string& item_id,
             int amount) {
    if (!controller || amount < 1) return false;

    const auto& items = ShopConfig::Get().Items();
    if (!items.contains(item_id)) {
        Log::GetLog()->warn("BuyItem: unknown item_id '{}'", item_id);
        return false;
    }

    const auto& item  = items.at(item_id);
    const int price   = item.value("Price", 0) * amount;
    const std::string id = Bridge::GetSteamId(controller);

    if (!ShopPoints::Get().SpendPoints(id, price)) {
        Log::GetLog()->info("BuyItem: player {} cannot afford '{}' (price={})",
                            id, item_id, price);
        return false;
    }

    // Single blueprint entry
    const std::string bp = item.value("Blueprint", "");
    if (!bp.empty()) {
        const int   qty   = item.value("Quantity",       1) * amount;
        const float qual  = item.value("Quality",        0.0f);
        const bool  force = item.value("ForceBlueprint", false);
        GiveSingleItem(controller, bp, qty, qual, force);
    }

    // Multi-item bundle (Items array)
    if (item.contains("Items"))
        GiveItemsArray(controller, item.at("Items"));

    Log::GetLog()->info("BuyItem: player {} bought '{}' x{}", id, item_id, amount);
    return true;
}

bool BuyKit(AShooterPlayerController* controller,
            const std::string& kit_id) {
    if (!controller) return false;

    const auto& kits = ShopConfig::Get().Kits();
    if (!kits.contains(kit_id)) {
        Log::GetLog()->warn("BuyKit: unknown kit_id '{}'", kit_id);
        return false;
    }

    const auto& kit  = kits.at(kit_id);
    const int price  = kit.value("Price", 0);
    const std::string id = Bridge::GetSteamId(controller);

    // ── Permission check ──────────────────────────────────────────
    // "Permissions" is an optional comma-separated list of group names.
    // If present, the player must belong to at least one of them.
    if (kit.contains("Permissions")) {
        const std::string perms_str = kit.value("Permissions", "");
        if (!perms_str.empty()) {
            std::vector<std::string> required_groups;
            std::stringstream ss(perms_str);
            std::string token;
            while (std::getline(ss, token, ',')) {
                // trim leading/trailing whitespace
                const auto first = token.find_first_not_of(" \t");
                if (first == std::string::npos) continue;
                const auto last = token.find_last_not_of(" \t");
                required_groups.push_back(token.substr(first, last - first + 1));
            }

            uint64_t steam_id = 0;
            try { steam_id = std::stoull(id); } catch (...) {}

            if (!Perms::IsInAnyGroup(steam_id, required_groups)) {
                Log::GetLog()->info(
                    "BuyKit: player {} lacks permission for kit '{}' (requires: {})",
                    id, kit_id, perms_str);
                return false;
            }
        }
    }
    // ─────────────────────────────────────────────────────────────

    if (!ShopPoints::Get().SpendPoints(id, price)) {
        Log::GetLog()->info("BuyKit: player {} cannot afford kit '{}' (price={})",
                            id, kit_id, price);
        return false;
    }

    if (kit.contains("Items"))    GiveItemsArray(controller,  kit.at("Items"));
    if (kit.contains("Dinos"))    SpawnDinosArray(controller, kit.at("Dinos"));
    if (kit.contains("Commands")) RunCommands(kit.at("Commands"), controller, id);

    Log::GetLog()->info("BuyKit: player {} redeemed kit '{}'", id, kit_id);
    return true;
}

bool GiveKit(AShooterPlayerController* controller,
             const std::string& kit_id) {
    if (!controller) return false;

    const auto& kits = ShopConfig::Get().Kits();
    if (!kits.contains(kit_id)) {
        Log::GetLog()->warn("GiveKit: unknown kit_id '{}'", kit_id);
        return false;
    }

    const auto& kit = kits.at(kit_id);
    const std::string id = Bridge::GetSteamId(controller);

    if (kit.contains("Items"))    GiveItemsArray(controller,  kit.at("Items"));
    if (kit.contains("Dinos"))    SpawnDinosArray(controller, kit.at("Dinos"));
    if (kit.contains("Commands")) RunCommands(kit.at("Commands"), controller, id);

    Log::GetLog()->info("GiveKit: kit '{}' delivered to player '{}'", kit_id, id);
    return true;
}

} // namespace Store
} // namespace CustomShop
