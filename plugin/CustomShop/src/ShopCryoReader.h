#pragma once

#include "pch.h"
#include <optional>
#include <string>
#include <vector>

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
    /** -1 = cryo permanente (sem decay); >= 0 = dias restantes estimados no inventario. */
    float timer_remaining_days = -1.f;
    std::string extraction_method = "custom_item_data";
};

// Lê metadados de cryopod vanilla (espelha ShopCryoDino::BuildCryoCustomData).
bool ParseCryopodItem(UPrimalItem* item, CryoParsedMetadata& out, std::string* error = nullptr,
                      AShooterPlayerController* context_player = nullptr);

// Remove timer de cryopod (restaura durabilidade padrão ~3600s). Retorna true se alterou.
bool StripCryopodTimer(UPrimalItem* item);

bool CryopodHasTimer(UPrimalItem* item);

/** Segundos de decay restantes; -1 = permanente (sem timer de captura). */
float GetCryopodRemainingDecaySeconds(UPrimalItem* item);

/** Dias restantes; -1 = permanente. */
float GetCryopodRemainingDays(UPrimalItem* item);

bool CryopodMeetsMarketTimerRequirement(UPrimalItem* item, float min_days);

void ApplyCryoTimerFieldsToMetadata(UPrimalItem* item, CryoParsedMetadata& out);

nlohmann::json CryoMetadataToJson(const CryoParsedMetadata& meta);

bool IsOfficialCryopodItem(UPrimalItem* item);

UPrimalItem* FindCryopodInInventory(AShooterPlayerController* controller, int slot_index);

// Localiza cryopod cujo parse coincide com o preview (/enviar → /confirmar).
UPrimalItem* FindCryopodMatchingMeta(
    AShooterPlayerController* controller, const CryoParsedMetadata& expected);

bool CryoMetadataMatches(const CryoParsedMetadata& a, const CryoParsedMetadata& b);

/** Uma entrada por cryopod vanilla encontrada no inventario (diagnostico). */
struct CryoDebugEntry {
    int inventory_index = -1;
    bool equipped = false;
    std::string class_name;
    bool vanilla_class = false;
    bool has_timer = false;
    float timer_remaining_days = -1.f;
    float item_durability = 0.f;
    float saved_durability = 0.f;
    float durability_pct = 0.f;
    int custom_datas = 0;
    bool get_custom_data = false;
    bool array_pick = false;
    int floats = 0;
    int doubles = 0;
    int strings = 0;
    int classes = 0;
    int blob_bytes = 0;
    bool clone_ok = false;
    int clone_custom_datas = 0;
    bool clone_get_custom = false;
    bool try_read_ok = false;
    bool parse_ok = false;
    std::string parse_error;
    float imprint_pct = 0.f;
    std::string species;
    std::string name_map;
};

struct CryoInventoryDebugReport {
    int vanilla_cryos = 0;
    int parseable = 0;
    std::vector<CryoDebugEntry> entries;
};

void BuildCryoInventoryDebugReport(AShooterPlayerController* controller, CryoInventoryDebugReport& out);

void LogCryoInventoryDebugReport(
    const std::string& steam_id, const char* stage, const CryoInventoryDebugReport& report);

/** Linhas ASCII curtas para chat in-game (max ~6). */
std::vector<std::string> CryoInventoryDebugChatLines(const CryoInventoryDebugReport& report);

} // namespace CustomShop
