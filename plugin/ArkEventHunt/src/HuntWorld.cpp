#include "pch.h"
#include "HuntWorld.h"
#include "HuntConfig.h"

namespace ArkEventHunt {
namespace World {

int64_t NowUnix() {
    return static_cast<int64_t>(
    std::chrono::duration_cast<std::chrono::seconds>(
            std::chrono::system_clock::now().time_since_epoch())
            .count());
}

std::wstring Utf8ToWide(const std::string& text) {
    if (text.empty()) return L"";
    const int len = MultiByteToWideChar(
        CP_UTF8, 0, text.c_str(), -1, nullptr, 0);
    if (len <= 0) return std::wstring(text.begin(), text.end());
    std::wstring out(static_cast<size_t>(len - 1), L'\0');
    MultiByteToWideChar(CP_UTF8, 0, text.c_str(), -1, &out[0], len);
    return out;
}

std::string Utf8ToAnsi(const std::string& text) {
    if (text.empty()) return "";
    const std::wstring w = Utf8ToWide(text);
    if (w.empty()) return text;
    const int len = WideCharToMultiByte(
        CP_ACP, 0, w.c_str(), -1, nullptr, 0, nullptr, nullptr);
    if (len <= 0) return text;
    std::string out(static_cast<size_t>(len - 1), '\0');
    WideCharToMultiByte(
        CP_ACP, 0, w.c_str(), -1, &out[0], len, nullptr, nullptr);
    return out;
}

APrimalDinoCharacter* FindDinoByIds(uint32_t id1, uint32_t id2) {
    if (id1 == 0 && id2 == 0) return nullptr;
    UWorld* world = ArkApi::GetApiUtils().GetWorld();
    if (!world) return nullptr;

    TArray<AActor*> actors;
    UGameplayStatics::GetAllActorsOfClass(
        world, APrimalDinoCharacter::GetPrivateStaticClass(), &actors);

    for (AActor* actor : actors) {
        auto* dino = static_cast<APrimalDinoCharacter*>(actor);
        if (!dino) continue;
        int a = 0;
        int b = 0;
        dino->GetDinoIDs(&a, &b);
        if (static_cast<uint32_t>(a) == id1 &&
            static_cast<uint32_t>(b) == id2)
            return dino;
    }
    return nullptr;
}

bool DespawnDino(uint32_t id1, uint32_t id2) {
    APrimalDinoCharacter* dino = FindDinoByIds(id1, id2);
    if (!dino) return false;
    try {
        dino->Destroy(true, false);
        Log::GetLog()->info(
            "ArkEventHunt despawn: id1={} id2={}", id1, id2);
        return true;
    } catch (...) {
        Log::GetLog()->warn(
            "ArkEventHunt despawn failed: id1={} id2={}", id1, id2);
        return false;
    }
}

void BroadcastChat(const std::string& message) {
    if (message.empty()) return;
    UWorld* world = ArkApi::GetApiUtils().GetWorld();
    if (!world) return;

    const std::wstring wsender = Utf8ToWide(HuntConfig::Get().SenderName());
    const std::wstring wmsg = Utf8ToWide(message);

    FChatMessage chat;
    chat.SenderName = FString(wsender.c_str());
    chat.Message = FString(wmsg.c_str());
    chat.SenderSteamName = FString();
    chat.SenderTribeName = FString();
    chat.SenderId = 0;
    chat.SenderIcon = nullptr;
    chat.UserId = FString();

    const auto& pcs = world->PlayerControllerListField();
    for (TWeakObjectPtr<APlayerController> pc : pcs) {
        auto* shooter = static_cast<AShooterPlayerController*>(pc.Get());
        if (shooter)
            shooter->ClientChatMessage(chat);
    }
}

bool IsPersonalTameActor(AActor* actor) {
    if (!actor) return false;
    if (!actor->IsA(APrimalDinoCharacter::GetPrivateStaticClass()))
        return false;
    auto* dino = static_cast<APrimalDinoCharacter*>(actor);
    return dino->TamingTeamIDField() != 0;
}

AShooterPlayerController* FindPlayerBySteamId(const std::string& steam_id) {
    if (steam_id.empty()) return nullptr;
    UWorld* world = ArkApi::GetApiUtils().GetWorld();
    if (!world) return nullptr;
    const auto& controllers = world->PlayerControllerListField();
    for (TWeakObjectPtr<APlayerController> wpc : controllers) {
        auto* sc = static_cast<AShooterPlayerController*>(wpc.Get());
        if (!sc) continue;
        const uint64 id =
            ArkApi::GetApiUtils().GetSteamIdFromController(sc);
        if (id != 0 && std::to_string(id) == steam_id)
            return sc;
    }
    return nullptr;
}

static bool InventoryLooksFull(UPrimalInventoryComponent* inv) {
    if (!inv) return true;
    try {
        const int cur = inv->InventoryItemsField().Num();
        int max_slots = inv->GetMaxInventoryItems(true);
        if (max_slots <= 0)
            max_slots = inv->AbsoluteMaxInventoryItemsField();
        if (max_slots > 0 && cur >= max_slots)
            return true;
    } catch (...) {
    }
    return false;
}

GiveItemResult GiveItemToPlayer(AShooterPlayerController* controller,
                                const std::string& blueprint, int quantity) {
    if (!controller || blueprint.empty() || quantity < 1)
        return GiveItemResult::NoController;

    FString fbp(blueprint.c_str());
    UClass* item_class = UVictoryCore::BPLoadClass(&fbp);
    if (!item_class) {
        Log::GetLog()->warn(
            "ArkEventHunt GiveItem: BPLoadClass failed '{}'", blueprint);
        return GiveItemResult::LoadFailed;
    }

    UPrimalInventoryComponent* inv = controller->GetPlayerInventoryComponent();
    if (!inv) {
        Log::GetLog()->warn("ArkEventHunt GiveItem: no inventory");
        return GiveItemResult::NoInventory;
    }

    if (InventoryLooksFull(inv)) {
        Log::GetLog()->warn(
            "ArkEventHunt GiveItem: inventory full bp='{}' qty={}",
            blueprint, quantity);
        return GiveItemResult::InventoryFull;
    }

    UPrimalItem* created = UPrimalItem::AddNewItem(
        TSubclassOf<UPrimalItem>(item_class),
        inv,
        false,
        false,
        0.0f,
        true,
        quantity,
        false,
        0.0f,
        false,
        TSubclassOf<UPrimalItem>(),
        0.0f,
        false,
        false);

    if (!created) {
        Log::GetLog()->warn(
            "ArkEventHunt GiveItem: AddNewItem failed (full?) bp='{}' qty={}",
            blueprint, quantity);
        return GiveItemResult::InventoryFull;
    }

    Log::GetLog()->info(
        "ArkEventHunt GiveItem: delivered qty={} bp={}", quantity, blueprint);
    return GiveItemResult::Ok;
}

int GiveLootTable(AShooterPlayerController* controller,
                  const std::vector<LootEntry>& loot) {
    if (!controller || loot.empty()) return 0;

    int ok = 0;
    bool warned_full = false;
    for (const auto& row : loot) {
        if (row.blueprint.empty() || row.qty < 1) continue;
        const GiveItemResult r =
            GiveItemToPlayer(controller, row.blueprint, row.qty);
        if (r == GiveItemResult::Ok) {
            ++ok;
            continue;
        }
        if (r == GiveItemResult::InventoryFull && !warned_full) {
            warned_full = true;
            const std::string ansi = Utf8ToAnsi(
                HuntConfig::Get().Msg(
                    "LootInventoryFull",
                    "Inventário cheio — não foi possível receber todo o loot "
                    "do evento."));
            ArkApi::GetApiUtils().SendServerMessage(
                controller, FColorList::Yellow, ansi.c_str());
            Log::GetLog()->warn(
                "ArkEventHunt loot: inventory full mid-grant "
                "(delivered={}/{})",
                ok, loot.size());
        } else if (r == GiveItemResult::LoadFailed) {
            Log::GetLog()->warn(
                "ArkEventHunt loot: skip unloadable bp='{}'", row.blueprint);
        }
    }
    if (ok > 0) {
        const std::string ansi = Utf8ToAnsi(
            HuntConfig::Get().Msg(
                "LootGranted",
                "Loot do evento entregue no inventário."));
        ArkApi::GetApiUtils().SendServerMessage(
            controller, FColorList::Green, ansi.c_str());
    }
    return ok;
}

} // namespace World
} // namespace ArkEventHunt
