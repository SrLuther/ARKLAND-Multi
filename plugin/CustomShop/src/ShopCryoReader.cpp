#include "pch.h"
#include "ShopCryoReader.h"
#include "ShopConfig.h"

#include <cmath>

namespace {

constexpr const char* kDefaultCryoBp =
    "Blueprint'/Game/Extinction/CoreBlueprints/Weapons/"
    "PrimalItem_WeaponEmptyCryopod.PrimalItem_WeaponEmptyCryopod'";

bool FloatAt(const TArray<float>& arr, int idx, float& out) {
    if (idx < 0 || idx >= arr.Num()) return false;
    out = arr[idx];
    return true;
}

double DoubleAt(const TArray<double>& arr, int idx, double& out) {
    if (idx < 0 || idx >= arr.Num()) return false;
    out = arr[idx];
    return true;
}

std::string ClassPath(UClass* cls) {
    if (!cls) return "";
    FString class_name;
    cls->GetFullName(&class_name, nullptr);
    return class_name.ToString();
}

const FName& DinoCustomDataName() {
    static const FName kName("Dino", EFindName::FNAME_Find);
    return kName;
}

UWorld* GameWorld() {
    AShooterGameMode* gm = ArkApi::GetApiUtils().GetShooterGameMode();
    return gm ? gm->GetWorld() : nullptr;
}

void EnsureItemInitialized(UPrimalItem* item) {
    if (!item) return;
    UWorld* world = GameWorld();
    if (!world) return;
    item->InitializeItem(true, world);
    item->BPPostInitializeItem(world);
    item->InventoryLoadedFromSaveGame();
}

bool IsVanillaEmptyCryopodClass(UPrimalItem* item) {
    if (!item) return false;
    UClass* cls = item->ClassField();
    if (!cls) return false;
    FString class_name;
    cls->GetFullName(&class_name, nullptr);
    const std::string name = class_name.ToString();
    return name.find("PrimalItem_WeaponEmptyCryopod") != std::string::npos;
}

bool CustomDataLooksLikeDino(const FCustomItemData& data) {
    if (data.CustomDataFloats.Num() >= 25) return true;
    if (data.CustomDataClasses.Num() >= 1 && data.CustomDataStrings.Num() >= 1) return true;
    if (data.CustomDataBytes.ByteArrays.Num() >= 1
        && data.CustomDataBytes.ByteArrays[0].Bytes.Num() > 32)
        return true;
    return false;
}

bool CustomDataNameIsDino(const FCustomItemData& data) {
    return data.CustomDataName == DinoCustomDataName();
}

bool PickDinoCustomDataFromArray(const TArray<FCustomItemData>& all, FCustomItemData& out) {
    for (int i = 0; i < all.Num(); ++i) {
        const FCustomItemData& entry = all[i];
        if (CustomDataNameIsDino(entry) && CustomDataLooksLikeDino(entry)) {
            out = entry;
            return true;
        }
    }
    for (int i = 0; i < all.Num(); ++i) {
        const FCustomItemData& entry = all[i];
        if (CustomDataLooksLikeDino(entry)) {
            out = entry;
            return true;
        }
    }
    return false;
}

bool TryReadDinoCustomData(UPrimalItem* item, FCustomItemData& out) {
    if (!item) return false;
    if (item->GetCustomItemData(DinoCustomDataName(), &out) && CustomDataLooksLikeDino(out))
        return true;
    static const FName kDinoAdd("Dino", EFindName::FNAME_Add);
    if (item->GetCustomItemData(kDinoAdd, &out) && CustomDataLooksLikeDino(out))
        return true;
    return PickDinoCustomDataFromArray(item->CustomItemDatasField(), out);
}

std::string ShortSpecies(const std::string& bp) {
    const size_t dot = bp.rfind('.');
    if (dot != std::string::npos && dot + 1 < bp.size())
        return bp.substr(dot + 1);
    return bp.size() > 32 ? bp.substr(0, 32) : bp;
}

bool TryGetCryoCustomDataFromItem(UPrimalItem* item, FCustomItemData& out);

bool CollectCryoCustomDataBlob(UPrimalItem* item, FCustomItemData& out) {
    if (!item) return false;
    if (TryGetCryoCustomDataFromItem(item, out))
        return true;

    FCustomItemByteArray bytes;
    item->GetItemBytes(&bytes.Bytes);
    if (bytes.Bytes.Num() <= 0)
        return false;

    UPrimalItem* clone = UPrimalItem::CreateFromBytes(&bytes.Bytes);
    if (!clone)
        return false;

    EnsureItemInitialized(clone);
    if (TryReadDinoCustomData(clone, out))
        return true;

    const TArray<FCustomItemData>& all = clone->CustomItemDatasField();
    for (int i = 0; i < all.Num(); ++i) {
        const FCustomItemData& entry = all[i];
        if (entry.CustomDataBytes.ByteArrays.Num() >= 1
            && entry.CustomDataBytes.ByteArrays[0].Bytes.Num() > 32) {
            out = entry;
            return true;
        }
    }
    return false;
}

bool FillMetadataFromDino(APrimalDinoCharacter* dino, CustomShop::CryoParsedMetadata& out) {
    if (!dino) return false;

    FARKDinoData dinoData;
    dino->GetDinoData(&dinoData);
    if (dinoData.DinoClass)
        out.species_blueprint = ClassPath(dinoData.DinoClass);
    out.name_map = dinoData.DinoNameInMap.ToString();
    out.name_breeder = dinoData.DinoName.ToString();
    out.is_female = dino->bIsFemale()();
    out.sex = out.is_female ? "female" : "male";
    out.is_neutered = dino->bNeutered()();
    out.mutations_male = dino->RandomMutationsMaleField();
    out.mutations_female = dino->RandomMutationsFemaleField();

    if (UPrimalCharacterStatusComponent* stat = dino->MyCharacterStatusComponentField()) {
        out.imprint_pct = stat->DinoImprintingQualityField();
        out.health.value = stat->MaxStatusValuesField()()[EPrimalCharacterStatusValue::Health];
        out.stamina.value = stat->MaxStatusValuesField()()[EPrimalCharacterStatusValue::Stamina];
        out.oxygen.value = stat->MaxStatusValuesField()()[EPrimalCharacterStatusValue::Oxygen];
        out.food.value = stat->MaxStatusValuesField()()[EPrimalCharacterStatusValue::Food];
        out.weight.value = stat->MaxStatusValuesField()()[EPrimalCharacterStatusValue::Weight];
        out.melee.value = stat->MaxStatusValuesField()()[EPrimalCharacterStatusValue::MeleeDamageMultiplier];
        out.speed.value = stat->MaxStatusValuesField()()[EPrimalCharacterStatusValue::SpeedMultiplier];

        auto fill_pts = [&](CustomShop::CryoParsedMetadata::StatVal& slot,
                            EPrimalCharacterStatusValue::Type t) {
            const int base = stat->GetLevelUpPoints(t, false);
            const int added = stat->GetLevelUpPoints(t, true);
            slot.points_base = base;
            slot.points_added = added;
        };
        fill_pts(out.health, EPrimalCharacterStatusValue::Health);
        fill_pts(out.stamina, EPrimalCharacterStatusValue::Stamina);
        fill_pts(out.oxygen, EPrimalCharacterStatusValue::Oxygen);
        fill_pts(out.food, EPrimalCharacterStatusValue::Food);
        fill_pts(out.weight, EPrimalCharacterStatusValue::Weight);
        fill_pts(out.melee, EPrimalCharacterStatusValue::MeleeDamageMultiplier);
        fill_pts(out.speed, EPrimalCharacterStatusValue::SpeedMultiplier);

        out.dino_level = stat->GetBaseLevelFromLevelUpPoints(true);
    }
    return true;
}

void CopyStatPoints(const CustomShop::CryoParsedMetadata& src, CustomShop::CryoParsedMetadata& dst) {
    dst.health.points_base = src.health.points_base;
    dst.health.points_added = src.health.points_added;
    dst.stamina.points_base = src.stamina.points_base;
    dst.stamina.points_added = src.stamina.points_added;
    dst.oxygen.points_base = src.oxygen.points_base;
    dst.oxygen.points_added = src.oxygen.points_added;
    dst.food.points_base = src.food.points_base;
    dst.food.points_added = src.food.points_added;
    dst.weight.points_base = src.weight.points_base;
    dst.weight.points_added = src.weight.points_added;
    dst.melee.points_base = src.melee.points_base;
    dst.melee.points_added = src.melee.points_added;
    dst.speed.points_base = src.speed.points_base;
    dst.speed.points_added = src.speed.points_added;
    if (src.dino_level > 0)
        dst.dino_level = src.dino_level;
}

bool TryParseViaSpawnProbe(UPrimalItem* item, AShooterPlayerController* player,
                           CustomShop::CryoParsedMetadata& out);

bool TryFillStatPointsViaSpawnProbe(UPrimalItem* item, AShooterPlayerController* player,
                                    CustomShop::CryoParsedMetadata& out) {
    CustomShop::CryoParsedMetadata probe;
    if (!TryParseViaSpawnProbe(item, player, probe))
        return false;
    CopyStatPoints(probe, out);
    return true;
}

bool TryParseViaSpawnProbe(UPrimalItem* item, AShooterPlayerController* player,
                           CustomShop::CryoParsedMetadata& out) {
    FCustomItemData data;
    if (!CollectCryoCustomDataBlob(item, data))
        return false;
    if (data.CustomDataClasses.Num() < 1
        || data.CustomDataBytes.ByteArrays.Num() < 1
        || data.CustomDataBytes.ByteArrays[0].Bytes.Num() <= 32)
        return false;

    UWorld* world = GameWorld();
    if (!world)
        return false;

    FARKDinoData dinoData;
    dinoData.DinoClass = data.CustomDataClasses[0];
    dinoData.DinoData = data.CustomDataBytes.ByteArrays[0].Bytes;
    if (data.CustomDataStrings.Num() >= 1)
        dinoData.DinoNameInMap = data.CustomDataStrings[0];
    if (data.CustomDataStrings.Num() >= 2)
        dinoData.DinoName = data.CustomDataStrings[1];

    FVector spawn_loc = FVector(0.f, 0.f, -50000.f);
    int team_id = 0;
    if (player)
        team_id = player->TargetingTeamField();

    FRotator spawn_rot = FRotator(0.f, 0.f, 0.f);
    bool duped = false;
    APrimalDinoCharacter* spawned = APrimalDinoCharacter::SpawnFromDinoDataEx(
        &dinoData, world, &spawn_loc, &spawn_rot, &duped, team_id, false, player, true);
    if (!spawned) {
        Log::GetLog()->warn("ShopCryoReader: SpawnFromDinoDataEx falhou species={}",
                            ClassPath(dinoData.DinoClass));
        return false;
    }

    out = CustomShop::CryoParsedMetadata{};
    out.has_dino_data = true;
    out.extraction_method = "spawn_probe";
    const bool ok = FillMetadataFromDino(spawned, out);
    spawned->Destroy(true, false);
    if (ok) {
        Log::GetLog()->info("ShopCryoReader: metadata via spawn probe species={} imprint={:.2f}",
                            ShortSpecies(out.species_blueprint), out.imprint_pct);
    }
    return ok;
}

bool TryGetCryoCustomDataFromItem(UPrimalItem* item, FCustomItemData& out) {
    if (!item) return false;

    EnsureItemInitialized(item);
    if (TryReadDinoCustomData(item, out))
        return true;

    FCustomItemByteArray bytes;
    item->GetItemBytes(&bytes.Bytes);
    if (bytes.Bytes.Num() <= 0)
        return false;

    UPrimalItem* clone = UPrimalItem::CreateFromBytes(&bytes.Bytes);
    if (!clone)
        return false;

    EnsureItemInitialized(clone);
    if (TryReadDinoCustomData(clone, out))
        return true;

    Log::GetLog()->warn(
        "ShopCryoReader: falha ao ler cryo class={} customDatas={} bytes={}",
        ClassPath(item->ClassField()),
        item->CustomItemDatasField().Num(),
        bytes.Bytes.Num());
    return false;
}

} // anonymous namespace

namespace CustomShop {

constexpr float kStandardCryoDurability = 3600.f;

bool CryopodHasTimer(UPrimalItem* item) {
    if (!item) return false;
    const float max_dur = item->ItemDurabilityField();
    if (max_dur <= 0.f) return false;
    const float saved = item->SavedDurabilityField();
    // Cryo capturada: carga em segundos em SavedDurability mesmo com teto vanilla ~3600.
    if (saved > kStandardCryoDurability + 1.f) return true;
    // Cryo sem timer de decay: teto ~3600s (1h) e carga 100%.
    if (std::abs(max_dur - kStandardCryoDurability) <= 0.5f)
        return item->BPGetItemDurabilityPercentage() < 0.999f;
    // Cryo capturada: teto em segundos (ex. ~30 dias) != 3600.
    return true;
}

float GetCryopodRemainingDecaySeconds(UPrimalItem* item) {
    if (!item) return 0.f;
    EnsureItemInitialized(item);

    const float max_dur = item->ItemDurabilityField();
    if (max_dur <= 0.f) return 0.f;
    const float saved = item->SavedDurabilityField();
    const float pct = item->BPGetItemDurabilityPercentage();

    // Cryo capturada com cryogun: UI mostra "29d 23h" em SavedDurability (segundos),
    // enquanto ItemDurability pode continuar ~3600 — ignorar pct nesse caso.
    if (saved > kStandardCryoDurability + 1.f)
        return saved;

    if (std::abs(max_dur - kStandardCryoDurability) <= 0.5f) {
        if (pct >= 0.999f) return -1.f;
        const float via_pct = max_dur * pct;
        if (saved > 0.f)
            return std::max(via_pct, saved);
        return via_pct;
    }

    // Teto estendido (cryogun / CryoLimitedTime / loja).
    const float via_pct = max_dur * pct;
    if (saved > kStandardCryoDurability + 1.f) {
        if (saved <= max_dur + 1.f)
            return std::max(via_pct, saved);
        return saved;
    }
    if (via_pct > kStandardCryoDurability + 1.f)
        return via_pct;
    // Cryogun: segundos restantes em ItemDurability; saved costuma ser lixo (~1).
    constexpr float kOneDaySeconds = 86400.f;
    if (max_dur > kOneDaySeconds && pct < 0.01f)
        return max_dur;
    if (saved > 0.f)
        return std::max(via_pct, saved);
    return via_pct;
}

float GetCryopodRemainingDays(UPrimalItem* item) {
    const float seconds = GetCryopodRemainingDecaySeconds(item);
    if (seconds < 0.f) return -1.f;
    return seconds / 86400.f;
}

bool CryopodMeetsMarketTimerRequirement(UPrimalItem* item, float min_days) {
    if (min_days <= 0.f) return true;
    const float seconds = GetCryopodRemainingDecaySeconds(item);
    if (seconds < 0.f) return true;
    // Mesma regra do chat: floor(dias) >= minimo (evita 19.9d exibido como 19).
    return std::floor(seconds / 86400.f + 1e-4f) >= static_cast<double>(min_days);
}

void ApplyCryoTimerFieldsToMetadata(UPrimalItem* item, CryoParsedMetadata& out) {
    out.timer_remaining_days = GetCryopodRemainingDays(item);
    out.had_timer = out.timer_remaining_days >= 0.f;
}

bool ValidateMarketCryopodItem(UPrimalItem* item, std::string* error,
                             AShooterPlayerController* context_player) {
    if (!item) {
        if (error) *error = "item nulo";
        return false;
    }
    CryoParsedMetadata meta;
    if (!ParseCryopodItem(item, meta, error, context_player))
        return false;
    if (!meta.has_dino_data) {
        if (error) *error = "cryopod vazia (sem dino)";
        return false;
    }
    return true;
}

bool RefreshCryopodEncapsulationWorldTime(UPrimalItem* item) {
    if (!item) return false;
    UWorld* world = GameWorld();
    if (!world) return false;

    FCustomItemData data;
    if (!TryReadDinoCustomData(item, data))
        return false;
    if (data.CustomDataDoubles.Doubles.Num() < 1)
        return false;

    const double now = static_cast<double>(world->TimeSecondsField());
    data.CustomDataDoubles.Doubles[0] = now;
    item->SetCustomItemData(&data);
    return true;
}

bool PrepareMarketCryopodForDelivery(UPrimalItem* item,
                                     AShooterPlayerController* context_player,
                                     std::string* error) {
    if (!item) {
        if (error) *error = "item nulo";
        return false;
    }

    // Ordem importa: nao chamar InventoryLoadedFromSaveGame antes de normalizar
    // timer/carga — o jogo usa CustomDataDoubles[0] (TimeSeconds do mapa de
    // encapsulamento) vs TimeSeconds local para calcular decay.
    const bool stripped = StripCryopodTimer(item);
    const bool time_refreshed = RefreshCryopodEncapsulationWorldTime(item);

    float max_dur = item->ItemDurabilityField();
    if (max_dur <= 0.f || max_dur > kStandardCryoDurability + 1.f)
        item->ItemDurabilityField() = kStandardCryoDurability;

    max_dur = item->ItemDurabilityField();
    const float pct = item->BPGetItemDurabilityPercentage();
    if (item->SavedDurabilityField() <= 0.f || pct < 0.999f
        || item->SavedDurabilityField() > max_dur + 1.f) {
        item->SavedDurabilityField() = max_dur;
    }

    item->UpdatedItem(true);

    if (!ValidateMarketCryopodItem(item, error, context_player)) {
        Log::GetLog()->warn(
            "ShopCryoReader: PrepareMarketCryopodForDelivery falhou max={:.0f} saved={:.0f} pct={:.4f} stripped={} time_refreshed={} err={}",
            item->ItemDurabilityField(),
            item->SavedDurabilityField(),
            item->BPGetItemDurabilityPercentage(),
            stripped ? 1 : 0,
            time_refreshed ? 1 : 0,
            error ? *error : std::string());
        return false;
    }

    Log::GetLog()->info(
        "ShopCryoReader: cryo pronta para entrega max={:.0f} saved={:.0f} stripped={} time_refreshed={}",
        item->ItemDurabilityField(),
        item->SavedDurabilityField(),
        stripped ? 1 : 0,
        time_refreshed ? 1 : 0);
    return true;
}

bool StripCryopodTimer(UPrimalItem* item) {
    if (!item || !CryopodHasTimer(item)) return false;

    float max_dur = item->ItemDurabilityField();

    // Inverso de ShopCryoDino::AddItemDurability((max - 3600) * -1).
    if (std::abs(max_dur - kStandardCryoDurability) > 0.01f)
        item->AddItemDurability(kStandardCryoDurability - max_dur);

    max_dur = item->ItemDurabilityField();
    if (std::abs(max_dur - kStandardCryoDurability) > 0.01f)
        item->ItemDurabilityField() = kStandardCryoDurability;

    item->SavedDurabilityField() = item->ItemDurabilityField();
    item->UpdatedItem(true);

    if (!CryopodHasTimer(item))
        return true;

    Log::GetLog()->warn(
        "ShopCryoReader: StripCryopodTimer retry max={} saved={} pct={}",
        item->ItemDurabilityField(),
        item->SavedDurabilityField(),
        item->BPGetItemDurabilityPercentage());

    item->ItemDurabilityField() = kStandardCryoDurability;
    item->SavedDurabilityField() = kStandardCryoDurability;
    item->UpdatedItem(true);
    return !CryopodHasTimer(item);
}

bool IsOfficialCryopodItem(UPrimalItem* item) {
    if (!item) return false;
    if (IsVanillaEmptyCryopodClass(item)) return true;
    FCustomItemData tmp;
    return TryGetCryoCustomDataFromItem(item, tmp);
}

UPrimalItem* FindCryopodInInventory(AShooterPlayerController* controller, int slot_index) {
    if (!controller) return nullptr;
    UPrimalInventoryComponent* inv = controller->GetPlayerInventoryComponent();
    if (!inv) return nullptr;

    auto is_parseable = [controller](UPrimalItem* item) -> bool {
        if (!item || !IsVanillaEmptyCryopodClass(item)) return false;
        CryoParsedMetadata meta;
        return ParseCryopodItem(item, meta, nullptr, controller);
    };

    if (slot_index >= 0) {
        TArray<UPrimalItem*> items = inv->InventoryItemsField();
        if (slot_index < items.Num() && is_parseable(items[slot_index]))
            return items[slot_index];
        return nullptr;
    }

    UPrimalItem* equipped = inv->GetEquippedItemOfType(EPrimalEquipmentType::Weapon);
    if (is_parseable(equipped)) return equipped;

    TArray<UPrimalItem*> items = inv->InventoryItemsField();
    for (int i = 0; i < items.Num(); ++i) {
        if (is_parseable(items[i])) return items[i];
    }
    return nullptr;
}

bool CryoMetadataMatches(const CryoParsedMetadata& a, const CryoParsedMetadata& b) {
    if (a.name_map != b.name_map) return false;
    if (a.species_blueprint != b.species_blueprint) return false;
    if (std::abs(a.imprint_pct - b.imprint_pct) > 0.01f) return false;
    if (a.mutations_male != b.mutations_male) return false;
    if (a.mutations_female != b.mutations_female) return false;
    return true;
}

UPrimalItem* FindCryopodMatchingMeta(
    AShooterPlayerController* controller, const CryoParsedMetadata& expected) {
    if (!controller) return nullptr;
    UPrimalInventoryComponent* inv = controller->GetPlayerInventoryComponent();
    if (!inv) return nullptr;

    auto try_item = [&](UPrimalItem* item) -> UPrimalItem* {
        if (!item) return nullptr;
        CryoParsedMetadata meta;
        if (!ParseCryopodItem(item, meta, nullptr, controller)) return nullptr;
        return CryoMetadataMatches(meta, expected) ? item : nullptr;
    };

    if (UPrimalItem* hit = try_item(inv->GetEquippedItemOfType(EPrimalEquipmentType::Weapon)))
        return hit;

    TArray<UPrimalItem*> items = inv->InventoryItemsField();
    for (int i = 0; i < items.Num(); ++i) {
        if (UPrimalItem* hit = try_item(items[i]))
            return hit;
    }
    return nullptr;
}

bool ParseCryopodItem(UPrimalItem* item, CryoParsedMetadata& out, std::string* error,
                      AShooterPlayerController* context_player) {
    if (!item) {
        if (error) *error = "item nulo";
        return false;
    }
    if (!IsVanillaEmptyCryopodClass(item)) {
        if (error) *error = "nao e cryopod oficial";
        return false;
    }

    FCustomItemData custom_data;
    const bool have_custom = TryGetCryoCustomDataFromItem(item, custom_data);

    if (!have_custom) {
        if (TryParseViaSpawnProbe(item, context_player, out)) {
            ApplyCryoTimerFieldsToMetadata(item, out);
            return true;
        }
        if (CryopodHasTimer(item)) {
            if (error) *error = "cryo com dino mas leitura falhou";
        } else if (error) {
            *error = "sem dino ou formato incompativeis";
        }
        return false;
    }

    out = CryoParsedMetadata{};
    out.has_dino_data = true;

    if (custom_data.CustomDataStrings.Num() >= 1)
        out.name_map = custom_data.CustomDataStrings[0].ToString();
    if (custom_data.CustomDataStrings.Num() >= 2)
        out.name_breeder = custom_data.CustomDataStrings[1].ToString();
    if (custom_data.CustomDataStrings.Num() >= 5) {
        const std::string gender = custom_data.CustomDataStrings[4].ToString();
        out.sex = gender;
        if (gender.find("FEMALE") != std::string::npos) out.is_female = true;
    }
    if (custom_data.CustomDataStrings.Num() >= 4) {
        const std::string neut = custom_data.CustomDataStrings[3].ToString();
        out.is_neutered = neut.find("NEUTERED") != std::string::npos;
    }
    if (custom_data.CustomDataClasses.Num() >= 1)
        out.species_blueprint = ClassPath(custom_data.CustomDataClasses[0]);

    const TArray<float>& floats = custom_data.CustomDataFloats;
    if (floats.Num() >= 25) {
        FloatAt(floats, static_cast<int>(EPrimalCharacterStatusValue::Health) + 12, out.health.value);
        FloatAt(floats, static_cast<int>(EPrimalCharacterStatusValue::Stamina) + 12, out.stamina.value);
        FloatAt(floats, static_cast<int>(EPrimalCharacterStatusValue::Oxygen) + 12, out.oxygen.value);
        FloatAt(floats, static_cast<int>(EPrimalCharacterStatusValue::Food) + 12, out.food.value);
        FloatAt(floats, static_cast<int>(EPrimalCharacterStatusValue::Weight) + 12, out.weight.value);
        FloatAt(floats, static_cast<int>(EPrimalCharacterStatusValue::MeleeDamageMultiplier) + 12, out.melee.value);
        if (out.melee.value <= 0.f)
            FloatAt(floats, static_cast<int>(EPrimalCharacterStatusValue::MeleeDamageMultiplier), out.melee.value);
        FloatAt(floats, static_cast<int>(EPrimalCharacterStatusValue::SpeedMultiplier) + 12, out.speed.value);
        if (out.speed.value <= 0.f)
            FloatAt(floats, static_cast<int>(EPrimalCharacterStatusValue::SpeedMultiplier), out.speed.value);

        float is_female_f = 0.f;
        if (FloatAt(floats, 24, is_female_f))
            out.is_female = is_female_f > 0.5f;
    }

    const TArray<double>& doubles = custom_data.CustomDataDoubles.Doubles;
    double mut_m = 0, mut_f = 0, imprint = 0;
    if (doubles.Num() >= 5) {
        DoubleAt(doubles, 3, mut_m);
        DoubleAt(doubles, 4, mut_f);
        out.mutations_male = static_cast<int>(mut_m);
        out.mutations_female = static_cast<int>(mut_f);
    }
    if (doubles.Num() >= 6)
        DoubleAt(doubles, 5, imprint);
    out.imprint_pct = static_cast<float>(imprint);

    ApplyCryoTimerFieldsToMetadata(item, out);

    if (TryFillStatPointsViaSpawnProbe(item, context_player, out)) {
        if (out.extraction_method.empty() || out.extraction_method == "custom_item_data")
            out.extraction_method = "custom_item_data+spawn_points";
    }

    return true;
}

nlohmann::json CryoMetadataToJson(const CryoParsedMetadata& meta) {
    auto stat_json = [](const CryoParsedMetadata::StatVal& s) {
        nlohmann::json j = {{"value", s.value}};
        if (s.points_base >= 0) {
            j["points_base"] = s.points_base;
            j["points"] = s.points_base + (s.points_added >= 0 ? s.points_added : 0);
        }
        if (s.points_added >= 0)
            j["points_added"] = s.points_added;
        return j;
    };
    nlohmann::json j;
    j["species_blueprint"] = meta.species_blueprint;
    j["name_map"] = meta.name_map;
    j["name_breeder"] = meta.name_breeder;
    j["sex"] = meta.is_female ? "female" : "male";
    j["is_female"] = meta.is_female;
    j["is_neutered"] = meta.is_neutered;
    j["imprint_pct"] = meta.imprint_pct;
    j["mutations_male"] = meta.mutations_male;
    j["mutations_female"] = meta.mutations_female;
    j["dino_level"] = meta.dino_level;
    j["stats_max"] = {
        {"health", stat_json(meta.health)},
        {"stamina", stat_json(meta.stamina)},
        {"oxygen", stat_json(meta.oxygen)},
        {"food", stat_json(meta.food)},
        {"weight", stat_json(meta.weight)},
        {"melee", stat_json(meta.melee)},
        {"speed", stat_json(meta.speed)},
    };
    j["extraction_method"] = meta.extraction_method.empty() ? "custom_item_data" : meta.extraction_method;
    if (meta.timer_remaining_days >= 0.f)
        j["cryo_timer_days_remaining"] = meta.timer_remaining_days;
    else
        j["cryo_timer_permanent"] = true;
    return j;
}

namespace {

void DiagnoseSingleCryo(UPrimalItem* item, AShooterPlayerController* controller, CryoDebugEntry& e) {
    if (!item) return;

    e.class_name = ClassPath(item->ClassField());
    e.vanilla_class = IsVanillaEmptyCryopodClass(item);
    e.has_timer = CustomShop::CryopodHasTimer(item);
    e.item_durability = item->ItemDurabilityField();
    e.saved_durability = item->SavedDurabilityField();
    e.durability_pct = item->BPGetItemDurabilityPercentage();
    e.timer_remaining_days = CustomShop::GetCryopodRemainingDays(item);
    e.custom_datas = item->CustomItemDatasField().Num();

    FCustomItemData direct;
    e.get_custom_data =
        item->GetCustomItemData(DinoCustomDataName(), &direct) && CustomDataLooksLikeDino(direct);

    FCustomItemData picked;
    e.array_pick = PickDinoCustomDataFromArray(item->CustomItemDatasField(), picked);

    FCustomItemByteArray bytes;
    item->GetItemBytes(&bytes.Bytes);
    e.blob_bytes = bytes.Bytes.Num();

    UPrimalItem* clone = nullptr;
    if (bytes.Bytes.Num() > 0) {
        clone = UPrimalItem::CreateFromBytes(&bytes.Bytes);
        e.clone_ok = clone != nullptr;
        if (clone) {
            EnsureItemInitialized(clone);
            e.clone_custom_datas = clone->CustomItemDatasField().Num();
            FCustomItemData clone_direct;
            e.clone_get_custom = clone->GetCustomItemData(DinoCustomDataName(), &clone_direct)
                && CustomDataLooksLikeDino(clone_direct);
        }
    }

    FCustomItemData merged;
    if (TryGetCryoCustomDataFromItem(item, merged)) {
        e.try_read_ok = true;
        e.floats = merged.CustomDataFloats.Num();
        e.doubles = merged.CustomDataDoubles.Doubles.Num();
        e.strings = merged.CustomDataStrings.Num();
        e.classes = merged.CustomDataClasses.Num();
    }

    CryoParsedMetadata meta;
    e.parse_ok = ParseCryopodItem(item, meta, &e.parse_error, controller);
    if (e.parse_ok) {
        e.imprint_pct = meta.imprint_pct;
        e.species = meta.species_blueprint;
        e.name_map = meta.name_map;
    } else if (e.try_read_ok) {
        if (merged.CustomDataStrings.Num() >= 1)
            e.name_map = merged.CustomDataStrings[0].ToString();
        if (merged.CustomDataClasses.Num() >= 1)
            e.species = ClassPath(merged.CustomDataClasses[0]);
        if (merged.CustomDataDoubles.Doubles.Num() >= 6) {
            double imprint = 0;
            DoubleAt(merged.CustomDataDoubles.Doubles, 5, imprint);
            e.imprint_pct = static_cast<float>(imprint);
        }
    }
}

} // anonymous namespace

void BuildCryoInventoryDebugReport(AShooterPlayerController* controller, CryoInventoryDebugReport& out) {
    out = CryoInventoryDebugReport{};
    if (!controller) return;

    UPrimalInventoryComponent* inv = controller->GetPlayerInventoryComponent();
    if (!inv) return;

    UPrimalItem* equipped = inv->GetEquippedItemOfType(EPrimalEquipmentType::Weapon);

    auto scan = [&](UPrimalItem* item, int index, bool is_equipped) {
        if (!item || !IsVanillaEmptyCryopodClass(item)) return;
        CryoDebugEntry entry;
        entry.inventory_index = index;
        entry.equipped = is_equipped;
        DiagnoseSingleCryo(item, controller, entry);
        out.entries.push_back(entry);
        ++out.vanilla_cryos;
        if (entry.parse_ok) ++out.parseable;
    };

    scan(equipped, -1, true);

    TArray<UPrimalItem*> items = inv->InventoryItemsField();
    for (int i = 0; i < items.Num(); ++i) {
        if (items[i] == equipped) continue;
        scan(items[i], i, false);
    }
}

void LogCryoInventoryDebugReport(
    const std::string& steam_id, const char* stage, const CryoInventoryDebugReport& report) {
    Log::GetLog()->warn(
        "ShopCryoReader[{}] steam={} vanilla_cryos={} parseable={}",
        stage ? stage : "debug",
        steam_id,
        report.vanilla_cryos,
        report.parseable);

    for (const CryoDebugEntry& e : report.entries) {
        Log::GetLog()->warn(
            "  cryo slot={} eq={} class={} timer={} max={:.0f} saved={:.0f} pct={:.4f} dias={:.1f} "
            "customDatas={} getCustom={} arrayPick={} "
            "floats={} doubles={} strings={} classes={} bytes={} clone={} cloneDatas={} "
            "cloneGet={} tryRead={} parse={} imprint={:.3f} species={} name={} err={}",
            e.inventory_index,
            e.equipped ? 1 : 0,
            e.class_name,
            e.has_timer ? 1 : 0,
            e.item_durability,
            e.saved_durability,
            e.durability_pct,
            e.timer_remaining_days,
            e.custom_datas,
            e.get_custom_data ? 1 : 0,
            e.array_pick ? 1 : 0,
            e.floats,
            e.doubles,
            e.strings,
            e.classes,
            e.blob_bytes,
            e.clone_ok ? 1 : 0,
            e.clone_custom_datas,
            e.clone_get_custom ? 1 : 0,
            e.try_read_ok ? 1 : 0,
            e.parse_ok ? 1 : 0,
            e.imprint_pct,
            ShortSpecies(e.species),
            e.name_map,
            e.parse_error);
    }
}

std::vector<std::string> CryoInventoryDebugChatLines(const CryoInventoryDebugReport& report) {
    std::vector<std::string> lines;
    lines.push_back(
        "[DBG] cryos vanilla=" + std::to_string(report.vanilla_cryos)
        + " parse ok=" + std::to_string(report.parseable));

    int shown = 0;
    for (const CryoDebugEntry& e : report.entries) {
        if (shown >= 3) break;
        const std::string slot = e.equipped ? "equipped" : ("slot" + std::to_string(e.inventory_index));
        lines.push_back(
            "[DBG] " + slot + " timer=" + (e.has_timer ? "1" : "0")
            + " dias=" + (e.timer_remaining_days < 0.f
                ? "perm"
                : std::to_string(static_cast<int>(std::floor(e.timer_remaining_days))))
            + " datas=" + std::to_string(e.custom_datas)
            + " get=" + (e.get_custom_data ? "1" : "0")
            + " arr=" + (e.array_pick ? "1" : "0")
            + " bytes=" + std::to_string(e.blob_bytes)
            + " read=" + (e.try_read_ok ? "1" : "0"));
        if (!e.parse_ok && !e.parse_error.empty()) {
            std::string err = e.parse_error;
            if (err.size() > 48) err.resize(48);
            lines.push_back("[DBG] parse FAIL: " + err);
        } else if (e.parse_ok) {
            lines.push_back(
                "[DBG] OK name=" + (e.name_map.empty() ? "?" : e.name_map)
                + " imprint=" + std::to_string(static_cast<int>(e.imprint_pct * 100)) + "%");
        }
        ++shown;
    }

    if (report.entries.size() > 3) {
        lines.push_back("[DBG] +" + std::to_string(report.entries.size() - 3) + " cryos (ver log servidor)");
    }
    return lines;
}

} // namespace CustomShop
