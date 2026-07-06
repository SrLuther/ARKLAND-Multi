#include "pch.h"
#include "DinoDeliver.h"
#include "DinoConfig.h"

#include <sstream>

namespace {

constexpr const char* kDefaultCryoBp =
    "Blueprint'/Game/Extinction/CoreBlueprints/Weapons/"
    "PrimalItem_WeaponEmptyCryopod.PrimalItem_WeaponEmptyCryopod'";

constexpr int kStatCount = 7;
constexpr float kSpawnExactSearchRadius = 600.0f;

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

UShooterCheatManager* GetPlayerCheatManager(AShooterPlayerController* controller) {
    if (!controller) return nullptr;
    return static_cast<UShooterCheatManager*>(controller->CheatManagerField());
}

int SumStatsJson(const nlohmann::json& stats_json) {
    if (!stats_json.is_array()) return 0;
    int sum = 0;
    for (size_t i = 0; i < stats_json.size() && i < static_cast<size_t>(kStatCount); ++i)
        sum += std::max(0, stats_json[i].get<int>());
    return sum;
}

std::string FormatStatsCsv(const nlohmann::json& stats_json) {
    std::ostringstream oss;
    for (int i = 0; i < 8; ++i) {
        if (i > 0) oss << ',';
        int v = 0;
        if (stats_json.is_array() && i < static_cast<int>(stats_json.size()) && i < kStatCount)
            v = stats_json[i].get<int>();
        oss << std::max(0, v);
    }
    return oss.str();
}

std::string FormatColorsCsv(const nlohmann::json& colors_json) {
    std::ostringstream oss;
    for (int i = 0; i < 6; ++i) {
        if (i > 0) oss << ',';
        int v = 0;
        if (colors_json.is_array() && i < static_cast<int>(colors_json.size()))
            v = colors_json[i].get<int>();
        oss << std::max(0, v);
    }
    return oss.str();
}

int64_t ParseImprinterIdHex(const std::string& hex_str) {
    if (hex_str.empty()) return 0;
    try {
        return std::stoll(hex_str, nullptr, 16);
    } catch (...) {
        return 0;
    }
}

FVector GetActorLocation(AActor* actor) {
    if (!actor) return FVector{0, 0, 0};
    USceneComponent* root = actor->RootComponentField();
    if (!root) return FVector{0, 0, 0};
    return root->RelativeLocationField();
}

APrimalDinoCharacter* FindNearestTamedDino(AShooterPlayerController* controller,
                                           float max_dist) {
    if (!controller) return nullptr;
    AShooterCharacter* pawn = controller->GetPlayerCharacter();
    if (!pawn) return nullptr;

    const FVector player_loc = GetActorLocation(pawn);
    const int team = controller->TargetingTeamField();
    UWorld* world = ArkApi::GetApiUtils().GetWorld();
    if (!world) return nullptr;

    TArray<AActor*> actors;
    UGameplayStatics::GetAllActorsOfClass(
        world,
        APrimalDinoCharacter::GetPrivateStaticClass(),
        &actors);

    APrimalDinoCharacter* best = nullptr;
    const float max_dist_sq = max_dist * max_dist;
    float best_dist_sq = max_dist_sq;

    for (AActor* actor : actors) {
        auto* dino = static_cast<APrimalDinoCharacter*>(actor);
        if (!dino || dino->TamingTeamIDField() != team) continue;
        const FVector loc = GetActorLocation(dino);
        const float dx = loc.X - player_loc.X;
        const float dy = loc.Y - player_loc.Y;
        const float dz = loc.Z - player_loc.Z;
        const float dist_sq = dx * dx + dy * dy + dz * dz;
        if (dist_sq <= best_dist_sq) {
            best_dist_sq = dist_sq;
            best = dino;
        }
    }
    return best;
}

APrimalDinoCharacter* SpawnExactFromPayload(AShooterPlayerController* controller,
                                            const nlohmann::json& payload) {
    if (!controller) return nullptr;

    const std::string blueprint =
        NormalizeBlueprintPath(payload.value("species_blueprint", ""));
    if (blueprint.empty()) return nullptr;

    const nlohmann::json spawn_exact =
        payload.value("spawn_exact", nlohmann::json::object());
    const nlohmann::json wild = spawn_exact.value("wild_stats", nlohmann::json::array());
    const nlohmann::json tamed = spawn_exact.value("tamed_stats", nlohmann::json::array());
    const int base_level = SumStatsJson(wild) + 1;
    const int extra_levels = SumStatsJson(tamed);

    const std::string saddle_bp_raw = payload.value("saddle_blueprint", "");
    const std::string saddle_bp = saddle_bp_raw.empty()
        ? "" : NormalizeBlueprintPath(saddle_bp_raw);
    const float saddle_quality = saddle_bp.empty() ? 0.0f : 0.0f;

    const std::string dino_name = payload.value("custom_name", "");
    const bool neutered = payload.value("neutered", false);
    const nlohmann::json colors = payload.value("colors", nlohmann::json::array());

    float imprint_quality = 0.0f;
    if (spawn_exact.contains("imprint_pct")) {
        imprint_quality = spawn_exact.value("imprint_pct", 0.0f);
        if (imprint_quality > 1.0f) imprint_quality /= 100.0f;
        imprint_quality = std::max(0.0f, std::min(1.0f, imprint_quality));
    }
    const std::string imprinter_name = spawn_exact.value("imprinter_name", "");
    const int imprinter_id = static_cast<int>(
        ParseImprinterIdHex(spawn_exact.value("imprinter_id_hex", "")));

    FString fbp(blueprint.c_str());
    FString fsaddle(saddle_bp.c_str());
    FString fwild(FormatStatsCsv(wild).c_str());
    FString ftamed(FormatStatsCsv(tamed).c_str());
    FString fname(dino_name.c_str());
    FString fempty("");
    FString fimprinter(imprinter_name.c_str());
    FString fcolors(FormatColorsCsv(colors).c_str());

    UShooterCheatManager* cheat = GetPlayerCheatManager(controller);
    if (!cheat)
        cheat = ArkApi::GetApiUtils().GetCheatManager();
    if (!cheat) {
        Log::GetLog()->warn("DinoDeliver: SpawnExact — cheat manager indisponivel");
        return nullptr;
    }

    const bool was_admin = controller->bIsAdmin()();
    if (!was_admin)
        controller->bIsAdmin() = true;

    cheat->SpawnExactDino(
        &fbp,
        &fsaddle,
        saddle_quality,
        base_level,
        extra_levels,
        &fwild,
        &ftamed,
        &fname,
        0,
        neutered ? 1 : 0,
        &fempty,
        &fempty,
        &fimprinter,
        imprinter_id,
        imprint_quality,
        &fcolors,
        0,
        0,
        200.0f,
        0.0f,
        0.0f);

    if (!was_admin)
        controller->bIsAdmin() = false;

    APrimalDinoCharacter* dino =
        FindNearestTamedDino(controller, kSpawnExactSearchRadius);
    if (!dino)
        Log::GetLog()->warn("DinoDeliver: SpawnExact — dino nao encontrado apos spawn");
    return dino;
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

    const nlohmann::json spawn_exact =
        payload.value("spawn_exact", nlohmann::json::object());
    const bool use_spawn_exact = spawn_exact.value("enabled", false);

    APrimalDinoCharacter* dino = nullptr;
    if (use_spawn_exact) {
        dino = SpawnExactFromPayload(controller, payload);
        if (!dino) {
            Log::GetLog()->warn("DinoDeliver: SpawnExact failed for '{}'", blueprint);
            NotifyPlayer(controller, FColorList::Red,
                         "Falha ao spawnar dino (SpawnExact). Contate um admin.");
            return false;
        }
    } else {
        FString fbp(blueprint.c_str());
        dino = ArkApi::GetApiUtils().SpawnDino(
            controller, fbp, nullptr, level, force_tame, neutered);
        if (!dino) {
            Log::GetLog()->warn("DinoDeliver: failed to spawn '{}'", blueprint);
            NotifyPlayer(controller, FColorList::Red,
                         "Falha ao spawnar o dino customizado. Contate um admin.");
            return false;
        }
    }

    ApplyGender(dino, gender);
    if (payload.contains("colors"))
        ApplyColors(dino, payload["colors"]);

    const std::string custom_name = payload.value("custom_name", "");
    if (!custom_name.empty() && !use_spawn_exact) {
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
