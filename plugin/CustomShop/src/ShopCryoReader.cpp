#include "pch.h"
#include "ShopCryoReader.h"
#include "ShopConfig.h"

namespace {

constexpr const char* kDefaultCryoBp =
    "Blueprint'/Game/Extinction/CoreBlueprints/Weapons/"
    "PrimalItem_WeaponEmptyCryopod.PrimalItem_WeaponEmptyCryopod'";

using StatIdx = EPrimalCharacterStatusValue;

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
    return cls->GetFullName();
}

} // anonymous namespace

namespace CustomShop {

bool IsOfficialCryopodItem(UPrimalItem* item) {
    if (!item) return false;
    UClass* cls = item->ClassField();
    if (!cls) return false;
    const std::string name = cls->GetName();
    if (name.find("Cryopod") != std::string::npos) return true;
    if (name.find("cryopod") != std::string::npos) return true;
    return item->GetCustomItemDataName().ToString() == "Dino";
}

UPrimalItem* FindCryopodInInventory(AShooterPlayerController* controller, int slot_index) {
    if (!controller) return nullptr;
    UPrimalInventoryComponent* inv = controller->GetPlayerInventoryComponent();
    if (!inv) return nullptr;

    if (slot_index >= 0) {
        TArray<UPrimalItem*> items = inv->InventoryItemsField();
        if (slot_index < items.Num() && IsOfficialCryopodItem(items[slot_index]))
            return items[slot_index];
        return nullptr;
    }

    UPrimalItem* equipped = inv->GetEquippedItemOfType(EPrimalEquipmentType::Weapon);
    if (IsOfficialCryopodItem(equipped)) return equipped;

    TArray<UPrimalItem*> items = inv->InventoryItemsField();
    for (int i = 0; i < items.Num(); ++i) {
        if (IsOfficialCryopodItem(items[i])) return items[i];
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
        if (!ParseCryopodItem(item, meta, nullptr)) return nullptr;
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

constexpr float kStandardCryoDurability = 3600.f;

bool CryopodHasTimer(UPrimalItem* item) {
    if (!item) return false;
    const float max_dur = item->ItemDurabilityField();
    if (max_dur <= 0.f) return false;
    // CryoLimitedTime reduz o teto (max < 3600s) — pode estar a 100% do teto reduzido
    if (max_dur < kStandardCryoDurability - 0.5f) return true;
    return item->GetItemDurabilityPercentage() < 0.999f;
}

bool StripCryopodTimer(UPrimalItem* item) {
    if (!item || !CryopodHasTimer(item)) return false;
    const float max_dur = item->ItemDurabilityField();
    // Inverso de ShopCryoDino::GiveCryopod (CryoLimitedTime): restaura max para 3600s
    const float delta = kStandardCryoDurability - max_dur;
    if (delta > 0.01f || delta < -0.01f)
        item->AddItemDurability(delta);
    item->UpdatedItem(true);
    return !CryopodHasTimer(item);
}

bool ParseCryopodItem(UPrimalItem* item, CryoParsedMetadata& out, std::string* error) {
    if (!item) {
        if (error) *error = "item nulo";
        return false;
    }
    if (!IsOfficialCryopodItem(item)) {
        if (error) *error = "nao e cryopod oficial";
        return false;
    }

    FCustomItemData custom_data;
    if (!item->GetCustomItemData(&custom_data)) {
        if (error) *error = "sem CustomItemData";
        return false;
    }
    if (custom_data.CustomDataName.ToString() != "Dino") {
        if (error) *error = "cryopod vazia (sem dino)";
        return false;
    }

    const TArray<float>& floats = custom_data.CustomDataFloats;
    if (floats.Num() < 25) {
        if (error) *error = "CustomDataFloats incompleto";
        return false;
    }

    out = CryoParsedMetadata{};
    out.has_dino_data = true;

    FloatAt(floats, static_cast<int>(StatIdx::Health) + 12, out.health.value);
    FloatAt(floats, static_cast<int>(StatIdx::Stamina) + 12, out.stamina.value);
    FloatAt(floats, static_cast<int>(StatIdx::Oxygen) + 12, out.oxygen.value);
    FloatAt(floats, static_cast<int>(StatIdx::Food) + 12, out.food.value);
    FloatAt(floats, static_cast<int>(StatIdx::Weight) + 12, out.weight.value);
    FloatAt(floats, static_cast<int>(StatIdx::MeleeDamageMultiplier) + 12, out.melee.value);
    FloatAt(floats, static_cast<int>(StatIdx::SpeedMultiplier) + 12, out.speed.value);

    float is_female_f = 0.f;
    if (FloatAt(floats, 24, is_female_f))
        out.is_female = is_female_f > 0.5f;

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

    out.had_timer = CryopodHasTimer(item);

    return true;
}

nlohmann::json CryoMetadataToJson(const CryoParsedMetadata& meta) {
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
        {"health",  {{"value", meta.health.value}}},
        {"stamina", {{"value", meta.stamina.value}}},
        {"oxygen",  {{"value", meta.oxygen.value}}},
        {"food",    {{"value", meta.food.value}}},
        {"weight",  {{"value", meta.weight.value}}},
        {"melee",   {{"value", meta.melee.value}}},
        {"speed",   {{"value", meta.speed.value}}},
    };
    j["extraction_method"] = "blob_parse";
    if (meta.had_timer)
        j["timer_stripped_on_upload"] = true;
    return j;
}

} // namespace CustomShop
