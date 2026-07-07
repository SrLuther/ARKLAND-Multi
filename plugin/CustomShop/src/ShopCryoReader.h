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
        int points_base = -1;
        int points_added = -1;
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

/** Reancora CustomDataDoubles[0] ao TimeSeconds do mapa atual (cluster cross-map). */
bool RefreshCryopodEncapsulationWorldTime(UPrimalItem* item);

/** Valida cryopod recriada do vault (dino legível). */
bool ValidateMarketCryopodItem(UPrimalItem* item, std::string* error = nullptr,
                               AShooterPlayerController* context_player = nullptr);

/** Inicializa cryo do vault, remove timer, garante carga cheia (~3600s) e valida dino. */
bool PrepareMarketCryopodForDelivery(UPrimalItem* item,
                                     AShooterPlayerController* context_player = nullptr,
                                     std::string* error = nullptr);

/**
 * Spawna o dino da cryopod preparada perto do jogador (/mercado).
 * Com MarketAssignNewDinoId gera ID novo e faz retry em duped=true.
 * Nao adiciona cryopod ao inventario.
 */
bool SpawnMarketDinoFromCryopod(UPrimalItem* item,
                                AShooterPlayerController* player,
                                APrimalDinoCharacter** out_dino = nullptr,
                                std::string* error = nullptr);

/**
 * Descarta cryopod transiente (CreateFromBytes, fora do inventario).
 * Usa guards UObject; nao chama BeginDestroy em ponteiro invalido.
 * Apos spawn bem-sucedido, prefira apenas zerar o ponteiro — o engine pode
 * ja ter invalidado o UObject.
 */
void SafeDestroyTransientCryopod(UPrimalItem* item);

/** Destroi e zera referencia do caller (evita double-destroy). */
void ReleaseTransientCryopod(UPrimalItem*& item);

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

struct DinoIdentity {
    uint32_t dino_id1 = 0;
    uint32_t dino_id2 = 0;
    std::vector<std::pair<uint32_t, uint32_t>> ancestor_pairs;
};

/** Extrai par proprio + ancestrais via spawn probe (bGenerateNewDinoID=false). */
bool ExtractDinoIdentityFromCryopod(UPrimalItem* item,
                                      AShooterPlayerController* player,
                                      DinoIdentity& out);

nlohmann::json DinoIdentityToJson(const DinoIdentity& identity);

} // namespace CustomShop
