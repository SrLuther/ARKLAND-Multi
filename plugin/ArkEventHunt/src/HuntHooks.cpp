#include "pch.h"
#include "HuntHooks.h"
#include "HuntConfig.h"
#include "HuntHttpClient.h"
#include "HuntRegistry.h"
#include "HuntWorld.h"

#include <unordered_set>
#include <thread>

namespace {

std::string ToLower(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(),
                   [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });
    return s;
}

std::string ActorClassHint(AActor* actor) {
    if (!actor) return {};
    UClass* cls = actor->ClassField();
    if (!cls) return {};
    FString full;
    cls->GetFullName(&full, nullptr);
    return full.ToString();
}

std::string DamageTypeHint(FDamageEvent* damage_event) {
    if (!damage_event) return {};
    try {
        UClass* cls = damage_event->DamageTypeClassField().uClass;
        if (!cls) return {};
        FString full;
        cls->GetFullName(&full, nullptr);
        return full.ToString();
    } catch (...) {
        return {};
    }
}

std::string ResolveWeaponHint(AController* killer, AActor* damage_causer) {
    std::string from_causer = ActorClassHint(damage_causer);
    if (!from_causer.empty())
        return from_causer;

    if (killer && killer->IsA(AShooterPlayerController::GetPrivateStaticClass())) {
        auto* spc = static_cast<AShooterPlayerController*>(killer);
        AShooterCharacter* ch = spc->GetPlayerCharacter();
        if (ch)
            return ActorClassHint(ch);
    }
    return {};
}

bool WhitelistMatch(const std::string& hint,
                    const std::vector<std::string>& whitelist) {
    if (hint.empty() || whitelist.empty()) return false;
    const std::string low = ToLower(hint);
    for (const auto& w : whitelist) {
        if (w.empty()) continue;
        std::string tag = w;
        if (tag.rfind("tag:", 0) == 0) {
            tag = tag.substr(4);
            const std::string t = ToLower(tag);
            if (t == "melee") {
                static const char* melee_keys[] = {
                    "melee", "sword", "pike", "club", "spear", "hatchet",
                    "pick", "axe", "whip", "lance", "teksword", "weapsword",
                    "weappike", "weapspear", "weapclub", "weaphatchet",
                };
                for (const char* k : melee_keys) {
                    if (low.find(k) != std::string::npos)
                        return true;
                }
                continue;
            }
        }
        if (low.find(ToLower(tag)) != std::string::npos)
            return true;
    }
    return false;
}

bool LooksLikeModPath(const std::string& hint) {
    const std::string low = ToLower(hint);
    static const char* keys[] = {
        "/mods/", "\\mods\\", "/game/mods/", "content/mods",
        "steamworkshop", "workshop/", "modded",
    };
    for (const char* k : keys) {
        if (low.find(k) != std::string::npos)
            return true;
    }
    return false;
}

bool LooksLikeOfficialPath(const std::string& hint) {
    const std::string low = ToLower(hint);
    static const char* keys[] = {
        "/game/primaleearth/",
        "/game/scorchedearth/",
        "/game/aberration/",
        "/game/extinction/",
        "/game/genesis",
        "/game/asa/",
        "coreblueprints/weapons",
        "coreblueprints/weapons/",
        "primalitem_weapon",
        "primalitemammo_",
        "weapbow",
        "weapgun",
        "weaprifle",
        "weapshotgun",
        "weappike",
        "weapspear",
        "weapcrossbow",
        "weaptekrifle",
        "weaptekpistol",
        "weapteksword",
        "weapsword",
        "weaponsword",
        "primalitem_weaponsword",
    };
    for (const char* k : keys) {
        if (low.find(k) != std::string::npos)
            return true;
    }
    return false;
}

bool LooksLikeTorpor(const std::string& damage_type_hint,
                     const std::string& weapon_hint) {
    const std::string blob = ToLower(damage_type_hint + " " + weapon_hint);
    static const char* keys[] = {
        "torpor", "torpidity", "tranq", "tranquiliz", "narcotic", "sleeping",
    };
    for (const char* k : keys) {
        if (blob.find(k) != std::string::npos)
            return true;
    }
    return false;
}

bool IsAllowedWeaponDamage(const std::string& weapon_hint,
                           const std::vector<std::string>& challenge_whitelist,
                           bool official_only) {
    if (weapon_hint.empty())
        return false;

    auto& cfg = ArkEventHunt::HuntConfig::Get();

    if (official_only && LooksLikeModPath(weapon_hint))
        return false;

    std::vector<std::string> whitelist = challenge_whitelist;
    if (whitelist.empty()) {
        if (official_only)
            whitelist = cfg.OfficialWeaponCatalog();
        else
            whitelist = cfg.WeaponWhitelist();
    }
    if (whitelist.empty())
        return false;

    if (!WhitelistMatch(weapon_hint, whitelist))
        return false;

    if (official_only) {
        const bool in_catalog =
            WhitelistMatch(weapon_hint, cfg.OfficialWeaponCatalog());
        if (!in_catalog && !LooksLikeOfficialPath(weapon_hint))
            return false;
    }
    return true;
}

void CaptureIds(APrimalDinoCharacter* dino, uint32_t& id1, uint32_t& id2) {
    id1 = 0;
    id2 = 0;
    if (!dino) return;
    int a = 0;
    int b = 0;
    dino->GetDinoIDs(&a, &b);
    id1 = static_cast<uint32_t>(a);
    id2 = static_cast<uint32_t>(b);
}

std::string UrlEncode(const std::string& s) {
    static const char* hex = "0123456789ABCDEF";
    std::string out;
    out.reserve(s.size() * 3);
    for (unsigned char c : s) {
        if (std::isalnum(c) || c == '-' || c == '_' || c == '.' || c == '~') {
            out.push_back(static_cast<char>(c));
        } else {
            out.push_back('%');
            out.push_back(hex[c >> 4]);
            out.push_back(hex[c & 0xF]);
        }
    }
    return out;
}

// true = HTTP/JSON ok (active may still be false). false = API unreachable /
// auth/teams error — caller must NOT treat as "not in team" / stolen.
bool LookupKillerTeam(uint64_t steam_u64, bool& active, uint64_t& team_id) {
    active = false;
    team_id = 0;
    if (steam_u64 == 0) return false;
    const std::string steam = std::to_string(steam_u64);
    const auto resp = ArkEventHunt::HttpClient::Get(
        "/api/teams/plugin/membership/" + UrlEncode(steam));
    if (resp.status == 0 || resp.body.empty() || resp.status >= 400) {
        Log::GetLog()->warn(
            "ArkEventHunt membership (Die): API fail steam={} status={}",
            steam, resp.status);
        return false;
    }
    try {
        const auto j = nlohmann::json::parse(resp.body);
        if (j.contains("ok") && !j.value("ok", false)) {
            Log::GetLog()->warn(
                "ArkEventHunt membership (Die): ok=false steam={}", steam);
            return false;
        }
        nlohmann::json data = j;
        if (j.contains("data") && j["data"].is_object())
            data = j["data"];
        active = data.value("active", false);
        if (data.contains("team_id") && !data["team_id"].is_null()) {
            if (data["team_id"].is_number())
                team_id = data["team_id"].get<uint64_t>();
            else if (data["team_id"].is_string()) {
                try {
                    team_id = static_cast<uint64_t>(
                        std::stoull(data["team_id"].get<std::string>()));
                } catch (...) {
                    team_id = 0;
                }
            }
        }
        return true;
    } catch (...) {
        Log::GetLog()->warn(
            "ArkEventHunt membership (Die): JSON fail steam={}", steam);
        return false;
    }
}

// Idempotência Mode A independente do registry (Unbind após Die).
std::mutex g_mode_a_outcome_mu;
std::unordered_set<int64_t> g_mode_a_outcome_claims;

bool TryClaimModeAOutcomeSlot(int64_t claim_id) {
    if (claim_id <= 0) return false;
    std::lock_guard<std::mutex> lock(g_mode_a_outcome_mu);
    if (g_mode_a_outcome_claims.count(claim_id)) return false;
    g_mode_a_outcome_claims.insert(claim_id);
    return true;
}

void NotifyKiller(AShooterPlayerController* killer_pc,
                  uint64_t killer_steam,
                  const std::string& msg) {
    if (msg.empty()) return;
    AShooterPlayerController* pc = killer_pc;
    if (!pc && killer_steam != 0)
        pc = ArkEventHunt::World::FindPlayerBySteamId(
            std::to_string(killer_steam));
    if (pc)
        ArkEventHunt::World::SendPlayerChat(pc, msg);
}

void ReliablePostJson(const std::string& path, const std::string& body) {
    // Detached com retries agressivos — Die não pode deixar SPAWNED eterno.
    std::thread([path, body]() {
        try {
            constexpr int kAttempts = 8;
            const auto resp =
                ArkEventHunt::HttpClient::PostJsonRetry(path, body, kAttempts);
            if (resp.status >= 200 && resp.status < 300) {
                Log::GetLog()->info(
                    "ArkEventHunt HTTP reliable POST {} status={}",
                    path, resp.status);
                return;
            }
            Log::GetLog()->error(
                "ArkEventHunt HTTP reliable POST FAILED {} status={} "
                "body_len={} — claim pode ficar SPAWNED; admin void ou "
                "reenviar complete/fail",
                path, resp.status, resp.body.size());
        } catch (const std::exception& e) {
            Log::GetLog()->error(
                "ArkEventHunt HTTP reliable POST {} exception: {}",
                path, e.what());
        } catch (...) {
            Log::GetLog()->error(
                "ArkEventHunt HTTP reliable POST {} unknown exception", path);
        }
    }).detach();
}

void PostModeAOutcome(const ArkEventHunt::Registry::Entry& entry,
                      bool success,
                      const char* fail_reason,
                      uint64_t killer_steam,
                      uint64_t killer_team,
                      const std::string& weapon_hint,
                      AShooterPlayerController* killer_pc) {
    if (entry.claim_id <= 0) return;
    if (!TryClaimModeAOutcomeSlot(entry.claim_id)) {
        Log::GetLog()->warn(
            "ArkEventHunt ModeA outcome duplicate skip claim={}",
            entry.claim_id);
        return;
    }
    // Best-effort no registry (pode já ter sido Unbind).
    ArkEventHunt::Registry::MarkOutcomeSent(entry.dino_id1, entry.dino_id2);

    auto& cfg = ArkEventHunt::HuntConfig::Get();

    // Loot só em COMPLETED válido — idempotente via claim slot acima.
    if (success && !entry.loot_on_complete.empty()) {
        AShooterPlayerController* pc = killer_pc;
        if (!pc && killer_steam != 0)
            pc = ArkEventHunt::World::FindPlayerBySteamId(
                std::to_string(killer_steam));
        if (pc) {
            const int n =
                ArkEventHunt::World::GiveLootTable(pc, entry.loot_on_complete);
            Log::GetLog()->info(
                "ArkEventHunt ModeA loot claim={} stacks_ok={} of {}",
                entry.claim_id, n, entry.loot_on_complete.size());
        } else {
            Log::GetLog()->warn(
                "ArkEventHunt ModeA loot: killer offline claim={} steam={}",
                entry.claim_id, killer_steam);
        }
    }

    const float total_hp =
        entry.allowed_hp_damage + entry.other_hp_damage;
    const float ratio =
        total_hp > 0.f ? (entry.allowed_hp_damage / total_hp) : 0.f;

    nlohmann::json body = {
        {"killer_steam_id", killer_steam ? std::to_string(killer_steam) : ""},
        {"killer_team_id", killer_team},
        {"weapon_hint", weapon_hint},
        {"dino_id1", entry.dino_id1},
        {"dino_id2", entry.dino_id2},
        {"server_id", entry.server_id},
        {"owner_steam_id", entry.owner_steam_id},
        {"allowed_hp_damage", entry.allowed_hp_damage},
        {"other_hp_damage", entry.other_hp_damage},
        {"torpor_hits", entry.torpor_hits},
        {"weapon_damage_ratio", ratio},
        {"min_allowed_weapon_damage_ratio",
         entry.min_allowed_weapon_damage_ratio},
        {"forbid_torpor", entry.forbid_torpor},
        {"official_weapons_only", entry.official_weapons_only},
        {"damage_events", entry.damage_events},
    };

    std::string path;
    if (success) {
        body["idempotency_key"] =
            "complete:" + std::to_string(entry.claim_id);
        path = "/api/event-hunt/a/claims/" + std::to_string(entry.claim_id) +
               "/complete";
        NotifyKiller(
            killer_pc, killer_steam,
            cfg.Msg("EveKillOk",
                    "Evento: kill válido! Pontuação a registar…"));
    } else {
        body["reason"] = fail_reason ? fail_reason : "unknown";
        body["idempotency_key"] =
            std::string("fail:") + std::to_string(entry.claim_id) + ":" +
            (fail_reason ? fail_reason : "unknown");
        path = "/api/event-hunt/a/claims/" + std::to_string(entry.claim_id) +
               "/fail";
        const std::string reason = fail_reason ? fail_reason : "unknown";
        if (reason == "weapon") {
            NotifyKiller(
                killer_pc, killer_steam,
                cfg.Msg("EveKillFailWeapon",
                        "Evento: FAIL — arma/torpor/ratio inválidos. Tentativa consumida."));
        } else if (reason == "stolen") {
            NotifyKiller(
                killer_pc, killer_steam,
                cfg.Msg("EveKillFailStolen",
                        "Evento: FAIL — kill de outra Equipe / sem Steam. Tentativa consumida."));
        } else {
            std::string m = cfg.Msg(
                "EveKillFail",
                "Evento: FAIL ({reason}). Tentativa consumida.");
            const auto pos = m.find("{reason}");
            if (pos != std::string::npos)
                m.replace(pos, 8, reason);
            NotifyKiller(killer_pc, killer_steam, m);
        }
    }

    ReliablePostJson(path, body.dump());
    Log::GetLog()->info(
        "ArkEventHunt ModeA outcome queued claim={} ok={} reason={} "
        "killer={} team={} ratio={:.3f}",
        entry.claim_id, success, fail_reason ? fail_reason : "-",
        killer_steam, killer_team, ratio);
}

void PostModeBKill(const ArkEventHunt::Registry::Entry& entry,
                   bool valid,
                   const char* fail_reason,
                   uint64_t killer_steam,
                   uint64_t killer_team,
                   const std::string& weapon_hint,
                   AShooterPlayerController* killer_pc) {
    if (entry.instance_id <= 0) return;
    if (!ArkEventHunt::Registry::MarkOutcomeSent(entry.dino_id1, entry.dino_id2))
        return;

    if (valid && !entry.loot_on_complete.empty()) {
        AShooterPlayerController* pc = killer_pc;
        if (!pc && killer_steam != 0)
            pc = ArkEventHunt::World::FindPlayerBySteamId(
                std::to_string(killer_steam));
        if (pc) {
            const int n =
                ArkEventHunt::World::GiveLootTable(pc, entry.loot_on_complete);
            Log::GetLog()->info(
                "ArkEventHunt ModeB loot instance={} stacks_ok={} of {}",
                entry.instance_id, n, entry.loot_on_complete.size());
        } else {
            Log::GetLog()->warn(
                "ArkEventHunt ModeB loot: killer offline instance={} steam={}",
                entry.instance_id, killer_steam);
        }
    }

    const float total_hp =
        entry.allowed_hp_damage + entry.other_hp_damage;
    const float ratio =
        total_hp > 0.f ? (entry.allowed_hp_damage / total_hp) : 0.f;

    nlohmann::json body = {
        {"valid", valid},
        {"killer_steam_id", killer_steam ? std::to_string(killer_steam) : ""},
        {"killer_team_id", killer_team},
        {"weapon_hint", weapon_hint},
        {"dino_id1", entry.dino_id1},
        {"dino_id2", entry.dino_id2},
        {"server_id", entry.server_id},
        {"mode", "PUBLIC"},
        {"allowed_hp_damage", entry.allowed_hp_damage},
        {"other_hp_damage", entry.other_hp_damage},
        {"personal_tame_hp_damage", entry.personal_tame_hp_damage},
        {"torpor_hits", entry.torpor_hits},
        {"weapon_damage_ratio", ratio},
        {"min_allowed_weapon_damage_ratio",
         entry.min_allowed_weapon_damage_ratio},
        {"allow_personal_tames", entry.allow_personal_tames},
        {"forbid_torpor", entry.forbid_torpor},
        {"official_weapons_only", entry.official_weapons_only},
        {"damage_events", entry.damage_events},
        {"idempotency_key", "kill:" + std::to_string(entry.instance_id)},
    };
    if (fail_reason)
        body["fail_reason"] = fail_reason;
    else
        body["fail_reason"] = nullptr;

    ArkEventHunt::HttpClient::PostJsonDetached(
        "/api/event-hunt/b/instances/" + std::to_string(entry.instance_id) +
            "/kill",
        body.dump(), 3);
    Log::GetLog()->info(
        "ArkEventHunt ModeB kill queued instance={} valid={} reason={} "
        "killer={} team={} ratio={:.3f} tameHP={:.1f}",
        entry.instance_id, valid, fail_reason ? fail_reason : "-",
        killer_steam, killer_team, ratio, entry.personal_tame_hp_damage);
}

void TrackDamageOnEntry(APrimalDinoCharacter* dino,
                        float hp_amount,
                        FDamageEvent* damage_event,
                        AController* instigator,
                        AActor* damage_causer,
                        bool is_killing_blow) {
    if (!dino || hp_amount < 0.f) return;
    uint32_t id1 = 0;
    uint32_t id2 = 0;
    CaptureIds(dino, id1, id2);

    ArkEventHunt::Registry::Entry entry;
    if (!ArkEventHunt::Registry::Find(id1, id2, entry))
        return;

    std::vector<std::string> whitelist = entry.allowed_weapons;
    if (whitelist.empty()) {
        if (entry.official_weapons_only)
            whitelist =
                ArkEventHunt::HuntConfig::Get().OfficialWeaponCatalog();
        else
            whitelist = ArkEventHunt::HuntConfig::Get().WeaponWhitelist();
    }

    const std::string weapon = ResolveWeaponHint(instigator, damage_causer);
    const std::string dmg_type = DamageTypeHint(damage_event);
    const bool is_torpor = LooksLikeTorpor(dmg_type, weapon);
    const bool is_tame =
        ArkEventHunt::World::IsPersonalTameActor(damage_causer);

    bool allowed = false;
    if (is_tame) {
        // Personal tames: allowed só se o dino/challenge permitir.
        allowed = entry.allow_personal_tames;
    } else {
        allowed = IsAllowedWeaponDamage(
            weapon, whitelist, entry.official_weapons_only);
    }

    const uint64_t steam = ArkApi::GetApiUtils().GetAttackerSteamID(
        dino, instigator, damage_causer, false);

    ArkEventHunt::Registry::RecordDamage(
        id1, id2, hp_amount, allowed, is_torpor, is_tame, weapon, steam);

    Log::GetLog()->info(
        "ArkEventHunt dmg{}: id1={} id2={} hp={:.1f} allowed={} torpor={} "
        "tame={} weapon='{}' type='{}'",
        is_killing_blow ? " FATAL" : "", id1, id2, hp_amount, allowed,
        is_torpor, is_tame, weapon, dmg_type);
}

bool WeaponRatioOk(const ArkEventHunt::Registry::Entry& entry, float& ratio_out) {
    const float total = entry.allowed_hp_damage + entry.other_hp_damage;
    if (total <= 0.f) {
        ratio_out = 0.f;
        return false;
    }
    ratio_out = entry.allowed_hp_damage / total;
    return ratio_out + 1e-4f >= entry.min_allowed_weapon_damage_ratio;
}

void HandleModeADie(const ArkEventHunt::Registry::Entry& entry,
                    uint64_t killer_steam,
                    const std::string& weapon,
                    AShooterPlayerController* killer_pc) {
    auto& cfg = ArkEventHunt::HuntConfig::Get();
    float ratio = 0.f;
    if (entry.forbid_torpor && entry.torpor_hits > 0.f) {
        PostModeAOutcome(entry, false, "weapon", killer_steam, 0, weapon,
                         killer_pc);
        return;
    }
    if (!WeaponRatioOk(entry, ratio)) {
        PostModeAOutcome(entry, false, "weapon", killer_steam, 0, weapon,
                         killer_pc);
        return;
    }
    if (killer_steam == 0) {
        NotifyKiller(
            killer_pc, 0,
            cfg.Msg("EveKillNoSteam",
                    "Evento: kill ignorado para score — SteamID do killer não resolvido; a marcar FAIL."));
        PostModeAOutcome(entry, false, "stolen", 0, 0, weapon, killer_pc);
        return;
    }

    const bool is_owner =
        !entry.owner_steam_id.empty() &&
        std::to_string(killer_steam) == entry.owner_steam_id;

    bool active = false;
    uint64_t killer_team = 0;
    const bool membership_ok =
        LookupKillerTeam(killer_steam, active, killer_team);

    // API down / auth: NUNCA deixar SPAWNED eterno (bug antigo: return cedo).
    if (!membership_ok) {
        if (is_owner) {
            Log::GetLog()->warn(
                "ArkEventHunt Mode A Die: membership API fail — owner kill "
                "trusted team={} steam={} claim={}",
                entry.team_id, killer_steam, entry.claim_id);
            NotifyKiller(
                killer_pc, killer_steam,
                cfg.Msg("EveKillMembershipDegraded",
                        "Evento: API Equipe offline — a registar kill do dono do claim."));
            PostModeAOutcome(entry, true, nullptr, killer_steam, entry.team_id,
                             weapon, killer_pc);
            return;
        }
        Log::GetLog()->error(
            "ArkEventHunt Mode A Die: membership API fail — non-owner "
            "steam={} expected_team={} claim={} — FAIL api_membership "
            "(desbloqueia SPAWNED; staff pode grant)",
            killer_steam, entry.team_id, entry.claim_id);
        NotifyKiller(
            killer_pc, killer_steam,
            cfg.Msg("EveKillMembershipFail",
                    "Evento: API Equipe offline no kill — FAIL temporário. Contacta staff se fores da Equipe certa."));
        PostModeAOutcome(entry, false, "api_membership", killer_steam, 0,
                         weapon, killer_pc);
        return;
    }

    if (!active || killer_team == 0 || killer_team != entry.team_id) {
        PostModeAOutcome(entry, false, "stolen", killer_steam, killer_team,
                         weapon, killer_pc);
        return;
    }

    PostModeAOutcome(entry, true, nullptr, killer_steam, killer_team, weapon,
                     killer_pc);
}

void HandleModeBDie(const ArkEventHunt::Registry::Entry& entry,
                    uint64_t killer_steam,
                    AActor* damage_causer,
                    const std::string& weapon,
                    AShooterPlayerController* killer_pc) {
    float ratio = 0.f;
    const bool tame_blow =
        ArkEventHunt::World::IsPersonalTameActor(damage_causer);
    const bool tame_cheese =
        !entry.allow_personal_tames &&
        (tame_blow || entry.personal_tame_hp_damage > 0.f);

    if (tame_cheese) {
        // Kill por tame proibido → sem score (API recebe valid=false).
        bool active = false;
        uint64_t killer_team = 0;
        if (killer_steam != 0)
            LookupKillerTeam(killer_steam, active, killer_team);
        PostModeBKill(entry, false, "tame", killer_steam, killer_team, weapon,
                      killer_pc);
        return;
    }

    if (entry.forbid_torpor && entry.torpor_hits > 0.f) {
        bool active = false;
        uint64_t killer_team = 0;
        if (killer_steam != 0)
            LookupKillerTeam(killer_steam, active, killer_team);
        PostModeBKill(entry, false, "weapon", killer_steam, killer_team,
                      weapon, killer_pc);
        return;
    }

    if (!WeaponRatioOk(entry, ratio)) {
        bool active = false;
        uint64_t killer_team = 0;
        if (killer_steam != 0)
            LookupKillerTeam(killer_steam, active, killer_team);
        PostModeBKill(entry, false, "weapon", killer_steam, killer_team,
                      weapon, killer_pc);
        return;
    }

    bool active = false;
    uint64_t killer_team = 0;
    if (killer_steam != 0)
        LookupKillerTeam(killer_steam, active, killer_team);

    // Inscrição / credit Team+MVP é responsabilidade da API (só inscritas).
    PostModeBKill(entry, true, nullptr, killer_steam, killer_team, weapon,
                  killer_pc);
}

} // anonymous

DECLARE_HOOK(APrimalDinoCharacter_TakeDamage, float, APrimalDinoCharacter*,
             float, FDamageEvent*, AController*, AActor*);
DECLARE_HOOK(APrimalDinoCharacter_Die, bool, APrimalDinoCharacter*, float,
             FDamageEvent*, AController*, AActor*);

float Hook_APrimalDinoCharacter_TakeDamage(APrimalDinoCharacter* _this,
                                           float Damage,
                                           FDamageEvent* DamageEvent,
                                           AController* EventInstigator,
                                           AActor* DamageCauser) {
    const float applied = APrimalDinoCharacter_TakeDamage_original(
        _this, Damage, DamageEvent, EventInstigator, DamageCauser);

    if (_this && applied > 0.f) {
        TrackDamageOnEntry(_this, applied, DamageEvent, EventInstigator,
                           DamageCauser, /*is_killing_blow=*/false);
    } else if (_this && DamageEvent) {
        const std::string weapon =
            ResolveWeaponHint(EventInstigator, DamageCauser);
        const std::string dmg_type = DamageTypeHint(DamageEvent);
        if (LooksLikeTorpor(dmg_type, weapon)) {
            TrackDamageOnEntry(_this, 0.f, DamageEvent, EventInstigator,
                               DamageCauser, /*is_killing_blow=*/false);
        }
    }

    return applied;
}

bool Hook_APrimalDinoCharacter_Die(APrimalDinoCharacter* _this,
                                   float KillingDamage,
                                   FDamageEvent* DamageEvent,
                                   AController* Killer,
                                   AActor* DamageCauser) {
    if (_this) {
        uint32_t id1 = 0;
        uint32_t id2 = 0;
        CaptureIds(_this, id1, id2);

        ArkEventHunt::Registry::Entry entry;
        if (ArkEventHunt::Registry::Find(id1, id2, entry)) {
            const uint64_t steam = ArkApi::GetApiUtils().GetAttackerSteamID(
                _this, Killer, DamageCauser, false);
            const std::string weapon = ResolveWeaponHint(Killer, DamageCauser);
            AShooterPlayerController* killer_pc = nullptr;
            if (Killer &&
                Killer->IsA(AShooterPlayerController::GetPrivateStaticClass())) {
                killer_pc = static_cast<AShooterPlayerController*>(Killer);
            }

            const float fatal_hp = KillingDamage > 0.f ? KillingDamage : 0.f;
            TrackDamageOnEntry(_this, fatal_hp, DamageEvent, Killer,
                               DamageCauser, /*is_killing_blow=*/true);

            ArkEventHunt::Registry::Find(id1, id2, entry);
            ArkEventHunt::Registry::UpdateHints(id1, id2, steam, weapon);

            const float total_hp =
                entry.allowed_hp_damage + entry.other_hp_damage;
            const float ratio =
                total_hp > 0.f ? entry.allowed_hp_damage / total_hp : 0.f;

            Log::GetLog()->info(
                "ArkEventHunt Die: id1={} id2={} steam={} weapon='{}' "
                "mode={} ratio={:.3f} allowedHP={:.1f} otherHP={:.1f} "
                "tameHP={:.1f} torpor={:.1f}",
                id1, id2, steam, weapon, static_cast<int>(entry.mode), ratio,
                entry.allowed_hp_damage, entry.other_hp_damage,
                entry.personal_tame_hp_damage, entry.torpor_hits);

            if (entry.mode == ArkEventHunt::Registry::Mode::ModeA) {
                HandleModeADie(entry, steam, weapon, killer_pc);
            } else if (entry.mode == ArkEventHunt::Registry::Mode::ModeB) {
                HandleModeBDie(entry, steam, DamageCauser, weapon, killer_pc);
            } else if (entry.mode == ArkEventHunt::Registry::Mode::Spike) {
                float spike_ratio = 0.f;
                const bool ratio_ok = WeaponRatioOk(entry, spike_ratio);
                const bool torpor_fail =
                    entry.forbid_torpor && entry.torpor_hits > 0.f;
                Log::GetLog()->info(
                    "ArkEventHunt spike Die: ratio_ok={} ratio={:.3f} "
                    "torpor_fail={} steam={}",
                    ratio_ok && !torpor_fail, spike_ratio, torpor_fail, steam);
            }

            ArkEventHunt::Registry::Unbind(id1, id2);
        } else if (id1 != 0 || id2 != 0) {
            // Dino com IDs mas fora do registry — tipicamente reload mid-fight.
            const uint64_t steam = ArkApi::GetApiUtils().GetAttackerSteamID(
                _this, Killer, DamageCauser, false);
            AShooterPlayerController* killer_pc = nullptr;
            if (Killer &&
                Killer->IsA(AShooterPlayerController::GetPrivateStaticClass())) {
                killer_pc = static_cast<AShooterPlayerController*>(Killer);
            }
            Log::GetLog()->warn(
                "ArkEventHunt Die: dino id1={} id2={} NÃO está no registry "
                "(reload? /eve noutro mapa?) steam={} — claim SPAWNED pode "
                "ficar preso; admin void no site",
                id1, id2, steam);
            NotifyKiller(
                killer_pc, steam,
                ArkEventHunt::HuntConfig::Get().Msg(
                    "EveKillUnknownDino",
                    "Evento: dino morto sem tracking local (plugin reload?). "
                    "Se o claim ficar SPAWNED no site, pede void ao staff."));
        }
    }

    return APrimalDinoCharacter_Die_original(
        _this, KillingDamage, DamageEvent, Killer, DamageCauser);
}

namespace ArkEventHunt {
namespace Hooks {

void Register() {
    ArkApi::GetHooks().SetHook(
        "APrimalDinoCharacter.TakeDamage(float,FDamageEvent*,AController*,AActor*)",
        Hook_APrimalDinoCharacter_TakeDamage,
        &APrimalDinoCharacter_TakeDamage_original);
    ArkApi::GetHooks().SetHook(
        "APrimalDinoCharacter.Die(float,FDamageEvent*,AController*,AActor*)",
        Hook_APrimalDinoCharacter_Die,
        &APrimalDinoCharacter_Die_original);
    Log::GetLog()->info(
        "ArkEventHunt: TakeDamage+Die hooks (Mode A + Mode B)");
}

void Unregister() {
    ArkApi::GetHooks().DisableHook(
        "APrimalDinoCharacter.TakeDamage(float,FDamageEvent*,AController*,AActor*)",
        Hook_APrimalDinoCharacter_TakeDamage);
    ArkApi::GetHooks().DisableHook(
        "APrimalDinoCharacter.Die(float,FDamageEvent*,AController*,AActor*)",
        Hook_APrimalDinoCharacter_Die);
}

} // namespace Hooks
} // namespace ArkEventHunt
