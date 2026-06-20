#pragma once

#include "pch.h"
#include <optional>
#include <string>

namespace CustomShop {

struct CryoParsedMetadata {
    std::string species_blueprint;
    std::string name_map;
    std::string name_breeder;
    std::string sex;
    bool is_female = false;
    bool is_neutered = false;
    float imprint_pct = 0.f;
    int mutations_male = 0;
    int mutations_female = 0;
    int dino_level = 0;
    struct StatVal {
        float value = 0.f;
    };
    StatVal health;
    StatVal stamina;
    StatVal oxygen;
    StatVal food;
    StatVal weight;
    StatVal melee;
    StatVal speed;
    bool has_dino_data = false;
    bool had_timer = false;
};

// Lê metadados de cryopod vanilla (espelha ShopCryoDino::BuildCryoCustomData).
bool ParseCryopodItem(UPrimalItem* item, CryoParsedMetadata& out, std::string* error = nullptr);

// Remove timer de cryopod (restaura durabilidade padrão ~3600s). Retorna true se alterou.
bool StripCryopodTimer(UPrimalItem* item);

bool CryopodHasTimer(UPrimalItem* item);

nlohmann::json CryoMetadataToJson(const CryoParsedMetadata& meta);

bool IsOfficialCryopodItem(UPrimalItem* item);

UPrimalItem* FindCryopodInInventory(AShooterPlayerController* controller, int slot_index);

// Localiza cryopod cujo parse coincide com o preview (/enviar → /confirmar).
UPrimalItem* FindCryopodMatchingMeta(
    AShooterPlayerController* controller, const CryoParsedMetadata& expected);

bool CryoMetadataMatches(const CryoParsedMetadata& a, const CryoParsedMetadata& b);

} // namespace CustomShop
