#include "pch.h"
#include "PlayerCommands.h"
#include "PlayerConfig.h"
#include "PlayerPerms.h"
#include "PlayerPoints.h"

namespace {

constexpr float kFoundationUnits = 300.0f;

std::unordered_map<std::string, long long> g_cooldowns;

FVector ActorLoc(AActor* actor) {
    if (!actor) return FVector{0, 0, 0};
    USceneComponent* root = actor->RootComponentField();
    if (!root) return FVector{0, 0, 0};
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

void SendMsg(AShooterPlayerController* c, const FLinearColor& color, const std::string& msg) {
    if (!c || msg.empty()) return;
    ArkApi::GetApiUtils().SendServerMessage(c, color, msg.c_str());
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

bool ChargePoints(AShooterPlayerController* c, uint64_t steam_id, int price) {
    auto& cfg = ArkPlayer::PlayerConfig::Get();
    if (cfg.EverythingFree() || price <= 0) return true;

    if (!ArkPlayer::Points::Available()) {
        SendMsg(c, FColorList::Red, cfg.Msg("PointsUnavailable",
            "Sistema de pontos indisponível. Comando cancelado."));
        return false;
    }
    if (!ArkPlayer::Points::SpendPoints(steam_id, price)) {
        SendMsg(c, FColorList::Red,
                cfg.FormatMsg("NoPoints", price,
                              "Você não tem pontos suficientes ({} necessários)"));
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

    const unsigned __int64 player_data_id = ch->GetLinkedPlayerDataID();
    UWorld* world = ArkApi::GetApiUtils().GetWorld();
    if (!world || player_data_id == 0) {
        SendMsg(c, FColorList::Red, cfg.Msg("PlayerGetDeathBagsNone", "Nenhuma bag"));
        return;
    }

    const FVector player_loc = ActorLoc(ch);
    const float range = static_cast<float>(group.loot_range_foundations) * kFoundationUnits;
    const float range_sq = range * range;

    TArray<AActor*> actors;
    UGameplayStatics::GetAllActorsOfClass(
        world, APrimalStructureItemContainer::GetPrivateStaticClass(), &actors);

    std::vector<APrimalStructureItemContainer*> bags;
    for (AActor* actor : actors) {
        auto* container = static_cast<APrimalStructureItemContainer*>(actor);
        if (!container) continue;
        if (!container->bUseDeathCacheCharacterID()()) continue;
        if (container->DeathCacheCharacterIDField() != player_data_id) continue;
        if (DistSq(ActorLoc(container), player_loc) > range_sq) continue;
        bags.push_back(container);
    }

    if (bags.empty()) {
        SendMsg(c, FColorList::Yellow,
                cfg.Msg("PlayerGetDeathBagsNone", "Nenhuma bag de morte encontrada."));
        return;
    }

    if (!ChargePoints(c, sid, group.loot_price)) return;

    FString empty(L"");
    for (APrimalStructureItemContainer* bag : bags) {
        UPrimalInventoryComponent* inv = bag->MyInventoryComponentField();
        if (!inv) continue;
        c->ServerTransferAllFromRemoteInventory(inv, &empty, &empty, &empty, true);
        bag->Destroy(true, false);
    }

    MarkCooldown(sid, "loot");
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

    FString new_name(ArkApi::Tools::Utf8Decode(raw).c_str());
    ch->RenamePlayer(&new_name);
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
    if (!group.suicide_allow_handcuffs
        && ch->HasBuffWithCustomTag(FName("Handcuffed", EFindName::FNAME_Find))) {
        SendMsg(c, FColorList::Red, cfg.Msg("PlayerSuicideHandcuffs", "Algemado"));
        return;
    }
    if (!group.suicide_allow_mind_control
        && ch->HasBuffWithCustomTag(FName("MindControl", EFindName::FNAME_Find))) {
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

    Log::GetLog()->info(
        "ArkPlayer: commands registered ({}, {}, {}, {}, {})",
        cfg.WipeMeta().chat_command,
        cfg.MissionMeta().chat_command,
        cfg.LootMeta().chat_command,
        cfg.RenameMeta().chat_command,
        cfg.SuicideMeta().chat_command);
}

void Unregister() {
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
