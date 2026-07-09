#include "pch.h"
#include "DinoDeliver.h"
#include "DinoConfig.h"
#include "DinoBridge.h"

#include <sstream>
#include <unordered_set>
#include <algorithm>
#include <cctype>

namespace {

constexpr const char* kDefaultCryoBp =
    "Blueprint'/Game/Extinction/CoreBlueprints/Weapons/"
    "PrimalItem_WeaponEmptyCryopod.PrimalItem_WeaponEmptyCryopod'";

constexpr int kStatCount = 7;          // Dino Lab payload (7 stats)
constexpr int kSpawnExactCsvCount = 8; // SpawnExactDino CSV (incl. Crafting)
constexpr int kStatMax = 254;
constexpr int kSpawnExactMaxTotalLevel = 5000;
constexpr float kSpawnExactSearchRadius = 600.0f;

struct SpawnExactCheatParams {
    UShooterCheatManager* cheat = nullptr;
    FString* blueprint = nullptr;
    FString* saddle = nullptr;
    float saddle_quality = 0.0f;
    int base_level = 1;
    int extra_levels = 0;
    FString* wild_stats = nullptr;
    FString* tamed_stats = nullptr;
    FString* name = nullptr;
    int cloned = 0;
    int neutered = 0;
    FString* tamed_date = nullptr;
    FString* uploaded_from = nullptr;
    FString* imprinter_name = nullptr;
    int imprinter_id = 0;
    float imprint_quality = 0.0f;
    FString* colors = nullptr;
    float spawn_dist = 200.0f;
    float spawn_y = 0.0f;
    float spawn_z = 0.0f;
};

// SEH isolado: excecoes de acesso em SpawnExactDino nao propagam para o servidor.
static int SehSpawnExactDinoInvoke(SpawnExactCheatParams* params) {
    if (!params || !params->cheat)
        return 0;
    __try {
        params->cheat->SpawnExactDino(
            params->blueprint,
            params->saddle,
            params->saddle_quality,
            params->base_level,
            params->extra_levels,
            params->wild_stats,
            params->tamed_stats,
            params->name,
            params->cloned,
            params->neutered,
            params->tamed_date,
            params->uploaded_from,
            params->imprinter_name,
            params->imprinter_id,
            params->imprint_quality,
            params->colors,
            0,
            0,
            params->spawn_dist,
            params->spawn_y,
            params->spawn_z);
        return 1;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return 0;
    }
}

std::string NormalizeBlueprintPath(std::string bp) {
    if (bp.empty()) return bp;
    if (bp.find("Blueprint'") != std::string::npos) return bp;
    if (bp.front() == '/')
        return "Blueprint'" + bp + "'";
    return "Blueprint'/Game/" + bp + "'";
}

std::string BlueprintPathInner(const std::string& bp) {
    if (bp.empty()) return bp;
    if (bp.rfind("Blueprint'", 0) == 0 && bp.size() >= 2 && bp.back() == '\'')
        return bp.substr(10, bp.size() - 11);
    return bp;
}

std::string LowerAscii(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(),
                   [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    return s;
}

// Heuristica minima: rejeita itens/selas/estruturas antes de chamar SpawnExactDino.
bool BlueprintPathLooksLikeDinoSpecies(const std::string& blueprint) {
    const std::string inner = LowerAscii(BlueprintPathInner(blueprint));
    if (inner.empty() || inner.find("/game/") == std::string::npos)
        return false;

    static const char* kForbidden[] = {
        "primalitem",
        "saddle",
        "primalstructure",
        "weapon",
        "consumable",
        "emote",
        "buff_",
        "skin",
        "costume",
        "armor",
        "shirt",
        "pants",
        "helmet",
        "gloves",
        "boots",
        "cryopod",
        "eggitem",
        "supplycrate",
        "beacon",
    };
    for (const char* token : kForbidden) {
        if (inner.find(token) != std::string::npos)
            return false;
    }

    if (inner.find("character_bp") != std::string::npos)
        return true;
    if (inner.find("_character.") != std::string::npos)
        return true;
    if (inner.find("/dinos/") != std::string::npos && inner.find("_bp.") != std::string::npos)
        return true;
    const auto dot = inner.rfind('.');
    if (dot != std::string::npos && dot >= 3 &&
        inner.compare(dot - 3, 3, "_bp") == 0)
        return true;

    return false;
}

bool IsPrimalDinoCharacterClass(UClass* cls) {
    if (!cls) return false;
    UClass* dino_base = APrimalDinoCharacter::GetPrivateStaticClass();
    return dino_base && (cls == dino_base || cls->IsChildOf(dino_base));
}

bool BlueprintLoadsAsDinoClass(const std::string& blueprint, UClass*& out_class) {
    out_class = nullptr;
    if (!BlueprintPathLooksLikeDinoSpecies(blueprint)) {
        Log::GetLog()->warn(
            "[DinoLabDeliver] blueprint nao parece especie de dino: '{}'",
            blueprint);
        return false;
    }

    FString fbp(blueprint.c_str());
    out_class = UVictoryCore::BPLoadClass(&fbp);
    if (!out_class) {
        Log::GetLog()->warn(
            "[DinoLabDeliver] blueprint invalido ou nao carregado: '{}'",
            blueprint);
        return false;
    }
    if (!IsPrimalDinoCharacterClass(out_class)) {
        Log::GetLog()->warn(
            "[DinoLabDeliver] blueprint carregou classe que nao e PrimalDinoCharacter: '{}'",
            blueprint);
        out_class = nullptr;
        return false;
    }
    return true;
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

int ClampStatValue(int value) {
    return std::max(0, std::min(kStatMax, value));
}

int ReadStatAt(const nlohmann::json& stats_json, int index) {
    if (!stats_json.is_array() || index < 0 || index >= static_cast<int>(stats_json.size()))
        return 0;
    if (!stats_json[index].is_number_integer() && !stats_json[index].is_number_unsigned())
        return 0;
    return ClampStatValue(stats_json[index].get<int>());
}

int SumStatsJson(const nlohmann::json& stats_json) {
    if (!stats_json.is_array()) return 0;
    int sum = 0;
    const int count = std::min(static_cast<int>(stats_json.size()), kStatCount);
    for (int i = 0; i < count; ++i)
        sum += ReadStatAt(stats_json, i);
    return sum;
}

std::string FormatStatsCsv(const nlohmann::json& stats_json) {
    std::ostringstream oss;
    for (int i = 0; i < kSpawnExactCsvCount; ++i) {
        if (i > 0) oss << ',';
        const int v = (i < kStatCount) ? ReadStatAt(stats_json, i) : 0;
        oss << v;
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

bool DinoMatchesExpectedClass(APrimalDinoCharacter* dino, UClass* expected_class) {
    if (!dino || !expected_class) return true;
    UClass* dino_class = dino->ClassField();
    if (!dino_class) return false;
    return dino_class == expected_class || dino_class->IsChildOf(expected_class);
}

void CollectTeamTamedDinos(AShooterPlayerController* controller,
                           std::unordered_set<APrimalDinoCharacter*>& out) {
    out.clear();
    if (!controller) return;
    const int team = controller->TargetingTeamField();
    UWorld* world = ArkApi::GetApiUtils().GetWorld();
    if (!world) return;

    TArray<AActor*> actors;
    UGameplayStatics::GetAllActorsOfClass(
        world,
        APrimalDinoCharacter::GetPrivateStaticClass(),
        &actors);

    for (AActor* actor : actors) {
        auto* dino = static_cast<APrimalDinoCharacter*>(actor);
        if (dino && dino->TamingTeamIDField() == team)
            out.insert(dino);
    }
}

// Seleciona o dino tameado mais proximo do jogador; opcionalmente exclui atores
// pre-existentes (SpawnExact) e filtra por especie esperada.
APrimalDinoCharacter* FindNearestTamedDino(
    AShooterPlayerController* controller,
    float max_dist,
    const std::unordered_set<APrimalDinoCharacter*>* exclude = nullptr,
    UClass* expected_class = nullptr) {
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
        if (exclude && exclude->count(dino) > 0) continue;
        if (!DinoMatchesExpectedClass(dino, expected_class)) continue;
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

bool ValidateSpawnExactContext(AShooterPlayerController* controller,
                               const std::string& blueprint,
                               const std::string& saddle_bp,
                               int base_level,
                               int extra_levels,
                               UClass*& out_species_class,
                               FString& fbp,
                               FString& fsaddle) {
    out_species_class = nullptr;

    if (!controller) {
        Log::GetLog()->warn("[DinoLabDeliver] SpawnExact — controller nulo");
        return false;
    }
    if (ArkApi::GetApiUtils().GetStatus() != ArkApi::ServerStatus::Ready) {
        Log::GetLog()->warn("[DinoLabDeliver] SpawnExact — servidor nao pronto");
        return false;
    }
    if (!controller->GetPlayerCharacter()) {
        Log::GetLog()->warn("[DinoLabDeliver] SpawnExact — jogador sem pawn");
        return false;
    }
    if (!ArkApi::GetApiUtils().GetWorld()) {
        Log::GetLog()->warn("[DinoLabDeliver] SpawnExact — world indisponivel");
        return false;
    }
    if (!GetPlayerCheatManager(controller)) {
        Log::GetLog()->warn(
            "[DinoLabDeliver] SpawnExact — cheat manager do jogador indisponivel");
        return false;
    }

    fbp = FString(blueprint.c_str());
    if (!BlueprintLoadsAsDinoClass(blueprint, out_species_class)) {
        Log::GetLog()->warn(
            "[DinoLabDeliver] SpawnExact — species blueprint rejeitado: '{}'",
            blueprint);
        return false;
    }

    if (!saddle_bp.empty()) {
        fsaddle = FString(saddle_bp.c_str());
        UClass* saddle_class = UVictoryCore::BPLoadClass(&fsaddle);
        if (!saddle_class) {
            Log::GetLog()->warn(
                "[DinoLabDeliver] SpawnExact — saddle blueprint invalido: '{}'",
                saddle_bp);
            return false;
        }
        if (IsPrimalDinoCharacterClass(saddle_class)) {
            Log::GetLog()->warn(
                "[DinoLabDeliver] SpawnExact — saddle blueprint e classe de dino: '{}'",
                saddle_bp);
            return false;
        }
    } else {
        fsaddle = FString("");
    }

    const int total_level = base_level + extra_levels;
    if (base_level < 1 || extra_levels < 0 || total_level > kSpawnExactMaxTotalLevel) {
        Log::GetLog()->warn(
            "[DinoLabDeliver] SpawnExact — nivel fora dos limites (base={} extra={} total={} max={})",
            base_level, extra_levels, total_level, kSpawnExactMaxTotalLevel);
        return false;
    }

    return true;
}

APrimalDinoCharacter* SpawnExactFromPayload(AShooterPlayerController* controller,
                                            const nlohmann::json& payload) {
    if (!controller) return nullptr;

    const std::string blueprint =
        NormalizeBlueprintPath(JsonStr(payload, "species_blueprint"));
    if (blueprint.empty()) {
        Log::GetLog()->warn("[DinoLabDeliver] SpawnExact — species_blueprint vazio");
        return nullptr;
    }

    const nlohmann::json spawn_exact =
        payload.value("spawn_exact", nlohmann::json::object());
    const nlohmann::json wild = spawn_exact.value("wild_stats", nlohmann::json::array());
    const nlohmann::json tamed = spawn_exact.value("tamed_stats", nlohmann::json::array());
    const int base_level = SumStatsJson(wild) + 1;
    const int extra_levels = SumStatsJson(tamed);

    const std::string saddle_bp_raw = JsonStr(payload, "saddle_blueprint");
    const std::string saddle_bp = saddle_bp_raw.empty()
        ? "" : NormalizeBlueprintPath(saddle_bp_raw);
    const float saddle_quality = saddle_bp.empty() ? 0.0f : 0.0f;

    const std::string dino_name = JsonStr(payload, "custom_name");
    const bool neutered = payload.value("neutered", false);
    const nlohmann::json colors = payload.value("colors", nlohmann::json::array());

    float imprint_quality = 0.0f;
    if (spawn_exact.contains("imprint_pct") && !spawn_exact["imprint_pct"].is_null()) {
        imprint_quality = spawn_exact.value("imprint_pct", 0.0f);
        if (imprint_quality > 1.0f) imprint_quality /= 100.0f;
        imprint_quality = std::max(0.0f, std::min(1.0f, imprint_quality));
    }
    const std::string imprinter_name = JsonStr(spawn_exact, "imprinter_name");
    const int imprinter_id = static_cast<int>(
        ParseImprinterIdHex(JsonStr(spawn_exact, "imprinter_id_hex")));

    FString fbp;
    FString fsaddle;
    UClass* species_class = nullptr;
    if (!ValidateSpawnExactContext(
            controller, blueprint, saddle_bp, base_level, extra_levels,
            species_class, fbp, fsaddle)) {
        return nullptr;
    }

    const std::string wild_csv = FormatStatsCsv(wild);
    const std::string tamed_csv = FormatStatsCsv(tamed);
    if (wild_csv.empty() || tamed_csv.empty()) {
        Log::GetLog()->warn("DinoDeliver: SpawnExact - stats CSV vazio");
        return nullptr;
    }

    FString fwild(wild_csv.c_str());
    FString ftamed(tamed_csv.c_str());
    FString fname(dino_name.c_str());
    FString fempty("");
    FString fimprinter(imprinter_name.c_str());
    FString fcolors(FormatColorsCsv(colors).c_str());

    UShooterCheatManager* cheat = GetPlayerCheatManager(controller);
    if (!cheat) {
        Log::GetLog()->warn("[DinoLabDeliver] SpawnExact — cheat manager indisponivel");
        return nullptr;
    }

    std::unordered_set<APrimalDinoCharacter*> before_spawn;
    CollectTeamTamedDinos(controller, before_spawn);

    const bool was_admin = controller->bIsAdmin()();
    if (!was_admin)
        controller->bIsAdmin() = true;

    SpawnExactCheatParams cheat_params;
    cheat_params.cheat = cheat;
    cheat_params.blueprint = &fbp;
    cheat_params.saddle = &fsaddle;
    cheat_params.saddle_quality = saddle_quality;
    cheat_params.base_level = base_level;
    cheat_params.extra_levels = extra_levels;
    cheat_params.wild_stats = &fwild;
    cheat_params.tamed_stats = &ftamed;
    cheat_params.name = &fname;
    cheat_params.neutered = neutered ? 1 : 0;
    cheat_params.tamed_date = &fempty;
    cheat_params.uploaded_from = &fempty;
    cheat_params.imprinter_name = &fimprinter;
    cheat_params.imprinter_id = imprinter_id;
    cheat_params.imprint_quality = imprint_quality;
    cheat_params.colors = &fcolors;

    Log::GetLog()->info(
        "[DinoLabDeliver] SpawnExact invoke species='{}' base={} extra={} wild='{}' tamed='{}'",
        blueprint, base_level, extra_levels,
        FormatStatsCsv(wild), FormatStatsCsv(tamed));

    const bool spawn_ok = SehSpawnExactDinoInvoke(&cheat_params) != 0;

    if (!was_admin)
        controller->bIsAdmin() = false;

    if (!spawn_ok) {
        Log::GetLog()->error(
            "[DinoLabDeliver] SpawnExact — excecao ou falha no motor (species='{}')",
            blueprint);
        return nullptr;
    }

    // SpawnExact nao retorna ponteiro: preferir dino novo (nao estava no snapshot),
    // mesma especie e menor distancia ao jogador.
    APrimalDinoCharacter* dino =
        FindNearestTamedDino(controller, kSpawnExactSearchRadius, &before_spawn, species_class);
    if (!dino)
        dino = FindNearestTamedDino(controller, kSpawnExactSearchRadius, nullptr, species_class);
    if (!dino)
        Log::GetLog()->warn(
            "[DinoLabDeliver] SpawnExact — dino nao encontrado apos spawn (species='{}')",
            blueprint);
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
    if (!stat) {
        Log::GetLog()->warn("DinoDeliver: BuildCryoCustomData — status component ausente");
    }
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

    double now = 0.0;
    if (AShooterGameMode* game_mode = ArkApi::GetApiUtils().GetShooterGameMode()) {
        if (UWorld* world = game_mode->GetWorld())
            now = world->TimeSecondsField();
    }
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

void AppendAncestorJson(nlohmann::json& ancestors,
                        uint32_t id1, uint32_t id2,
                        const char* side, int generation) {
    if (id1 == 0 && id2 == 0) return;
    ancestors.push_back({
        {"dino_id1", id1},
        {"dino_id2", id2},
        {"side", side},
        {"generation", generation},
    });
}

uint32_t AncestorMaleId1(const FDinoAncestorsEntry& entry) {
    return static_cast<uint32_t>(entry.MaleDinoID1);
}

uint32_t AncestorMaleId2(const FDinoAncestorsEntry& entry) {
    return static_cast<uint32_t>(entry.MaleDinoID2);
}

uint32_t AncestorFemaleId1(const FDinoAncestorsEntry& entry) {
    return static_cast<uint32_t>(entry.FemaleDinoID1);
}

uint32_t AncestorFemaleId2(const FDinoAncestorsEntry& entry) {
    return static_cast<uint32_t>(entry.FemaleDinoID2);
}

void CaptureDinoIdentity(APrimalDinoCharacter* dino, CustomDinoDeliver::DinoIdentityCapture& out) {
    if (!dino) return;
    int id1 = 0;
    int id2 = 0;
    dino->GetDinoIDs(&id1, &id2);
    out.dino_id1 = static_cast<uint32_t>(id1);
    out.dino_id2 = static_cast<uint32_t>(id2);
    out.ancestors = nlohmann::json::array();

    auto capture_chain = [&](const TArray<FDinoAncestorsEntry>& chain, int generation) {
        for (int i = 0; i < chain.Num(); ++i) {
            const FDinoAncestorsEntry& entry = chain[i];
            AppendAncestorJson(out.ancestors,
                               AncestorMaleId1(entry), AncestorMaleId2(entry),
                               "male", generation);
            AppendAncestorJson(out.ancestors,
                               AncestorFemaleId1(entry), AncestorFemaleId2(entry),
                               "female", generation);
        }
    };

    capture_chain(dino->DinoAncestorsField(), 1);
    capture_chain(dino->DinoAncestorsMaleField(), 1);
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

DeliverCustomDinoResult DeliverCustomDino(AShooterPlayerController* controller,
                                          const nlohmann::json& payload) {
    DeliverCustomDinoResult result;
    if (!controller)
        return result;

    const std::string blueprint =
        NormalizeBlueprintPath(JsonStr(payload, "species_blueprint"));
    if (blueprint.empty()) {
        Log::GetLog()->warn("DinoDeliver: empty species_blueprint");
        return result;
    }

    const int level = payload.value("level", 150);
    const bool force_tame = payload.value("force_tame", true);
    const bool neutered = payload.value("neutered", false);
    const std::string gender = JsonStr(payload, "gender", "female");
    const std::string deliver_as = JsonStr(payload, "deliver_as", "cryopod");
    const std::string saddle_bp = JsonStr(payload, "saddle_blueprint");
    const std::string display = JsonStr(payload, "species_display_name", "dino");

    const nlohmann::json spawn_exact =
        payload.value("spawn_exact", nlohmann::json::object());
    const bool payload_spawn_exact = spawn_exact.value("enabled", false);
    const bool use_spawn_exact =
        payload_spawn_exact && DinoConfig::Get().UseSpawnExact();

    if (payload_spawn_exact && !DinoConfig::Get().UseSpawnExact()) {
        Log::GetLog()->error(
            "[DinoLabDeliver] SpawnExact pedido no payload mas UseSpawnExact=false "
            "no plugin (species='{}') — re-sincronize CustomDinoDeliver/config.json",
            blueprint);
        NotifyPlayer(controller, FColorList::Red,
                     "SpawnExact desabilitado no servidor. Contate um admin "
                     "(UseSpawnExact no plugin).");
        return result;
    }

    Log::GetLog()->info(
        "DinoDeliver: start '{}' blueprint='{}' level={} spawn_exact={} deliver_as={}",
        display, blueprint, level, use_spawn_exact, deliver_as);

    if (!BlueprintPathLooksLikeDinoSpecies(blueprint)) {
        Log::GetLog()->error(
            "[DinoLabDeliver] species blueprint rejeitado antes do spawn: '{}'",
            blueprint);
        NotifyPlayer(controller, FColorList::Red,
                     "Blueprint de especie invalido. Contate um admin.");
        return result;
    }

    APrimalDinoCharacter* dino = nullptr;
    if (use_spawn_exact) {
        try {
            dino = SpawnExactFromPayload(controller, payload);
        } catch (const std::exception& e) {
            Log::GetLog()->error(
                "[DinoLabDeliver] SpawnExact exception species='{}' — {}",
                blueprint, e.what());
            dino = nullptr;
        } catch (...) {
            Log::GetLog()->error(
                "[DinoLabDeliver] SpawnExact unknown exception species='{}'",
                blueprint);
            dino = nullptr;
        }
        if (!dino) {
            Log::GetLog()->error(
                "[DinoLabDeliver] SpawnExact failed for '{}' — sem fallback SpawnDino "
                "(stats do payload nao seriam aplicados)",
                blueprint);
            NotifyPlayer(controller, FColorList::Red,
                         "Falha ao spawnar dino (SpawnExact). Contate um admin.");
            return result;
        }
    } else {
        FString fbp(blueprint.c_str());
        dino = ArkApi::GetApiUtils().SpawnDino(
            controller, fbp, nullptr, level, force_tame, neutered);
        if (!dino) {
            Log::GetLog()->error("DinoDeliver: failed to spawn '{}'", blueprint);
            NotifyPlayer(controller, FColorList::Red,
                         "Falha ao spawnar o dino customizado. Contate um admin.");
            return result;
        }
    }

    ApplyGender(dino, gender);
    if (payload.contains("colors"))
        ApplyColors(dino, payload["colors"]);

    const std::string custom_name = JsonStr(payload, "custom_name");
    if (!custom_name.empty() && !use_spawn_exact) {
        FString fname(custom_name.c_str());
        dino->TamedNameField() = fname;
    }

    CaptureDinoIdentity(dino, result.identity);
    const bool has_identity =
        result.identity.dino_id1 != 0 || result.identity.dino_id2 != 0;
    const std::string steam_id = Bridge::GetSteamId(controller);
    Log::GetLog()->info(
        "[DinoLabDeliver] identity id1={} id2={} ancestors={} species='{}' steam={}",
        result.identity.dino_id1, result.identity.dino_id2,
        result.identity.ancestors.size(), display, steam_id);

    if (!has_identity) {
        Log::GetLog()->error(
            "[DinoLabDeliver] identity capture failed species='{}' steam={} — aborting delivery",
            display, steam_id);
        NotifyPlayer(controller, FColorList::Red,
                     "Falha ao registrar identidade do dino. Contate um admin.");
        dino->Destroy(true, false);
        return result;
    }

    if (deliver_as == "cryopod") {
        UPrimalItem* saddle = CreateSaddleItem(saddle_bp);
        if (GiveCryopod(controller, dino, saddle)) {
            Log::GetLog()->info("DinoDeliver: '{}' delivered in cryopod", display);
            NotifyPlayer(controller, FColorList::Green,
                         "Dino customizado entregue em cryopod no seu inventario.");
            result.ok = true;
            return result;
        }

        if (DinoConfig::Get().GroundFallbackOnFullInventory()) {
            Log::GetLog()->warn(
                "DinoDeliver: cryopod failed for '{}' — ground fallback", display);
            NotifyPlayer(controller, FColorList::Yellow,
                         "Cryopod falhou (inventario cheio?). O dino foi spawnado ao seu lado.");
            result.ok = true;
            return result;
        }

        NotifyPlayer(controller, FColorList::Red,
                     "Falha ao entregar cryopod. Inventario cheio.");
        dino->Destroy(true, false);
        return result;
    }

    Log::GetLog()->info("DinoDeliver: '{}' spawned near player", display);
    NotifyPlayer(controller, FColorList::Green, "Dino customizado spawnado ao seu lado.");
    result.ok = true;
    return result;
}

} // namespace CustomDinoDeliver
