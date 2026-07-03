#include "pch.h"
#include "ShopCryoDino.h"
#include "ShopConfig.h"

namespace {

constexpr const char* kDefaultCryoBp =
    "Blueprint'/Game/Extinction/CoreBlueprints/Weapons/"
    "PrimalItem_WeaponEmptyCryopod.PrimalItem_WeaponEmptyCryopod'";

std::string NormalizeBlueprintPath(std::string bp) {
    if (bp.empty()) return bp;
    if (bp.find("Blueprint'") != std::string::npos) return bp;
    if (bp.front() == '/')
        return "Blueprint'" + bp + "'";
    return "Blueprint'/Game/" + bp + "'";
}

void NotifyPlayer(AShooterPlayerController* controller,
                  const FLinearColor& color,
                  const std::string& msg) {
    if (controller && !msg.empty())
        ArkApi::GetApiUtils().SendServerMessage(controller, color, msg.c_str());
}

bool ShouldUseCryopod(const nlohmann::json& entry) {
    if (entry.value("PreventCryo", false))
        return false;
    if (entry.contains("Cryopod"))
        return entry.value("Cryopod", false);
    return CustomShop::ShopConfig::Get().DeliverDinosInCryopods();
}

void ApplyGender(APrimalDinoCharacter* dino, const std::string& gender) {
    if (!dino || gender.empty() || !dino->bUsesGender()())
        return;
    if (gender == "male" || gender == "Male")
        dino->bIsFemale() = false;
    else if (gender == "female" || gender == "Female")
        dino->bIsFemale() = true;
}

UPrimalItem* CreateSaddleItem(const std::string& saddle_blueprint) {
    if (saddle_blueprint.empty())
        return nullptr;
    const std::string bp = NormalizeBlueprintPath(saddle_blueprint);
    FString fbp(bp.c_str());
    UClass* cls = UVictoryCore::BPLoadClass(&fbp);
    if (!cls)
        return nullptr;
    UPrimalItem* item = UPrimalItem::AddNewItem(
        cls, nullptr, false, false, 0.0f, false, 0, false, 0.0f,
        false, nullptr, 0.0f, false, false);
    if (!item) return nullptr;

    // Force a Defense metadata entry so serialized item bytes include it.
    // This ensures generated cryopod/item blobs retain the defense value.
    FCustomItemData defData;
    defData.CustomDataName = FName("Defense", EFindName::FNAME_Add);
    defData.CustomDataFloats.Add(350.0f);
    item->CustomItemDatasField().Add(defData);
    item->UpdatedItem(true);
    return item;
}

FCustomItemData BuildCryoCustomData(APrimalDinoCharacter* dino, UPrimalItem* saddle) {
    FCustomItemData customItemData;
    FARKDinoData dinoData;
    dino->GetDinoData(&dinoData);

    customItemData.CustomDataName = FName("Dino", EFindName::FNAME_Add);
    customItemData.CustomDataNames.Add(FName("MissionTemporary", EFindName::FNAME_Add));
    customItemData.CustomDataNames.Add(FName("None", EFindName::FNAME_Find));

    auto* stat = dino->MyCharacterStatusComponentField();
    if (stat) {
        customItemData.CustomDataFloats.Add(stat->CurrentStatusValuesField()()[EPrimalCharacterStatusValue::Health]);
        customItemData.CustomDataFloats.Add(stat->CurrentStatusValuesField()()[EPrimalCharacterStatusValue::Stamina]);
        customItemData.CustomDataFloats.Add(stat->CurrentStatusValuesField()()[EPrimalCharacterStatusValue::Torpidity]);
        customItemData.CustomDataFloats.Add(stat->CurrentStatusValuesField()()[EPrimalCharacterStatusValue::Oxygen]);
        customItemData.CustomDataFloats.Add(stat->CurrentStatusValuesField()()[EPrimalCharacterStatusValue::Food]);
        customItemData.CustomDataFloats.Add(stat->CurrentStatusValuesField()()[EPrimalCharacterStatusValue::Water]);
        customItemData.CustomDataFloats.Add(stat->CurrentStatusValuesField()()[EPrimalCharacterStatusValue::Temperature]);
        customItemData.CustomDataFloats.Add(stat->CurrentStatusValuesField()()[EPrimalCharacterStatusValue::Weight]);
        customItemData.CustomDataFloats.Add(stat->CurrentStatusValuesField()()[EPrimalCharacterStatusValue::MeleeDamageMultiplier]);
        customItemData.CustomDataFloats.Add(stat->CurrentStatusValuesField()()[EPrimalCharacterStatusValue::SpeedMultiplier]);
        customItemData.CustomDataFloats.Add(stat->CurrentStatusValuesField()()[EPrimalCharacterStatusValue::TemperatureFortitude]);
        customItemData.CustomDataFloats.Add(stat->CurrentStatusValuesField()()[EPrimalCharacterStatusValue::CraftingSpeedMultiplier]);
        customItemData.CustomDataFloats.Add(stat->MaxStatusValuesField()()[EPrimalCharacterStatusValue::Health]);
        customItemData.CustomDataFloats.Add(stat->MaxStatusValuesField()()[EPrimalCharacterStatusValue::Stamina]);
        customItemData.CustomDataFloats.Add(stat->MaxStatusValuesField()()[EPrimalCharacterStatusValue::Torpidity]);
        customItemData.CustomDataFloats.Add(stat->MaxStatusValuesField()()[EPrimalCharacterStatusValue::Oxygen]);
        customItemData.CustomDataFloats.Add(stat->MaxStatusValuesField()()[EPrimalCharacterStatusValue::Food]);
        customItemData.CustomDataFloats.Add(stat->MaxStatusValuesField()()[EPrimalCharacterStatusValue::Water]);
        customItemData.CustomDataFloats.Add(stat->MaxStatusValuesField()()[EPrimalCharacterStatusValue::Temperature]);
        customItemData.CustomDataFloats.Add(stat->MaxStatusValuesField()()[EPrimalCharacterStatusValue::Weight]);
        customItemData.CustomDataFloats.Add(stat->MaxStatusValuesField()()[EPrimalCharacterStatusValue::MeleeDamageMultiplier]);
        customItemData.CustomDataFloats.Add(stat->MaxStatusValuesField()()[EPrimalCharacterStatusValue::SpeedMultiplier]);
        customItemData.CustomDataFloats.Add(stat->MaxStatusValuesField()()[EPrimalCharacterStatusValue::TemperatureFortitude]);
        customItemData.CustomDataFloats.Add(stat->MaxStatusValuesField()()[EPrimalCharacterStatusValue::CraftingSpeedMultiplier]);
        customItemData.CustomDataFloats.Add(dino->bIsFemale()());
    }

    const double now = ArkApi::GetApiUtils().GetShooterGameMode()->GetWorld()->TimeSecondsField();
    customItemData.CustomDataDoubles.Doubles.Add(now);
    customItemData.CustomDataDoubles.Doubles.Add(dino->BabyNextCuddleTimeField() - now);
    customItemData.CustomDataDoubles.Doubles.Add(dino->NextAllowedMatingTimeField());
    customItemData.CustomDataDoubles.Doubles.Add(static_cast<double>(static_cast<float>(dino->RandomMutationsMaleField())));
    customItemData.CustomDataDoubles.Doubles.Add(static_cast<double>(static_cast<float>(dino->RandomMutationsFemaleField())));
    if (stat)
        customItemData.CustomDataDoubles.Doubles.Add(static_cast<double>(stat->DinoImprintingQualityField()));

    FString sNeutered;
    FString sGender = dino->bIsFemale()() ? FString("FEMALE") : FString("Male");
    if (dino->bNeutered()())
        sNeutered = FString("NEUTERED");

    FString color_indices;
    dino->GetColorSetInidcesAsString(&color_indices);
    customItemData.CustomDataStrings.Add(dinoData.DinoNameInMap);
    customItemData.CustomDataStrings.Add(dinoData.DinoName);
    customItemData.CustomDataStrings.Add(color_indices);
    customItemData.CustomDataStrings.Add(sNeutered);
    customItemData.CustomDataStrings.Add(sGender);
    customItemData.CustomDataClasses.Add(dinoData.DinoClass);

    FCustomItemByteArray dinoBytes;
    dinoBytes.Bytes = dinoData.DinoData;
    customItemData.CustomDataBytes.ByteArrays.Add(dinoBytes);
    if (saddle) {
        FCustomItemByteArray saddleBytes;
        saddle->GetItemBytes(&saddleBytes.Bytes);
        customItemData.CustomDataBytes.ByteArrays.Add(saddleBytes);
    }

    return customItemData;
}

UPrimalItem* AddCryopodToInventory(AShooterPlayerController* controller,
                                   UClass* cryoClass,
                                   const FCustomItemData& customData,
                                   UPrimalItem* orphanItem) {
    if (!controller || !cryoClass) return nullptr;

    UPrimalInventoryComponent* inv = controller->GetPlayerInventoryComponent();
    if (!inv) return nullptr;

    if (orphanItem) {
        UPrimalItem* added = inv->AddItemObject(orphanItem);
        if (added) return added;
    }

    UPrimalItem* direct = UPrimalItem::AddNewItem(
        TSubclassOf<UPrimalItem>(cryoClass),
        inv,
        /*bEquipItem=*/false,
        /*bDontStack=*/false,
        /*ItemQuality=*/0.0f,
        /*bForceNoBlueprint=*/false,
        /*ItemQuantity=*/1,
        /*bForceBlueprint=*/false,
        /*MaxItemDifficultyClamp=*/0.0f,
        /*CreateOnClient=*/false,
        TSubclassOf<UPrimalItem>(),
        /*MinRandomQuality=*/0.0f,
        /*clampStats=*/false,
        /*bIgnoreAbsoluteMaxInventory=*/true);
    if (!direct) return nullptr;

    direct->SetCustomItemData(const_cast<FCustomItemData*>(&customData));
    direct->UpdatedItem(true);
    return direct;
}

bool GiveCryopod(AShooterPlayerController* controller,
                 APrimalDinoCharacter* dino,
                 UPrimalItem* saddle) {
    if (!controller || !dino)
        return false;

    const auto& cfg = CustomShop::ShopConfig::Get();
    std::string cryoPath = cfg.CryoItemPath();
    if (cryoPath.empty())
        cryoPath = kDefaultCryoBp;
    cryoPath = NormalizeBlueprintPath(cryoPath);

    FString fcryo(cryoPath.c_str());
    UClass* cryoClass = UVictoryCore::BPLoadClass(&fcryo);
    if (!cryoClass) {
        Log::GetLog()->warn("ShopCryoDino: failed to load cryopod class '{}'", cryoPath);
        return false;
    }

    UPrimalItem* item = UPrimalItem::AddNewItem(
        cryoClass, nullptr, false, false, 0.0f, false, 0, false, 0.0f,
        false, nullptr, 0.0f, false, false);
    if (!item) {
        Log::GetLog()->warn("ShopCryoDino: failed to create cryopod item");
        return false;
    }

    if (cfg.CryoLimitedTime())
        item->AddItemDurability((item->ItemDurabilityField() - 3600) * -1);

    FCustomItemData customData = BuildCryoCustomData(dino, saddle);
    item->SetCustomItemData(&customData);
    item->UpdatedItem(true);

    UPrimalItem* added = AddCryopodToInventory(controller, cryoClass, customData, item);
    if (!added) {
        Log::GetLog()->warn("ShopCryoDino: inventory full or failed to add cryopod");
        return false;
    }

    dino->Destroy(true, false);
    return true;
}

} // anonymous namespace

namespace CustomShop {

bool DeliverDino(AShooterPlayerController* controller,
                 const nlohmann::json& entry) {
    if (!controller)
        return false;

    const std::string blueprint = NormalizeBlueprintPath(entry.value("Blueprint", ""));
    if (blueprint.empty())
        return false;

    const int level = entry.value("Level", 150);
    const bool force_tame = entry.value("ForceTame", true);
    const bool neutered = entry.value("Neutered", false);
    const std::string gender = entry.value("Gender", "");
    const std::string saddle_bp = entry.value("SaddleBlueprint", "");

    FString fbp(blueprint.c_str());
    APrimalDinoCharacter* dino = ArkApi::GetApiUtils().SpawnDino(
        controller, fbp, nullptr, level, force_tame, neutered);
    if (!dino) {
        Log::GetLog()->warn("ShopCryoDino: failed to spawn '{}'", blueprint);
        NotifyPlayer(controller, FColorList::Red,
                     "Falha ao spawnar o dino. Verifique o blueprint no config.");
        return false;
    }

    ApplyGender(dino, gender);

    if (ShouldUseCryopod(entry)) {
        Log::GetLog()->info(
            "ShopCryoDino: cryo mode for '{}' (DeliverDinosInCryopods={})",
            blueprint, CustomShop::ShopConfig::Get().DeliverDinosInCryopods());

        UPrimalItem* saddle = CreateSaddleItem(saddle_bp);
        const bool ok = GiveCryopod(controller, dino, saddle);
        if (ok) {
            Log::GetLog()->info("ShopCryoDino: delivered '{}' in cryopod", blueprint);
            NotifyPlayer(controller, FColorList::Green,
                         "Dino entregue em cryopod no seu inventario.");
            return true;
        }

        Log::GetLog()->warn(
            "ShopCryoDino: cryopod failed for '{}' — dino permanece no chao como fallback",
            blueprint);
        NotifyPlayer(controller, FColorList::Yellow,
                     "Cryopod falhou (inventario cheio?). O dino foi spawnado ao seu lado.");
        return true;
    }

    Log::GetLog()->info("ShopCryoDino: spawned '{}' near player", blueprint);
    NotifyPlayer(controller, FColorList::Green, "Dino spawnado ao seu lado.");
    return true;
}

} // namespace CustomShop
