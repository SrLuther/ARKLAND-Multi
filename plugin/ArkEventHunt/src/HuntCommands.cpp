#include "pch.h"
#include "HuntCommands.h"
#include "HuntConfig.h"
#include "HuntHttpClient.h"
#include "HuntPerms.h"
#include "HuntRegistry.h"
#include "HuntWorld.h"

namespace {

void SendMsg(AShooterPlayerController* c, const FLinearColor& color,
             const std::string& msg) {
    if (!c || msg.empty()) return;
    ArkApi::GetApiUtils().SendServerMessage(c, color, msg.c_str());
}

bool IsAdminPlayer(AShooterPlayerController* controller) {
    if (!controller) return false;
    if (controller->bIsAdmin()()) return true;
    const uint64 steam = ArkApi::GetApiUtils().GetSteamIdFromController(controller);
    if (steam == 0) return false;
    return ArkEventHunt::Perms::IsInAnyGroup(
        static_cast<uint64_t>(steam),
        ArkEventHunt::HuntConfig::Get().AdminGroups());
}

std::string GetSteamId(AShooterPlayerController* controller) {
    if (!controller) return "";
    const uint64 id = ArkApi::GetApiUtils().GetSteamIdFromController(controller);
    return (id != 0) ? std::to_string(id) : "";
}

std::vector<std::string> SplitCmd(FString* cmd_str) {
    std::vector<std::string> parts;
    if (!cmd_str) return parts;
    const std::string s = cmd_str->ToString();
    std::istringstream ss(s);
    std::string token;
    while (ss >> token)
        parts.push_back(token);
    return parts;
}

std::string FormatIds(const std::string& tpl, uint32_t id1, uint32_t id2) {
    std::string out = tpl;
    auto replace_once = [&](const std::string& needle, const std::string& val) {
        const auto pos = out.find(needle);
        if (pos != std::string::npos)
            out.replace(pos, needle.size(), val);
    };
    replace_once("{}", std::to_string(id1));
    replace_once("{}", std::to_string(id2));
    return out;
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

std::string ResolveServerId() {
    auto& cfg = ArkEventHunt::HuntConfig::Get();
    const std::string configured = cfg.ServerId();
    if (!configured.empty() && configured != "CHANGE_ME")
        return configured;
    try {
        auto* gm = ArkApi::GetApiUtils().GetShooterGameMode();
        if (gm) {
            FString map_name;
            gm->GetMapName(&map_name);
            if (!map_name.IsEmpty())
                return map_name.ToString();
        }
    } catch (...) {
    }
    return "unknown";
}

std::string ResolveMapName() {
    try {
        auto* gm = ArkApi::GetApiUtils().GetShooterGameMode();
        if (gm) {
            FString map_name;
            gm->GetMapName(&map_name);
            if (!map_name.IsEmpty())
                return map_name.ToString();
        }
    } catch (...) {
    }
    return "";
}

nlohmann::json UnwrapData(const nlohmann::json& j) {
    if (j.contains("data") && j["data"].is_object())
        return j["data"];
    return j;
}

bool ParseMembershipActiveTeam(const std::string& steam_id,
                               bool& active,
                               uint64_t& team_id) {
    active = false;
    team_id = 0;
    if (steam_id.empty()) return false;

    const auto resp = ArkEventHunt::HttpClient::Get(
        "/api/teams/plugin/membership/" + UrlEncode(steam_id));
    if (resp.status == 0 || resp.body.empty()) return false;

    try {
        const auto j = nlohmann::json::parse(resp.body);
        const auto data = UnwrapData(j);
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
        return false;
    }
}

void ReadAllowedWeapons(const nlohmann::json& payload,
                        std::vector<std::string>& out) {
    out.clear();
    if (!payload.contains("allowed_weapons") ||
        !payload["allowed_weapons"].is_array())
        return;
    for (const auto& w : payload["allowed_weapons"]) {
        if (w.is_string()) {
            const std::string s = w.get<std::string>();
            if (!s.empty()) out.push_back(s);
        }
    }
}

// Best-effort GiveItem (pattern CustomShop): deliver official weapon on /eve.
bool GiveOfficialWeapon(AShooterPlayerController* controller,
                        const std::string& blueprint,
                        int quantity) {
    if (!controller || blueprint.empty() || quantity < 1)
        return false;
    FString fbp(blueprint.c_str());
    UClass* item_class = UVictoryCore::BPLoadClass(&fbp);
    if (!item_class) {
        Log::GetLog()->warn(
            "ArkEventHunt GiveWeapon: BPLoadClass failed '{}'", blueprint);
        return false;
    }
    UPrimalInventoryComponent* inv = controller->GetPlayerInventoryComponent();
    if (!inv) {
        Log::GetLog()->warn("ArkEventHunt GiveWeapon: no inventory");
        return false;
    }
    UPrimalItem::AddNewItem(
        TSubclassOf<UPrimalItem>(item_class),
        inv,
        false,
        false,
        0.0f,
        true,
        quantity,
        false,
        0.0f,
        false,
        TSubclassOf<UPrimalItem>(),
        0.0f,
        false,
        false);
    Log::GetLog()->info(
        "ArkEventHunt GiveWeapon: delivered qty={} bp={}", quantity, blueprint);
    return true;
}

// SPIKE only: SpawnDino wild + bind IDs.
void CmdEveSpike(AShooterPlayerController* controller, FString* cmd,
                 EChatSendMode::Type) {
    if (!controller) return;
    auto& cfg = ArkEventHunt::HuntConfig::Get();
    if (!cfg.SpikeEnabled()) {
        SendMsg(controller, FColorList::Yellow,
                cfg.Msg("NotImplemented",
                        "ArkEventHunt: spike desligado no config."));
        return;
    }
    if (!IsAdminPlayer(controller)) {
        SendMsg(controller, FColorList::Red,
                cfg.Msg("NoPermission", "Sem permissão."));
        return;
    }

    const auto parts = SplitCmd(cmd);
    std::string bp = cfg.SpikeDefaultBlueprint();
    int level = cfg.SpikeDefaultLevel();
    size_t i = 0;
    if (parts.size() > i &&
        (parts[i] == "/evespike" || parts[i] == "evespike"))
        ++i;
    if (parts.size() > i &&
        (parts[i] == "spawn" || parts[i] == "s"))
        ++i;
    if (parts.size() > i && parts[i].find("Blueprint'") != std::string::npos) {
        bp = parts[i];
        ++i;
    }
    if (parts.size() > i) {
        try {
            level = std::stoi(parts[i]);
        } catch (...) {
        }
    }

    FString fbp(bp.c_str());
    APrimalDinoCharacter* dino = ArkApi::GetApiUtils().SpawnDino(
        controller, fbp, nullptr, level, /*force_tame=*/false,
        /*neutered=*/false);
    if (!dino) {
        SendMsg(controller, FColorList::Red,
                cfg.Msg("SpikeSpawnFail", "Spike: falha ao spawnar."));
        Log::GetLog()->error("ArkEventHunt spike: SpawnDino failed bp={}", bp);
        return;
    }

    int raw1 = 0;
    int raw2 = 0;
    dino->GetDinoIDs(&raw1, &raw2);
    const uint32_t id1 = static_cast<uint32_t>(raw1);
    const uint32_t id2 = static_cast<uint32_t>(raw2);

    ArkEventHunt::Registry::Entry entry;
    entry.mode = ArkEventHunt::Registry::Mode::Spike;
    entry.code = "SPIKE";
    entry.dino_id1 = id1;
    entry.dino_id2 = id2;
    entry.allowed_weapons = cfg.SpikeWeaponWhitelist();
    entry.min_allowed_weapon_damage_ratio = cfg.MinAllowedWeaponDamageRatio();
    entry.forbid_torpor = cfg.ForbidTorpor();
    entry.official_weapons_only = cfg.OfficialWeaponsOnly();
    if (!ArkEventHunt::Registry::Bind(entry)) {
        Log::GetLog()->warn(
            "ArkEventHunt spike: GetDinoIDs returned 0/0 — ver timing no ASE");
    }

    const std::string ok = FormatIds(
        cfg.Msg("SpikeSpawnOk", "Spike: dino spawnado (wild) id1={} id2={}"),
        id1, id2);
    SendMsg(controller, FColorList::Green, ok);
    Log::GetLog()->info(
        "ArkEventHunt spike spawn bp={} lvl={} id1={} id2={} tracked={}",
        bp, level, id1, id2, ArkEventHunt::Registry::Count());
}

// Mode A — /eve <code>: só o owner do claim; spawn wild ao lado; bind + HTTP.
void CmdEve(AShooterPlayerController* controller, FString* cmd,
            EChatSendMode::Type) {
    if (!controller) return;
    auto& cfg = ArkEventHunt::HuntConfig::Get();

    if (!cfg.Enabled() || !cfg.ModeAEnabled()) {
        SendMsg(controller, FColorList::Yellow,
                cfg.Msg("Disabled", "ArkEventHunt desligado."));
        return;
    }

    const auto parts = SplitCmd(cmd);
    size_t i = 0;
    if (parts.size() > i && (parts[i] == "/eve" || parts[i] == "eve"))
        ++i;

    if (parts.size() <= i) {
        SendMsg(controller, FColorList::Yellow,
                cfg.Msg("EveUsage",
                        "Uso: /eve <código> — só o dono do claim no site."));
        return;
    }

    const std::string code = parts[i];
    const std::string steam = GetSteamId(controller);
    if (steam.empty()) {
        SendMsg(controller, FColorList::Red,
                cfg.Msg("NoSteam", "SteamID inválido."));
        return;
    }

    if (ArkEventHunt::Registry::HasActiveClaimForOwner(steam)) {
        SendMsg(controller, FColorList::Yellow,
                cfg.Msg("EveAlreadyActive",
                        "Já tens um dino de evento activo neste mapa."));
        return;
    }

    bool member_active = false;
    uint64_t member_team = 0;
    if (!ParseMembershipActiveTeam(steam, member_active, member_team) ||
        !member_active || member_team == 0) {
        SendMsg(controller, FColorList::Red,
                cfg.Msg("EveNotActiveMember",
                        "Precisas de ser membro ACTIVE de uma Equipe no site."));
        return;
    }

    const std::string path =
        "/api/event-hunt/a/claims/by-code/" + UrlEncode(code) +
        "?steam_id=" + UrlEncode(steam);
    const auto claim_resp = ArkEventHunt::HttpClient::Get(path);
    if (claim_resp.status == 0) {
        SendMsg(controller, FColorList::Red,
                cfg.Msg("EveApiDown",
                        "API Event Hunt inacessível. Tenta mais tarde."));
        return;
    }
    if (claim_resp.status == 404 || claim_resp.body.empty()) {
        SendMsg(controller, FColorList::Red,
                cfg.Msg("EveCodeInvalid", "Código inválido ou expirado."));
        return;
    }
    if (claim_resp.status >= 400) {
        SendMsg(controller, FColorList::Red,
                cfg.Msg("EveCodeRejected",
                        "Código rejeitado pela API Event Hunt."));
        return;
    }

    nlohmann::json payload;
    try {
        const auto j = nlohmann::json::parse(claim_resp.body);
        payload = UnwrapData(j);
        if (j.contains("ok") && j["ok"].is_boolean() && !j["ok"].get<bool>()) {
            SendMsg(controller, FColorList::Red,
                    cfg.Msg("EveCodeRejected",
                            "Código rejeitado pela API Event Hunt."));
            return;
        }
    } catch (...) {
        SendMsg(controller, FColorList::Red,
                cfg.Msg("EveApiBad", "Resposta inválida da API Event Hunt."));
        return;
    }

    const std::string owner = JsonStr(payload, "owner_steam_id", "");
    if (owner.empty() || owner != steam) {
        SendMsg(controller, FColorList::Red,
                cfg.Msg("EveNotOwner",
                        "Só o dono do claim pode usar /eve com este código."));
        return;
    }

    const uint64_t claim_team = [&]() -> uint64_t {
        if (!payload.contains("team_id") || payload["team_id"].is_null())
            return 0;
        if (payload["team_id"].is_number())
            return payload["team_id"].get<uint64_t>();
        if (payload["team_id"].is_string()) {
            try {
                return static_cast<uint64_t>(
                    std::stoull(payload["team_id"].get<std::string>()));
            } catch (...) {
                return 0;
            }
        }
        return 0;
    }();

    if (claim_team == 0 || claim_team != member_team) {
        SendMsg(controller, FColorList::Red,
                cfg.Msg("EveTeamMismatch",
                        "A tua Equipe no site não corresponde ao claim."));
        return;
    }

    const std::string status = JsonStr(payload, "status", "CLAIMED");
    if (!status.empty() && status != "CLAIMED") {
        SendMsg(controller, FColorList::Yellow,
                cfg.Msg("EveBadStatus",
                        "Este claim já não está disponível para spawn."));
        return;
    }

    const int64_t claim_id = [&]() -> int64_t {
        if (payload.contains("claim_id") && payload["claim_id"].is_number())
            return payload["claim_id"].get<int64_t>();
        if (payload.contains("id") && payload["id"].is_number())
            return payload["id"].get<int64_t>();
        return 0;
    }();
    if (claim_id <= 0) {
        SendMsg(controller, FColorList::Red,
                cfg.Msg("EveApiBad", "Resposta inválida da API Event Hunt."));
        return;
    }

    const std::string bp = JsonStr(payload, "blueprint", "");
    if (bp.empty()) {
        SendMsg(controller, FColorList::Red,
                cfg.Msg("EveNoBlueprint", "Claim sem blueprint."));
        return;
    }
    const int level = JsonInt(payload, "level", 150);

    std::vector<std::string> allowed;
    ReadAllowedWeapons(payload, allowed);
    if (allowed.empty()) {
        if (JsonBool(payload, "official_weapons_only", cfg.OfficialWeaponsOnly()))
            allowed = cfg.OfficialWeaponCatalog();
        else
            allowed = cfg.WeaponWhitelist();
    }

    const float min_ratio = JsonFloat(
        payload, "min_allowed_weapon_damage_ratio",
        cfg.MinAllowedWeaponDamageRatio());
    const bool forbid_torpor =
        JsonBool(payload, "forbid_torpor", cfg.ForbidTorpor());
    const bool official_only =
        JsonBool(payload, "official_weapons_only", cfg.OfficialWeaponsOnly());

    FString fbp(bp.c_str());
    APrimalDinoCharacter* dino = ArkApi::GetApiUtils().SpawnDino(
        controller, fbp, nullptr, level, /*force_tame=*/false,
        /*neutered=*/false);
    if (!dino) {
        SendMsg(controller, FColorList::Red,
                cfg.Msg("EveSpawnFail", "Falha ao spawnar o dino de evento."));
        Log::GetLog()->error(
            "ArkEventHunt /eve: SpawnDino failed claim={} bp={}", claim_id, bp);
        return;
    }

    int raw1 = 0;
    int raw2 = 0;
    dino->GetDinoIDs(&raw1, &raw2);
    const uint32_t id1 = static_cast<uint32_t>(raw1);
    const uint32_t id2 = static_cast<uint32_t>(raw2);
    const std::string server_id = ResolveServerId();
    const std::string map_name = ResolveMapName();

    nlohmann::json spawned_body = {
        {"dino_id1", id1},
        {"dino_id2", id2},
        {"steam_id", steam},
        {"server_id", server_id},
        {"map_name", map_name},
    };

    const auto spawned_resp = ArkEventHunt::HttpClient::PostJsonRetry(
        "/api/event-hunt/a/claims/" + std::to_string(claim_id) + "/spawned",
        spawned_body.dump(), 3);
    if (spawned_resp.status == 0 || spawned_resp.status >= 400) {
        // Dino já existe — regista localmente mesmo assim e avisa.
        Log::GetLog()->error(
            "ArkEventHunt /eve: bind HTTP failed claim={} status={}",
            claim_id, spawned_resp.status);
        SendMsg(controller, FColorList::Yellow,
                cfg.Msg("EveBindWarn",
                        "Dino spawnado, mas bind na API falhou — contacta staff."));
    }

    ArkEventHunt::Registry::Entry entry;
    entry.mode = ArkEventHunt::Registry::Mode::ModeA;
    entry.code = code;
    entry.claim_id = claim_id;
    entry.challenge_id = JsonInt(payload, "challenge_id", 0);
    entry.team_id = claim_team;
    entry.owner_steam_id = owner;
    entry.server_id = server_id;
    entry.allowed_weapons = allowed;
    entry.min_allowed_weapon_damage_ratio =
        (min_ratio < 0.f) ? 0.f : (min_ratio > 1.f ? 1.f : min_ratio);
    entry.forbid_torpor = forbid_torpor;
    entry.official_weapons_only = official_only;
    entry.dino_id1 = id1;
    entry.dino_id2 = id2;
    if (!ArkEventHunt::Registry::Bind(entry)) {
        Log::GetLog()->warn(
            "ArkEventHunt /eve: GetDinoIDs 0/0 claim={} — ver timing ASE",
            claim_id);
    }

    // Optional: deliver the official challenge weapon so everyone starts equal.
    if (JsonBool(payload, "grant_weapon_on_start", true)) {
        std::string grant_bp =
            JsonStr(payload, "grant_weapon_blueprint", "");
        if (grant_bp.empty()) {
            for (const auto& w : allowed) {
                if (!w.empty() && w.rfind("tag:", 0) != 0) {
                    grant_bp = w;
                    break;
                }
            }
        }
        const int grant_qty = std::max(1, JsonInt(payload, "grant_weapon_qty", 1));
        if (!grant_bp.empty()) {
            if (GiveOfficialWeapon(controller, grant_bp, grant_qty)) {
                SendMsg(controller, FColorList::Green,
                        cfg.Msg("EveWeaponGranted",
                                "Arma oficial do desafio entregue no inventário."));
            } else {
                SendMsg(controller, FColorList::Yellow,
                        cfg.Msg("EveWeaponGrantFail",
                                "Não foi possível entregar a arma — usa a oficial da whitelist."));
            }
        }
    }

    const std::string ok = FormatIds(
        cfg.Msg("EveSpawnOk",
                "Evento: dino spawnado! Mata com a arma permitida. id1={} id2={}"),
        id1, id2);
    SendMsg(controller, FColorList::Green, ok);
    Log::GetLog()->info(
        "ArkEventHunt /eve OK claim={} code={} steam={} team={} id1={} id2={} "
        "minRatio={:.2f} forbidTorpor={} officialOnly={} grant={}",
        claim_id, code, steam, claim_team, id1, id2,
        entry.min_allowed_weapon_damage_ratio, forbid_torpor, official_only,
        JsonBool(payload, "grant_weapon_on_start", true));
}

// Mode B — /eveadm <code>: admin Permissions → claim-summon Catálogo B → spawn → bind PUBLIC.
void CmdEveAdm(AShooterPlayerController* controller, FString* cmd,
               EChatSendMode::Type) {
    if (!controller) return;
    auto& cfg = ArkEventHunt::HuntConfig::Get();

    if (!IsAdminPlayer(controller)) {
        SendMsg(controller, FColorList::Red,
                cfg.Msg("NoPermission", "Sem permissão."));
        return;
    }

    if (!cfg.Enabled() || !cfg.ModeBEnabled()) {
        SendMsg(controller, FColorList::Yellow,
                cfg.Msg("Disabled", "ArkEventHunt desligado."));
        return;
    }

    const auto parts = SplitCmd(cmd);
    size_t i = 0;
    if (parts.size() > i &&
        (parts[i] == "/eveadm" || parts[i] == "eveadm"))
        ++i;

    if (parts.size() <= i) {
        SendMsg(controller, FColorList::Yellow,
                cfg.Msg("EveAdmUsage",
                        "Uso: /eveadm <código> | /eveadm status"));
        return;
    }

    if (parts[i] == "status" || parts[i] == "list") {
        const auto alive = ArkEventHunt::Registry::Snapshot(
            ArkEventHunt::Registry::Mode::ModeB, true);
        if (alive.empty()) {
            SendMsg(controller, FColorList::Yellow,
                    cfg.Msg("EveAdmStatusEmpty",
                            "Mode B: nenhum dino vivo neste mapa."));
            return;
        }
        SendMsg(controller, FColorList::Green,
                "Mode B vivos: " + std::to_string(alive.size()) +
                    " (A=" +
                    std::to_string(ArkEventHunt::Registry::CountMode(
                        ArkEventHunt::Registry::Mode::ModeA)) +
                    ")");
        for (const auto& e : alive) {
            const int64_t rem =
                e.expires_at_unix > 0
                    ? (e.expires_at_unix - ArkEventHunt::World::NowUnix())
                    : -1;
            std::string line = "  #" + std::to_string(e.instance_id) + " " +
                               (e.display_name.empty() ? e.code : e.display_name) +
                               " ids=" + std::to_string(e.dino_id1) + "/" +
                               std::to_string(e.dino_id2);
            if (rem >= 0)
                line += " ttl=" + std::to_string(rem) + "s";
            else
                line += " ttl=∞";
            SendMsg(controller, FColorList::White, line);
        }
        return;
    }

    const std::string code = parts[i];
    const std::string steam = GetSteamId(controller);
    if (steam.empty()) {
        SendMsg(controller, FColorList::Red,
                cfg.Msg("NoSteam", "SteamID inválido."));
        return;
    }

    const std::string path =
        "/api/event-hunt/b/codes/" + UrlEncode(code);
    const auto code_resp = ArkEventHunt::HttpClient::Get(path);
    if (code_resp.status == 0) {
        SendMsg(controller, FColorList::Red,
                cfg.Msg("EveApiDown",
                        "API Event Hunt inacessível. Tenta mais tarde."));
        return;
    }
    if (code_resp.status == 404 || code_resp.body.empty()) {
        SendMsg(controller, FColorList::Red,
                cfg.Msg("EveAdmCodeInvalid",
                        "Código Mode B inválido ou sessão inactiva."));
        return;
    }
    if (code_resp.status >= 400) {
        SendMsg(controller, FColorList::Red,
                cfg.Msg("EveAdmCodeRejected",
                        "Código Mode B rejeitado pela API."));
        return;
    }

    nlohmann::json payload;
    try {
        const auto j = nlohmann::json::parse(code_resp.body);
        payload = UnwrapData(j);
        if (j.contains("ok") && j["ok"].is_boolean() && !j["ok"].get<bool>()) {
            SendMsg(controller, FColorList::Red,
                    cfg.Msg("EveAdmCodeRejected",
                            "Código Mode B rejeitado pela API."));
            return;
        }
    } catch (...) {
        SendMsg(controller, FColorList::Red,
                cfg.Msg("EveApiBad", "Resposta inválida da API Event Hunt."));
        return;
    }

    const std::string session_status =
        JsonStr(payload, "session_status", "ACTIVE");
    if (session_status == "DRAFT" || session_status == "CLOSED" ||
        session_status == "CLOSING" ||
        session_status == "OPEN_INSCRIPTION") {
        SendMsg(controller, FColorList::Yellow,
                cfg.Msg("EveAdmSessionClosed",
                        "Sessão Mode B não está ACTIVE para summon."));
        return;
    }

    const std::string bp = JsonStr(payload, "blueprint", "");
    if (bp.empty()) {
        SendMsg(controller, FColorList::Red,
                cfg.Msg("EveNoBlueprint", "Claim sem blueprint."));
        return;
    }
    const int level = JsonInt(payload, "level", 150);
    const int64_t public_dino_id = JsonInt64(payload, "public_dino_id", 0);
    const int64_t session_id = JsonInt64(
        payload, "event_session_id", JsonInt64(payload, "session_id", 0));
    const std::string display = JsonStr(
        payload, "display_name", JsonStr(payload, "name", code));

    std::vector<std::string> allowed;
    ReadAllowedWeapons(payload, allowed);
    if (allowed.empty()) {
        if (JsonBool(payload, "official_weapons_only", cfg.OfficialWeaponsOnly()))
            allowed = cfg.OfficialWeaponCatalog();
        else
            allowed = cfg.WeaponWhitelist();
    }

    const float min_ratio = JsonFloat(
        payload, "min_allowed_weapon_damage_ratio",
        cfg.MinAllowedWeaponDamageRatio());
    const bool forbid_torpor =
        JsonBool(payload, "forbid_torpor", cfg.ForbidTorpor());
    const bool official_only =
        JsonBool(payload, "official_weapons_only", cfg.OfficialWeaponsOnly());
    const bool allow_tames = JsonBool(
        payload, "allow_personal_tames", cfg.AllowPersonalTamesDefault());
    const int ttl_sec = JsonInt(payload, "ttl_sec", 0);
    int64_t expires_at = JsonInt64(payload, "expires_at_unix", 0);
    if (expires_at <= 0 && ttl_sec > 0)
        expires_at = ArkEventHunt::World::NowUnix() + ttl_sec;

    FString fbp(bp.c_str());
    APrimalDinoCharacter* dino = ArkApi::GetApiUtils().SpawnDino(
        controller, fbp, nullptr, level, /*force_tame=*/false,
        /*neutered=*/false);
    if (!dino) {
        SendMsg(controller, FColorList::Red,
                cfg.Msg("EveAdmSpawnFail",
                        "Falha ao spawnar o dino Mode B."));
        Log::GetLog()->error(
            "ArkEventHunt /eveadm: SpawnDino failed code={} bp={}", code, bp);
        return;
    }

    int raw1 = 0;
    int raw2 = 0;
    dino->GetDinoIDs(&raw1, &raw2);
    const uint32_t id1 = static_cast<uint32_t>(raw1);
    const uint32_t id2 = static_cast<uint32_t>(raw2);
    const std::string server_id = ResolveServerId();
    const std::string map_name = ResolveMapName();

    nlohmann::json spawned_body = {
        {"event_code", code},
        {"public_dino_id", public_dino_id},
        {"event_session_id", session_id},
        {"dino_id1", id1},
        {"dino_id2", id2},
        {"admin_steam_id", steam},
        {"server_id", server_id},
        {"map_name", map_name},
        {"mode", "PUBLIC"},
        {"ttl_sec", ttl_sec},
        {"expires_at_unix", expires_at},
        {"display_name", display},
    };

    const auto spawned_resp = ArkEventHunt::HttpClient::PostJsonRetry(
        "/api/event-hunt/b/instances/spawned", spawned_body.dump(), 3);

    int64_t instance_id = 0;
    if (spawned_resp.status == 0 || spawned_resp.status >= 400) {
        Log::GetLog()->error(
            "ArkEventHunt /eveadm: bind HTTP failed code={} status={}",
            code, spawned_resp.status);
        SendMsg(controller, FColorList::Yellow,
                cfg.Msg("EveAdmBindWarn",
                        "Dino spawnado, mas bind Mode B na API falhou — "
                        "contacta staff."));
    } else {
        try {
            const auto j = nlohmann::json::parse(spawned_resp.body);
            const auto data = UnwrapData(j);
            instance_id = JsonInt64(data, "instance_id",
                                    JsonInt64(data, "id", 0));
            const int64_t api_exp =
                JsonInt64(data, "expires_at_unix", 0);
            if (api_exp > 0) expires_at = api_exp;
        } catch (...) {
        }
    }

    ArkEventHunt::Registry::Entry entry;
    entry.mode = ArkEventHunt::Registry::Mode::ModeB;
    entry.code = code;
    entry.instance_id = instance_id;
    entry.public_dino_id = public_dino_id;
    entry.session_id = session_id;
    entry.display_name = display;
    entry.owner_steam_id = steam; // admin que summonou (auditoria)
    entry.server_id = server_id;
    entry.allowed_weapons = allowed;
    entry.min_allowed_weapon_damage_ratio =
        (min_ratio < 0.f) ? 0.f : (min_ratio > 1.f ? 1.f : min_ratio);
    entry.forbid_torpor = forbid_torpor;
    entry.official_weapons_only = official_only;
    entry.allow_personal_tames = allow_tames;
    entry.dino_id1 = id1;
    entry.dino_id2 = id2;
    entry.expires_at_unix = expires_at;
    if (!ArkEventHunt::Registry::Bind(entry)) {
        Log::GetLog()->warn(
            "ArkEventHunt /eveadm: GetDinoIDs 0/0 code={} — ver timing ASE",
            code);
    }

    const std::string ok = FormatIds(
        cfg.Msg("EveAdmSpawnOk",
                "Mode B: {name} spawnado (PUBLIC) id1={} id2={}"),
        id1, id2);
    std::string msg = ok;
    const auto npos = msg.find("{name}");
    if (npos != std::string::npos)
        msg.replace(npos, 6, display);
    SendMsg(controller, FColorList::Green, msg);

    if (expires_at > 0) {
        const int64_t rem = expires_at - ArkEventHunt::World::NowUnix();
        SendMsg(controller, FColorList::Yellow,
                "TTL: " + std::to_string(rem) +
                    "s (aviso chat a T-60s).");
    }

    Log::GetLog()->info(
        "ArkEventHunt /eveadm OK instance={} code={} admin={} id1={} id2={} "
        "ttl={} tames={} minRatio={:.2f} A={} B={}",
        instance_id, code, steam, id1, id2, expires_at, allow_tames,
        entry.min_allowed_weapon_damage_ratio,
        ArkEventHunt::Registry::CountMode(ArkEventHunt::Registry::Mode::ModeA),
        ArkEventHunt::Registry::CountMode(ArkEventHunt::Registry::Mode::ModeB));
}

void CmdAdminReload(APlayerController* pc, FString*, bool) {
    auto* admin = static_cast<AShooterPlayerController*>(pc);
    try {
        ArkEventHunt::HuntConfig::Get().Load();
        if (admin)
            SendMsg(admin, FColorList::Green, "ArkEventHunt config reloaded.");
        Log::GetLog()->info("ArkEventHunt: config reloaded");
    } catch (const std::exception& e) {
        const std::string err = std::string("Reload failed: ") + e.what();
        Log::GetLog()->error("{}", err);
        if (admin) SendMsg(admin, FColorList::Red, err);
    }
}

} // anonymous

namespace ArkEventHunt {
namespace Commands {

void Register() {
    ArkApi::GetCommands().AddConsoleCommand("EventHunt.Reload", &CmdAdminReload);
    ArkApi::GetCommands().AddChatCommand("/evespike", &CmdEveSpike);
    ArkApi::GetCommands().AddChatCommand("/eve", &CmdEve);
    ArkApi::GetCommands().AddChatCommand("/eveadm", &CmdEveAdm);
    Log::GetLog()->info(
        "ArkEventHunt: commands (/evespike, /eve Mode A, /eveadm Mode B, "
        "EventHunt.Reload)");
}

void Unregister() {
    ArkApi::GetCommands().RemoveConsoleCommand("EventHunt.Reload");
    ArkApi::GetCommands().RemoveChatCommand("/evespike");
    ArkApi::GetCommands().RemoveChatCommand("/eve");
    ArkApi::GetCommands().RemoveChatCommand("/eveadm");
}

} // namespace Commands
} // namespace ArkEventHunt
