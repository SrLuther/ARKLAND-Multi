#include "pch.h"
#include "DinoDeliver.h"
#include "DinoConfig.h"

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

void ApplyGender(APrimalDinoCharacter* dino, const std::string& gender) {
    if (!dino || gender.empty() || !dino->bUsesGender()())
        return;
    if (gender == "male" || gender == "Male")
        dino->bIsFemale() = false;
    else if (gender == "female" || gender == "Female")
        dino->bIsFemale() = true;
}

void ApplyColors(APrimalDinoCharacter* dino, const nlohmann::json& colors_json) {
    if (!dino || !colors_json.is_array() || colors_json.size() != 6)
        return;
    char* indices = dino->ColorSetIndicesField()();
    if (!indices)
        return;
    int c0 = 0, c1 = 0, c2 = 0, c3 = 0, c4 = 0, c5 = 0;
    for (size_t i = 0; i < 6; ++i) {
        const int v = colors_json[i].get<int>();
        indices[static_cast<int>(i)] = static_cast<char>(v);
        switch (i) {
            case 0: c0 = v; break;
            case 1: c1 = v; break;
            case 2: c2 = v; break;
            case 3: c3 = v; break;
            case 4: c4 = v; break;
            case 5: c5 = v; break;
            default: break;
        }
    }
    dino->MulticastUpdateAllColorSets_Implementation(c0, c1, c2, c3, c4, c5);
    dino->RefreshColorization(true);
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
        false, false, 0.0f, false, 1, false, 0.0f,
        false, TSubclassOf<UPrimalItem>(), 0.0f, false, true);
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

    const auto& cfg = CustomDinoDeliver::DinoConfig::Get();
    std::string cryoPath = cfg.CryoItemPath();
    if (cryoPath.empty())
        cryoPath = kDefaultCryoBp;
    cryoPath = NormalizeBlueprintPath(cryoPath);

    FString fcryo(cryoPath.c_str());
    UClass* cryoClass = UVictoryCore::BPLoadClass(&fcryo);
    if (!cryoClass) {
        Log::GetLog()->warn("DinoDeliver: failed to load cryopod class '{}'", cryoPath);
        return false;
    }

    UPrimalItem* item = UPrimalItem::AddNewItem(
        cryoClass, nullptr, false, false, 0.0f, false, 0, false, 0.0f,
        false, nullptr, 0.0f, false, false);
    if (!item) {
        Log::GetLog()->warn("DinoDeliver: failed to create cryopod item");
        return false;
    }

    FCustomItemData customData = BuildCryoCustomData(dino, saddle);
    item->SetCustomItemData(&customData);
    item->UpdatedItem(true);

    UPrimalItem* added = AddCryopodToInventory(controller, cryoClass, customData, item);
    if (!added) {
        Log::GetLog()->warn("DinoDeliver: inventory full or failed to add cryopod");
        return false;
    }

    dino->Destroy(true, false);
    return true;
}

} // anonymous namespace

namespace CustomDinoDeliver {

bool DeliverCustomDino(AShooterPlayerController* controller,
                       const nlohmann::json& payload) {
    if (!controller)
        return false;

    const std::string blueprint =
        NormalizeBlueprintPath(payload.value("species_blueprint", ""));
    if (blueprint.empty()) {
        Log::GetLog()->warn("DinoDeliver: empty species_blueprint");
        return false;
    }

    const int level = payload.value("level", 150);
    const bool force_tame = payload.value("force_tame", true);
    const bool neutered = payload.value("neutered", false);
    const std::string gender = payload.value("gender", "female");
    const std::string deliver_as = payload.value("deliver_as", "cryopod");
    const std::string saddle_bp = payload.value("saddle_blueprint", "");
    const std::string display = payload.value("species_display_name", "dino");

    FString fbp(blueprint.c_str());
    APrimalDinoCharacter* dino = ArkApi::GetApiUtils().SpawnDino(
        controller, fbp, nullptr, level, force_tame, neutered);
    if (!dino) {
        Log::GetLog()->warn("DinoDeliver: failed to spawn '{}'", blueprint);
        NotifyPlayer(controller, FColorList::Red,
                     "Falha ao spawnar o dino customizado. Contate um admin.");
        return false;
    }

    ApplyGender(dino, gender);
    if (payload.contains("colors"))
        ApplyColors(dino, payload["colors"]);

    const std::string custom_name = payload.value("custom_name", "");
    if (!custom_name.empty()) {
        FString fname(custom_name.c_str());
        dino->TamedNameField() = fname;
    }

    if (deliver_as == "cryopod") {
        UPrimalItem* saddle = CreateSaddleItem(saddle_bp);
        if (GiveCryopod(controller, dino, saddle)) {
            Log::GetLog()->info("DinoDeliver: '{}' delivered in cryopod", display);
            NotifyPlayer(controller, FColorList::Green,
                         "Dino customizado entregue em cryopod no seu inventario.");
            return true;
        }

        if (DinoConfig::Get().GroundFallbackOnFullInventory()) {
            Log::GetLog()->warn(
                "DinoDeliver: cryopod failed for '{}' — ground fallback", display);
            NotifyPlayer(controller, FColorList::Yellow,
                         "Cryopod falhou (inventario cheio?). O dino foi spawnado ao seu lado.");
            return true;
        }

        NotifyPlayer(controller, FColorList::Red,
                     "Falha ao entregar cryopod. Inventario cheio.");
        dino->Destroy(true, false);
        return false;
    }

    Log::GetLog()->info("DinoDeliver: '{}' spawned near player", display);
    NotifyPlayer(controller, FColorList::Green, "Dino customizado spawnado ao seu lado.");
    return true;
}

} // namespace CustomDinoDeliver
