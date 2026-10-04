#include "pch.h"
#include "PlayerCommands.h"
#include "PlayerConfig.h"
#include "PlayerPerms.h"
#include "PlayerPoints.h"

#include <Timer.h>

#include <cstring>

namespace {

constexpr float kFoundationUnits = 300.0f;
// Config de produção era 15 fundações (4500 uu). O corpo/feixe aos pés
// cabe nisso se a posição for a do mundo; 30 cobre o ator do feixe um
// pouco afastado do ragdoll sem varrer o mapa (~90 m).
constexpr int kMinLootFoundations = 30;
// DeathItemCache do ASE 361.7 pode trazer um id que não é o
// LinkedPlayerDataID. Nesse caso só entra se estiver aos pés (~36 m).
constexpr int kDeathClassFeetFoundations = 12;

std::unordered_map<std::string, long long> g_cooldowns;

FVector ActorLoc(AActor* actor) {
    if (!actor) return FVector{0, 0, 0};
    USceneComponent* root = actor->RootComponentField();
    if (!root) return FVector{0, 0, 0};
    // RelativeLocation é local ao pai. O DeathItemCache / feixe nasce
    // preso ao corpo, então o relativo fica perto de zero e o raio
    // descarta a bag que está aos pés. ComponentToWorld é a posição no mapa.
    float world_xyz[4] = {};
    std::memcpy(world_xyz, &root->ComponentToWorldField().Translation, sizeof(float) * 3);
    const FVector world{world_xyz[0], world_xyz[1], world_xyz[2]};
    const float mag = world.X * world.X + world.Y * world.Y + world.Z * world.Z;
    if (mag > 1.f) return world;
    return root->RelativeLocationField();
}

float DistSq(const FVector& a, const FVector& b) {
    const float dx = a.X - b.X;
    const float dy = a.Y - b.Y;
    const float dz = a.Z - b.Z;
    return dx * dx + dy * dy + dz * dz;
}

uint64_t SteamId(AShooterPlayerController* c) {
    if (!c) return 0;
    return ArkApi::GetApiUtils().GetSteamIdFromController(c);
}

std::wstring Utf8ToWide(const std::string& text) {
    if (text.empty()) return L"";
    const int len = MultiByteToWideChar(
        CP_UTF8, 0, text.c_str(), -1, nullptr, 0);
    if (len <= 0) return std::wstring(text.begin(), text.end());
    std::wstring out(static_cast<size_t>(len - 1), L'\0');
    MultiByteToWideChar(CP_UTF8, 0, text.c_str(), -1, out.data(), len);
    return out;
}

// SendServerMessage(char*) trata a string como ANSI. UTF-8 vira "??"
// (ê = C3 AA, ã = C3 A3). O chat do ASE mostra wchar inteiro e mantém a cor.
void SendMsg(AShooterPlayerController* c, const FLinearColor& color, const std::string& msg) {
    if (!c || msg.empty()) return;
    const std::wstring wide = Utf8ToWide(msg);
    FString text(wide);
    c->ClientServerChatDirectMessage(&text, color, false);
}

std::string ToLower(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(),
                   [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });
    return s;
}

bool ContainsBlocked(const std::string& name,
                     const std::vector<std::string>& a,
                     const std::vector<std::string>& b) {
    const std::string low = ToLower(name);
    auto contains_any = [&](const std::vector<std::string>& list) {
        for (const auto& w : list) {
            if (w.empty()) continue;
            if (low.find(ToLower(w)) != std::string::npos) return true;
        }
        return false;
    };
    return contains_any(a) || contains_any(b);
}

bool IsOnCooldown(uint64_t steam_id, const std::string& cmd, int seconds) {
    if (seconds <= 0) return false;
    const std::string key = std::to_string(steam_id) + "|" + cmd;
    const auto now = std::chrono::duration_cast<std::chrono::seconds>(
                         std::chrono::steady_clock::now().time_since_epoch())
                         .count();
    const auto it = g_cooldowns.find(key);
    return it != g_cooldowns.end() && (now - it->second) < seconds;
}

void MarkCooldown(uint64_t steam_id, const std::string& cmd) {
    const std::string key = std::to_string(steam_id) + "|" + cmd;
    g_cooldowns[key] = std::chrono::duration_cast<std::chrono::seconds>(
                           std::chrono::steady_clock::now().time_since_epoch())
                           .count();
}

bool HasRealBuff(AShooterCharacter* ch, const char* class_needle, const char* tag_exact) {
    if (!ch) return false;
    TArray<APrimalBuff*> buffs;
    ch->GetBuffs(&buffs);
    const std::string needle = class_needle ? ToLower(class_needle) : "";
    const std::string tag_want = tag_exact ? ToLower(tag_exact) : "";
    for (APrimalBuff* buff : buffs) {
        if (!buff) continue;
        if (!tag_want.empty()) {
            FName tag = buff->CustomTagField();
            // NAME_None (índice 0) é a tag vazia da maioria dos buffs — não é algema.
            if (tag.ComparisonIndex != 0) {
                FString tag_fs;
                tag.ToString(&tag_fs);
                if (ToLower(tag_fs.ToString()) == tag_want) return true;
            }
        }
        if (needle.empty()) continue;
        UClass* cls = buff->ClassField();
        if (!cls) continue;
        FString name_fs;
        cls->NameField().ToString(&name_fs);
        if (ToLower(name_fs.ToString()).find(needle) != std::string::npos)
            return true;
    }
    return false;
}

bool ChargePoints(AShooterPlayerController* c, uint64_t steam_id, int price) {
    auto& cfg = ArkPlayer::PlayerConfig::Get();
    if (cfg.EverythingFree() || price <= 0) return true;

    auto unavailable = [&]() {
        SendMsg(c, FColorList::Red, cfg.Msg("PointsUnavailable",
            "Sistema de pontos indisponivel. Comando cancelado."));
    };
    auto no_points = [&]() {
        SendMsg(c, FColorList::Red,
                cfg.FormatMsg("NoPoints", price,
                              "Voce nao tem pontos suficientes ({} necessarios)"));
    };

    // Loja fora (DLL/API/MySQL). Saldo curto é outra frase, mais abaixo.
    if (!ArkPlayer::Points::Available()) {
        unavailable();
        return false;
    }
    const int balance = ArkPlayer::Points::GetPoints(steam_id);
    if (balance < 0) {
        unavailable();
        return false;
    }
    if (balance < price) {
        no_points();
        return false;
    }
    if (!ArkPlayer::Points::SpendPoints(steam_id, price)) {
        if (!ArkPlayer::Points::Available()) unavailable();
        else no_points();
        return false;
    }
    SendMsg(c, FColorList::Green,
            cfg.FormatMsg("CommandPurchased", price, "Comando comprado por {} pontos"));
    return true;
}

bool WorldReady() {
    return ArkApi::GetApiUtils().GetStatus() == ArkApi::ServerStatus::Ready;
}

bool IsGenesisMap() {
    if (!WorldReady()) return false;
    AShooterGameMode* gm = ArkApi::GetApiUtils().GetShooterGameMode();
    if (!gm) return false;
    FString map_name;
    gm->GetMapName(&map_name);
    const std::string name = ToLower(map_name.ToString());
    return name.find("gen") != std::string::npos;
}

bool HasMindwipeItem(AShooterCharacter* character) {
    if (!character) return false;
    UPrimalInventoryComponent* inv = character->MyInventoryComponentField();
    if (!inv) return false;
    TArray<UPrimalItem*> items = inv->InventoryItemsField();
    for (UPrimalItem* item : items) {
        if (!item) continue;
        FString name;
        item->GetItemName(&name, false, true, nullptr);
        const std::string s = ToLower(name.ToString());
        if (s.find("mindwipe") != std::string::npos)
            return true;
    }
    return false;
}

// ── /mindwipe ──────────────────────────────────────────────────────────────

void CmdMindwipe(AShooterPlayerController* c, FString*, EChatSendMode::Type) {
    if (!c || !WorldReady()) return;
    auto& cfg = ArkPlayer::PlayerConfig::Get();
    const auto& meta = cfg.WipeMeta();
    if (!meta.enabled) {
        SendMsg(c, FColorList::Red, cfg.Msg("NotEnabled", "Não habilitado"));
        return;
    }

    const uint64_t sid = SteamId(c);
    const auto group = cfg.ResolveGroup(sid);
    if (!group.wipe_enabled) {
        SendMsg(c, FColorList::Red, cfg.Msg("NoPermission", "Sem permissão"));
        return;
    }
    if (IsOnCooldown(sid, "wipe", meta.cooldown_seconds)) {
        SendMsg(c, FColorList::Yellow, cfg.Msg("CommandCooldown", "Cooldown"));
        return;
    }

    AShooterCharacter* ch = c->GetPlayerCharacter();
    if (!ch || ch->IsDead()) {
        SendMsg(c, FColorList::Red, cfg.Msg("PlayerSuicideDead", "Já está morto"));
        return;
    }
    if (group.wipe_require_mindwipe && !HasMindwipeItem(ch)) {
        SendMsg(c, FColorList::Red,
                cfg.Msg("PlayerCharacterWipeNoMindwipe", "Precisa de mindwipe"));
        return;
    }
    if (!ChargePoints(c, sid, group.wipe_price)) return;

    auto* state = static_cast<AShooterPlayerState*>(c->PlayerStateField());
    if (!state) {
        SendMsg(c, FColorList::Red, "Falha ao resetar atributos.");
        return;
    }
    state->DoRespec(nullptr, nullptr, false);
    MarkCooldown(sid, "wipe");
    SendMsg(c, FColorList::Green, cfg.Msg("PlayerCharacterWipe", "Redistribua seus pontos"));
}

// ── /missao ────────────────────────────────────────────────────────────────

void CmdMissao(AShooterPlayerController* c, FString*, EChatSendMode::Type) {
    if (!c || !WorldReady()) return;
    auto& cfg = ArkPlayer::PlayerConfig::Get();
    const auto& meta = cfg.MissionMeta();
    if (!meta.enabled) {
        SendMsg(c, FColorList::Red, cfg.Msg("NotEnabled", "Não habilitado"));
        return;
    }

    const uint64_t sid = SteamId(c);
    const auto group = cfg.ResolveGroup(sid);
    if (!group.mission_enabled) {
        SendMsg(c, FColorList::Red, cfg.Msg("NoPermission", "Sem permissão"));
        return;
    }
    if (IsOnCooldown(sid, "mission", meta.cooldown_seconds)) {
        SendMsg(c, FColorList::Yellow, cfg.Msg("CommandCooldown", "Cooldown"));
        return;
    }
    if (!IsGenesisMap()) {
        SendMsg(c, FColorList::Red,
                cfg.Msg("PlayerCompleteMissionWrongMap",
                        "Você precisa estar em Genesis 1 ou 2"));
        return;
    }

    AMissionType* mission = c->GetActiveMission();
    if (!mission) {
        AShooterCharacter* ch = c->GetPlayerCharacter();
        if (ch) mission = ch->GetActiveMission();
    }
    if (mission) {
        const std::string tag = ToLower(mission->MissionDisplayNameField().ToString());
        for (const auto& blocked : meta.master_blacklist) {
            if (!blocked.empty() && tag.find(ToLower(blocked)) != std::string::npos) {
                SendMsg(c, FColorList::Red,
                        cfg.Msg("PlayerCompleteMissionBlacklisted",
                                "Missão bloqueada"));
                return;
            }
        }
    }

    if (!ChargePoints(c, sid, group.mission_price)) return;

    auto* cheat = static_cast<UShooterCheatManager*>(c->CheatManagerField());
    if (!cheat) {
        SendMsg(c, FColorList::Yellow, "CheatManager indisponível — tente como admin.");
        return;
    }
    cheat->CompleteMission();
    MarkCooldown(sid, "mission");
    SendMsg(c, FColorList::Green, cfg.Msg("PlayerCompleteMission", "Missão concluída"));
}

// ── nome que sobrevive a morte e troca de mapa ────────────────────────────
// RenamePlayer só escreve o pawn atual. O respawn e a viagem leem
// MyPlayerCharacterConfig.PlayerCharacterName do perfil (.arkprofile).

std::unordered_map<uint64_t, std::string> g_names;
bool g_names_loaded = false;
bool g_reapply_pending = false;
bool g_hook_save = false;
bool g_hook_apply = false;
bool g_hook_possess = false;
int g_save_depth = 0;

std::string NamesPath() {
    return ArkApi::Tools::GetCurrentDir() + "/ArkApi/Plugins/ArkPlayer/names.json";
}

void LoadNames() {
    if (g_names_loaded) return;
    g_names_loaded = true;
    std::ifstream in(NamesPath());
    if (!in.is_open()) return;
    nlohmann::json doc;
    try {
        in >> doc;
    } catch (const std::exception& e) {
        Log::GetLog()->error("ArkPlayer: names.json: {}", e.what());
        return;
    }
    if (!doc.is_object()) return;
    for (auto it = doc.begin(); it != doc.end(); ++it) {
        if (!it.value().is_string()) continue;
        try {
            const uint64_t id = std::stoull(it.key());
            const std::string name = it.value().get<std::string>();
            if (id != 0 && !name.empty()) g_names[id] = name;
        } catch (const std::exception&) {
        }
    }
}

void SaveNames() {
    nlohmann::json doc = nlohmann::json::object();
    for (const auto& entry : g_names) {
        if (entry.first == 0 || entry.second.empty()) continue;
        doc[std::to_string(entry.first)] = entry.second;
    }
    std::ofstream out(NamesPath(), std::ios::trunc);
    if (!out.is_open()) {
        Log::GetLog()->error("ArkPlayer: não gravou {}", NamesPath());
        return;
    }
    out << doc.dump(2);
}

AShooterPlayerState* ShooterState(APlayerState* state) {
    if (!state) return nullptr;
    static UClass* cls = nullptr;
    if (!cls) cls = AShooterPlayerState::GetPrivateStaticClass(nullptr);
    if (!cls || !state->IsA(cls)) return nullptr;
    return static_cast<AShooterPlayerState*>(state);
}

AShooterPlayerController* AsShooterPC(APlayerController* pc) {
    if (!pc) return nullptr;
    if (!pc->IsA(AShooterPlayerController::GetPrivateStaticClass())) return nullptr;
    return static_cast<AShooterPlayerController*>(pc);
}

UPrimalPlayerData* DataOf(AShooterPlayerController* c, AShooterCharacter* ch) {
    if (ch) {
        if (UPrimalPlayerData* data = ch->GetPlayerData()) return data;
    }
    if (!c) return nullptr;
    if (AShooterPlayerState* state = ShooterState(c->PlayerStateField()))
        return state->MyPlayerDataField();
    return nullptr;
}

uint64_t SteamFromUniqueId(UPrimalPlayerData* data) {
    if (!data) return 0;
    FString id;
    data->GetUniqueIdString(&id);
    const std::string text = id.ToString();
    std::string digits;
    digits.reserve(text.size());
    for (unsigned char ch : text) {
        if (ch >= '0' && ch <= '9') digits.push_back(static_cast<char>(ch));
    }
    if (digits.size() < 8) return 0;
    try {
        return std::stoull(digits);
    } catch (const std::exception&) {
        return 0;
    }
}

uint64_t SteamForData(UPrimalPlayerData* data) {
    const uint64_t from_id = SteamFromUniqueId(data);
    if (from_id != 0 && g_names.find(from_id) != g_names.end()) return from_id;
    UWorld* world = ArkApi::GetApiUtils().GetWorld();
    if (!world || !data) return from_id;
    for (TWeakObjectPtr<APlayerController> weak : world->PlayerControllerListField()) {
        AShooterPlayerController* pc = AsShooterPC(weak.Get());
        if (!pc) continue;
        AShooterCharacter* ch = pc->GetPlayerCharacter();
        if (DataOf(pc, ch) == data) {
            const uint64_t steam = SteamId(pc);
            if (steam != 0) return steam;
        }
    }
    return from_id;
}

void StampStruct(FPrimalPlayerDataStruct* data, const FString& name) {
    if (!data) return;
    data->MyPlayerCharacterConfigField().PlayerCharacterName = name;
    data->PlayerNameField() = name;
}

void StampProfile(AShooterPlayerController* c, AShooterCharacter* ch, const FString& name) {
    if (UPrimalPlayerData* data = DataOf(c, ch))
        StampStruct(data->MyDataField(), name);
    if (c) {
        if (AShooterPlayerState* state = ShooterState(c->PlayerStateField()))
            StampStruct(state->MyPlayerDataStructField(), name);
    }
}

bool ProfileHasName(UPrimalPlayerData* data, const std::string& want) {
    if (!data || !data->MyDataField()) return false;
    return data->MyDataField()->MyPlayerCharacterConfigField().PlayerCharacterName.ToString() == want;
}

void ApplyStoredName(AShooterPlayerController* c, AShooterCharacter* ch, bool save) {
    if (!c || !ch || ch->IsDead()) return;
    LoadNames();
    const uint64_t steam = SteamId(c);
    const auto it = g_names.find(steam);
    if (it == g_names.end() || it->second.empty()) return;

    const std::string& want = it->second;
    FString fname(Utf8ToWide(want).c_str());
    if (ch->PlayerNameField().ToString() != want) {
        ch->PlayerNameField() = fname;
        ch->RenamePlayer(&fname);
    }
    UPrimalPlayerData* data = DataOf(c, ch);
    if (!data || ProfileHasName(data, want)) return;
    StampProfile(c, ch, fname);
    if (!save) return;
    if (UWorld* world = ArkApi::GetApiUtils().GetWorld())
        data->SavePlayerData(world);
}

void PersistCharacterName(AShooterPlayerController* c, AShooterCharacter* ch,
                          uint64_t steam, const std::string& utf8) {
    LoadNames();
    if (steam != 0) {
        g_names[steam] = utf8;
        SaveNames();
    }
    FString fname(Utf8ToWide(utf8).c_str());
    ch->PlayerNameField() = fname;
    ch->RenamePlayer(&fname);
    StampProfile(c, ch, fname);
    if (UPrimalPlayerData* data = DataOf(c, ch)) {
        if (UWorld* world = ArkApi::GetApiUtils().GetWorld())
            data->SavePlayerData(world);
    }
    Log::GetLog()->info("ArkPlayer: nome gravado no perfil steam={}", steam);
}

void ReapplyOnline() {
    UWorld* world = ArkApi::GetApiUtils().GetWorld();
    if (!world) return;
    for (TWeakObjectPtr<APlayerController> weak : world->PlayerControllerListField()) {
        AShooterPlayerController* pc = AsShooterPC(weak.Get());
        if (!pc) continue;
        ApplyStoredName(pc, pc->GetPlayerCharacter(), true);
    }
}

void ReapplyTimer() {
    g_reapply_pending = false;
    ReapplyOnline();
}

void ScheduleReapply() {
    if (g_reapply_pending) return;
    g_reapply_pending = true;
    API::Timer::Get().DelayExecute(&ReapplyTimer, 2);
}

struct OwnerIds {
    uint64_t linked = 0;
    uint64_t profile = 0;
};

OwnerIds CollectOwnerIds(AShooterCharacter* ch, AShooterPlayerController* c) {
    OwnerIds ids;
    if (ch) {
        ids.linked = ch->GetLinkedPlayerDataID();
        if (ids.linked == 0) ids.linked = ch->LinkedPlayerDataIDField();
    }
    if (UPrimalPlayerData* data = DataOf(c, ch)) {
        if (FPrimalPlayerDataStruct* mine = data->MyDataField())
            ids.profile = mine->PlayerDataIDField();
    }
    return ids;
}

bool SameOwnerId(uint64_t cache_id, uint64_t owner_id) {
    if (cache_id == 0 || owner_id == 0) return false;
    if (cache_id == owner_id) return true;
    const uint64_t a = cache_id & 0xFFFFFFFFull;
    const uint64_t b = owner_id & 0xFFFFFFFFull;
    return a != 0 && a == b;
}

bool OwnsId(uint64_t cache_id, const OwnerIds& ids) {
    return SameOwnerId(cache_id, ids.linked) || SameOwnerId(cache_id, ids.profile);
}

std::string ClassChain(AActor* actor) {
    std::string out;
    if (!actor) return out;
    int guard = 0;
    for (UClass* cls = actor->ClassField(); cls && guard < 8; ++guard) {
        FString n;
        cls->NameField().ToString(&n);
        const std::string piece = n.ToString();
        if (!out.empty()) out.push_back('/');
        out += piece;
        const std::string low = ToLower(piece);
        if (low == "actor" || low == "object") break;
        cls = static_cast<UClass*>(cls->SuperStructField());
    }
    return out;
}

bool IsDeathCacheClass(const std::string& chain) {
    const std::string low = ToLower(chain);
    return low.find("deathitem") != std::string::npos
        || low.find("deathcache") != std::string::npos
        || low.find("death_item") != std::string::npos;
}

bool InventoryHasItems(UPrimalInventoryComponent* inv) {
    if (!inv) return false;
    for (UPrimalItem* item : inv->InventoryItemsField()) {
        if (item) return true;
    }
    for (UPrimalItem* item : inv->EquippedItemsField()) {
        if (item) return true;
    }
    return false;
}

struct LootTarget {
    UPrimalInventoryComponent* inv = nullptr;
    AActor* destroy_actor = nullptr;
    std::string kind;
};

void PullInventory(AShooterPlayerController* c, UPrimalInventoryComponent* inv) {
    if (!c || !inv) return;
    FString empty(L"");
    c->ServerTransferAllFromRemoteInventory_Implementation(inv, &empty, &empty, &empty, true);
}

// ── /loot ──────────────────────────────────────────────────────────────────

void CmdLoot(AShooterPlayerController* c, FString*, EChatSendMode::Type) {
    if (!c || !WorldReady()) return;
    auto& cfg = ArkPlayer::PlayerConfig::Get();
    const auto& meta = cfg.LootMeta();
    if (!meta.enabled) {
        SendMsg(c, FColorList::Red, cfg.Msg("NotEnabled", "Não habilitado"));
        return;
    }

    const uint64_t sid = SteamId(c);
    const auto group = cfg.ResolveGroup(sid);
    if (!group.loot_enabled) {
        SendMsg(c, FColorList::Red, cfg.Msg("NoPermission", "Sem permissão"));
        return;
    }
    if (IsOnCooldown(sid, "loot", meta.cooldown_seconds)) {
        SendMsg(c, FColorList::Yellow, cfg.Msg("CommandCooldown", "Cooldown"));
        return;
    }

    AShooterCharacter* ch = c->GetPlayerCharacter();
    if (!ch || ch->IsDead()) {
        SendMsg(c, FColorList::Red, cfg.Msg("PlayerSuicideDead", "Já está morto"));
        return;
    }

    UWorld* world = ArkApi::GetApiUtils().GetWorld();
    if (!world) {
        SendMsg(c, FColorList::Yellow,
                cfg.Msg("PlayerGetDeathBagsNone", "Nenhuma bag de morte encontrada."));
        return;
    }

    const OwnerIds ids = CollectOwnerIds(ch, c);
    const FVector player_loc = ActorLoc(ch);
    int foundations = group.loot_range_foundations;
    if (foundations < kMinLootFoundations) foundations = kMinLootFoundations;
    const float range = static_cast<float>(foundations) * kFoundationUnits;
    const float range_sq = range * range;
    const float feet = static_cast<float>(kDeathClassFeetFoundations) * kFoundationUnits;
    const float feet_sq = feet * feet;

    std::vector<LootTarget> targets;

    TArray<AActor*> actors;
    UGameplayStatics::GetAllActorsOfClass(
        world, APrimalStructureItemContainer::GetPrivateStaticClass(), &actors);
    for (AActor* actor : actors) {
        auto* container = static_cast<APrimalStructureItemContainer*>(actor);
        if (!container) continue;
        const float dist_sq = DistSq(ActorLoc(container), player_loc);
        if (dist_sq > range_sq) continue;
        const std::string chain = ClassChain(container);
        const bool death_class = IsDeathCacheClass(chain);
        const uint64_t cache_id = container->DeathCacheCharacterIDField();
        const bool death_mark = death_class
            || cache_id != 0
            || container->DeathCacheCreationTimeField() > 0.0
            || container->bUseDeathCacheCharacterID()();
        if (!death_mark) continue;
        const bool owned = OwnsId(cache_id, ids);
        const bool at_feet = dist_sq <= feet_sq;
        // O feixe verde do ASE 361.7 é DeathItemCache. O bit
        // bUseDeathCacheCharacterID e o LinkedPlayerDataID não o identificam.
        if (!owned && !(death_class && (cache_id == 0 || at_feet))) continue;
        UPrimalInventoryComponent* inv = container->MyInventoryComponentField();
        if (!inv) continue;
        LootTarget target;
        target.inv = inv;
        target.destroy_actor = container;
        target.kind = chain.empty() ? "death-cache" : chain;
        targets.push_back(target);
    }

    TArray<AActor*> bodies;
    UGameplayStatics::GetAllActorsOfClass(
        world, AShooterCharacter::GetPrivateStaticClass(), &bodies);
    for (AActor* actor : bodies) {
        auto* corpse = static_cast<AShooterCharacter*>(actor);
        if (!corpse || corpse == ch) continue;
        if (!corpse->IsDead() && !corpse->bIsDead()()) continue;
        const float dist_sq = DistSq(ActorLoc(corpse), player_loc);
        if (dist_sq > range_sq) continue;
        uint64_t cid = corpse->GetLinkedPlayerDataID();
        if (cid == 0) cid = corpse->LinkedPlayerDataIDField();
        const bool owned = OwnsId(cid, ids);
        const bool at_feet = dist_sq <= feet_sq;
        if (!owned && !(cid == 0 && at_feet)) continue;
        UPrimalInventoryComponent* inv = corpse->MyInventoryComponentField();
        if (!inv) continue;
        if (!at_feet && !InventoryHasItems(inv)) continue;
        LootTarget target;
        target.inv = inv;
        target.kind = "corpse";
        targets.push_back(target);
    }

    if (targets.empty()) {
        Log::GetLog()->info(
            "ArkPlayer: /loot nenhuma bag (raio={:.0f} uu, containers={})",
            range, static_cast<int>(actors.Num()));
        SendMsg(c, FColorList::Yellow,
                cfg.Msg("PlayerGetDeathBagsNone", "Nenhuma bag de morte encontrada."));
        return;
    }

    if (!ChargePoints(c, sid, group.loot_price)) return;

    for (const LootTarget& target : targets) {
        PullInventory(c, target.inv);
        if (target.destroy_actor && target.inv)
            target.destroy_actor->Destroy(true, false);
    }

    MarkCooldown(sid, "loot");
    Log::GetLog()->info(
        "ArkPlayer: /loot {} alvo(s), primeiro='{}', raio={:.0f}",
        targets.size(), targets.front().kind, range);
    SendMsg(c, FColorList::Green, cfg.Msg("PlayerGetDeathBags", "Bag(s) recuperada(s)"));
}

// ── /nome ──────────────────────────────────────────────────────────────────

void CmdNome(AShooterPlayerController* c, FString* message, EChatSendMode::Type) {
    if (!c || !WorldReady()) return;
    auto& cfg = ArkPlayer::PlayerConfig::Get();
    const auto& meta = cfg.RenameMeta();
    if (!meta.enabled) {
        SendMsg(c, FColorList::Red, cfg.Msg("NotEnabled", "Não habilitado"));
        return;
    }

    const uint64_t sid = SteamId(c);
    const auto group = cfg.ResolveGroup(sid);
    if (!group.rename_enabled) {
        SendMsg(c, FColorList::Red, cfg.Msg("NoPermission", "Sem permissão"));
        return;
    }
    if (IsOnCooldown(sid, "rename", meta.cooldown_seconds)) {
        SendMsg(c, FColorList::Yellow, cfg.Msg("CommandCooldown", "Cooldown"));
        return;
    }

    std::string raw = message ? message->ToString() : "";
    // Chat entrega "/nome NovoNome" — remover o comando.
    {
        std::istringstream ss(raw);
        std::string cmd_tok;
        ss >> cmd_tok;
        std::string rest;
        std::getline(ss, rest);
        const auto start = rest.find_first_not_of(" \t");
        raw = (start == std::string::npos) ? "" : rest.substr(start);
        const auto end = raw.find_last_not_of(" \t");
        if (end != std::string::npos) raw = raw.substr(0, end + 1);
    }

    if (raw.empty() || raw.size() > 32) {
        SendMsg(c, FColorList::Red, cfg.Msg("InvalidName", "Nome inválido"));
        return;
    }
    if (ContainsBlocked(raw, meta.master_blacklist, group.rename_blacklist)) {
        SendMsg(c, FColorList::Red, cfg.Msg("InvalidName", "Nome inválido"));
        return;
    }

    AShooterCharacter* ch = c->GetPlayerCharacter();
    if (!ch || ch->IsDead()) {
        SendMsg(c, FColorList::Red, cfg.Msg("PlayerSuicideDead", "Já está morto"));
        return;
    }

    if (!ChargePoints(c, sid, group.rename_price)) return;

    PersistCharacterName(c, ch, sid, raw);
    MarkCooldown(sid, "rename");
    SendMsg(c, FColorList::Green, cfg.Msg("PlayerRename", "Renomeado com sucesso"));
}

// ── /kill ──────────────────────────────────────────────────────────────────

void CmdKill(AShooterPlayerController* c, FString*, EChatSendMode::Type) {
    if (!c || !WorldReady()) return;
    auto& cfg = ArkPlayer::PlayerConfig::Get();
    const auto& meta = cfg.SuicideMeta();
    if (!meta.enabled) {
        SendMsg(c, FColorList::Red, cfg.Msg("NotEnabled", "Não habilitado"));
        return;
    }

    const uint64_t sid = SteamId(c);
    const auto group = cfg.ResolveGroup(sid);
    if (!group.suicide_enabled) {
        SendMsg(c, FColorList::Red, cfg.Msg("NoPermission", "Sem permissão"));
        return;
    }
    if (IsOnCooldown(sid, "kill", meta.cooldown_seconds)) {
        SendMsg(c, FColorList::Yellow, cfg.Msg("CommandCooldown", "Cooldown"));
        return;
    }

    AShooterCharacter* ch = c->GetPlayerCharacter();
    if (!ch) {
        SendMsg(c, FColorList::Red, cfg.Msg("PlayerSuicideDead", "Já está morto"));
        return;
    }
    if (ch->IsDead()) {
        SendMsg(c, FColorList::Red, cfg.Msg("PlayerSuicideDead", "Já está morto"));
        return;
    }

    // Flags: false = bloqueado nesse estado (igual PlayerUtilities).
    if (!group.suicide_allow_ko && ch->bIsSleeping()()) {
        SendMsg(c, FColorList::Red, cfg.Msg("PlayerSuicideKO", "Inconsciente"));
        return;
    }
    if (!group.suicide_allow_sitting && ch->IsSitting(false)) {
        SendMsg(c, FColorList::Red, cfg.Msg("PlayerSuicideSitting", "Sentado"));
        return;
    }
    if (!group.suicide_allow_riding && (ch->bIsRiding()() || c->IsRidingDino())) {
        SendMsg(c, FColorList::Red, cfg.Msg("PlayerSuicideRiding", "Montado"));
        return;
    }
    if (!group.suicide_allow_picked && (ch->bIsCarried()() || ch->CharacterIsCarriedAsPassenger())) {
        SendMsg(c, FColorList::Red, cfg.Msg("PlayerSuicidePicked", "Carregado"));
        return;
    }
    if (!group.suicide_allow_grappled && ch->CurrentGrappledToCharacterField().Get()) {
        SendMsg(c, FColorList::Red, cfg.Msg("PlayerSuicideGrappled", "Preso"));
        return;
    }
    // FName("Handcuffed", FNAME_Find) vira NAME_None se o nome não está na
    // tabela. HasBuffWithCustomTag(None) casa com qualquer buff sem tag e
    // bloqueava /kill de quem não estava algemado. Só Buff_Handcuffed_C
    // (ou tag Handcuffed de verdade, índice != 0) bloqueia.
    if (!group.suicide_allow_handcuffs && HasRealBuff(ch, "handcuff", "handcuffed")) {
        SendMsg(c, FColorList::Red, cfg.Msg("PlayerSuicideHandcuffs", "Algemado"));
        return;
    }
    if (!group.suicide_allow_mind_control
        && (HasRealBuff(ch, "mindcontrol", "mindcontrol")
            || HasRealBuff(ch, "brainslug", nullptr))) {
        SendMsg(c, FColorList::Red, cfg.Msg("PlayerSuicideMindControl", "Noglin"));
        return;
    }

    if (!ChargePoints(c, sid, group.suicide_price)) return;

    MarkCooldown(sid, "kill");
    SendMsg(c, FColorList::Yellow, cfg.Msg("PlayerSuicide", "Você morreu"));
    ch->Suicide();
}

void CmdAdminReload(APlayerController* pc, FString*, bool) {
    auto* admin = static_cast<AShooterPlayerController*>(pc);
    try {
        ArkPlayer::PlayerConfig::Get().Load();
        ArkPlayer::Perms::Init();
        ArkPlayer::Points::Init();
        if (admin)
            SendMsg(admin, FColorList::Green, "ArkPlayer: config recarregado.");
        Log::GetLog()->info("ArkPlayer: config reloaded");
    } catch (const std::exception& e) {
        if (admin) SendMsg(admin, FColorList::Red, std::string("Reload failed: ") + e.what());
        Log::GetLog()->error("ArkPlayer reload: {}", e.what());
    }
}

DECLARE_HOOK(UPrimalPlayerData_SavePlayerData, void, UPrimalPlayerData*, UWorld*);
void Hook_UPrimalPlayerData_SavePlayerData(UPrimalPlayerData* data, UWorld* world) {
    if (data && g_save_depth == 0) {
        LoadNames();
        const uint64_t steam = SteamForData(data);
        const auto it = g_names.find(steam);
        if (it != g_names.end() && !it->second.empty()) {
            FString fname(Utf8ToWide(it->second).c_str());
            StampStruct(data->MyDataField(), fname);
        }
    }
    UPrimalPlayerData_SavePlayerData_original(data, world);
    if (!data || g_save_depth > 0) return;
    const uint64_t steam = SteamForData(data);
    const auto it = g_names.find(steam);
    if (it == g_names.end() || it->second.empty()) return;
    if (ProfileHasName(data, it->second)) return;
    FString fname(Utf8ToWide(it->second).c_str());
    StampStruct(data->MyDataField(), fname);
    ++g_save_depth;
    UPrimalPlayerData_SavePlayerData_original(data, world);
    --g_save_depth;
}

DECLARE_HOOK(UPrimalPlayerData_ApplyToPlayerCharacter, void, UPrimalPlayerData*, AShooterPlayerState*, AShooterCharacter*);
void Hook_UPrimalPlayerData_ApplyToPlayerCharacter(UPrimalPlayerData* data,
                                                   AShooterPlayerState* state,
                                                   AShooterCharacter* pawn) {
    UPrimalPlayerData_ApplyToPlayerCharacter_original(data, state, pawn);
    AShooterPlayerController* pc = nullptr;
    if (state) pc = AsShooterPC(state->GetOwnerController());
    if (!pc && pawn) pc = AsShooterPC(pawn->GetOwnerController());
    if (pc) ApplyStoredName(pc, pawn, true);
    ScheduleReapply();
}

DECLARE_HOOK(AShooterPlayerController_Possess, void, AShooterPlayerController*, APawn*);
void Hook_AShooterPlayerController_Possess(AShooterPlayerController* pc, APawn* pawn) {
    AShooterPlayerController_Possess_original(pc, pawn);
    if (!pawn || !pawn->IsA(AShooterCharacter::GetPrivateStaticClass())) return;
    ApplyStoredName(pc, static_cast<AShooterCharacter*>(pawn), true);
}

template <typename T>
bool TryNameHook(const char* name, LPVOID detour, T** original) {
    if (ArkApi::GetHooks().SetHook(name, detour, original)) return true;
    Log::GetLog()->error("ArkPlayer: hook nao encaixou: {}", name);
    return false;
}

void InstallNameHooks() {
    LoadNames();
    g_hook_save = TryNameHook(
        "UPrimalPlayerData.SavePlayerData(UWorld*)",
        Hook_UPrimalPlayerData_SavePlayerData,
        &UPrimalPlayerData_SavePlayerData_original);
    g_hook_apply = TryNameHook(
        "UPrimalPlayerData.ApplyToPlayerCharacter(AShooterPlayerState*,AShooterCharacter*)",
        Hook_UPrimalPlayerData_ApplyToPlayerCharacter,
        &UPrimalPlayerData_ApplyToPlayerCharacter_original);
    g_hook_possess = TryNameHook(
        "AShooterPlayerController.Possess(APawn*)",
        Hook_AShooterPlayerController_Possess,
        &AShooterPlayerController_Possess_original);
    ScheduleReapply();
    Log::GetLog()->info(
        "ArkPlayer: nome persiste em perfil + {} ({} entradas)",
        NamesPath(), g_names.size());
}

void RemoveNameHooks() {
    if (g_hook_save)
        ArkApi::GetHooks().DisableHook(
            "UPrimalPlayerData.SavePlayerData(UWorld*)",
            Hook_UPrimalPlayerData_SavePlayerData);
    if (g_hook_apply)
        ArkApi::GetHooks().DisableHook(
            "UPrimalPlayerData.ApplyToPlayerCharacter(AShooterPlayerState*,AShooterCharacter*)",
            Hook_UPrimalPlayerData_ApplyToPlayerCharacter);
    if (g_hook_possess)
        ArkApi::GetHooks().DisableHook(
            "AShooterPlayerController.Possess(APawn*)",
            Hook_AShooterPlayerController_Possess);
    g_hook_save = false;
    g_hook_apply = false;
    g_hook_possess = false;
}

} // anonymous namespace

namespace ArkPlayer {
namespace Commands {

void Register() {
    auto& cfg = PlayerConfig::Get();
    ArkApi::GetCommands().AddConsoleCommand("ArkPlayer.Reload", &CmdAdminReload);

    ArkApi::GetCommands().AddChatCommand(cfg.WipeMeta().chat_command.c_str(), &CmdMindwipe);
    ArkApi::GetCommands().AddChatCommand(cfg.MissionMeta().chat_command.c_str(), &CmdMissao);
    ArkApi::GetCommands().AddChatCommand(cfg.LootMeta().chat_command.c_str(), &CmdLoot);
    ArkApi::GetCommands().AddChatCommand(cfg.RenameMeta().chat_command.c_str(), &CmdNome);
    ArkApi::GetCommands().AddChatCommand(cfg.SuicideMeta().chat_command.c_str(), &CmdKill);
    InstallNameHooks();

    Log::GetLog()->info(
        "ArkPlayer: commands registered ({}, {}, {}, {}, {})",
        cfg.WipeMeta().chat_command,
        cfg.MissionMeta().chat_command,
        cfg.LootMeta().chat_command,
        cfg.RenameMeta().chat_command,
        cfg.SuicideMeta().chat_command);
}

void Unregister() {
    RemoveNameHooks();
    auto& cfg = PlayerConfig::Get();
    ArkApi::GetCommands().RemoveConsoleCommand("ArkPlayer.Reload");
    ArkApi::GetCommands().RemoveChatCommand(cfg.WipeMeta().chat_command.c_str());
    ArkApi::GetCommands().RemoveChatCommand(cfg.MissionMeta().chat_command.c_str());
    ArkApi::GetCommands().RemoveChatCommand(cfg.LootMeta().chat_command.c_str());
    ArkApi::GetCommands().RemoveChatCommand(cfg.RenameMeta().chat_command.c_str());
    ArkApi::GetCommands().RemoveChatCommand(cfg.SuicideMeta().chat_command.c_str());
}

} // namespace Commands
} // namespace ArkPlayer
