#include "pch.h"
#include "HuntLifecycle.h"
#include "HuntConfig.h"
#include "HuntHttpClient.h"
#include "HuntRegistry.h"
#include "HuntWorld.h"

#include <Timer.h>

namespace {

bool g_timer_started = false;
bool g_stopped = false;

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

void ExpireInstance(const ArkEventHunt::Registry::Entry& entry, bool warn_only) {
    auto& cfg = ArkEventHunt::HuntConfig::Get();
    const std::string name =
        entry.display_name.empty() ? entry.code : entry.display_name;

    if (warn_only) {
        if (!ArkEventHunt::Registry::MarkTtlWarned(entry.dino_id1, entry.dino_id2))
            return;
        std::string msg = cfg.Msg(
            "EveAdmExpireWarn",
            "[Evento] {name} expira em 1 minuto!");
        const auto pos = msg.find("{name}");
        if (pos != std::string::npos)
            msg.replace(pos, 6, name);
        ArkEventHunt::World::BroadcastChat(msg);
        Log::GetLog()->info(
            "ArkEventHunt TTL warn: instance={} name={}",
            entry.instance_id, name);
        return;
    }

    if (!ArkEventHunt::Registry::MarkOutcomeSent(entry.dino_id1, entry.dino_id2))
        return;

    std::string msg = cfg.Msg(
        "EveAdmExpired",
        "[Evento] {name} expirou e foi removido.");
    const auto pos = msg.find("{name}");
    if (pos != std::string::npos)
        msg.replace(pos, 6, name);
    ArkEventHunt::World::BroadcastChat(msg);

    ArkEventHunt::World::DespawnDino(entry.dino_id1, entry.dino_id2);

    if (entry.instance_id > 0) {
        nlohmann::json body = {
            {"dino_id1", entry.dino_id1},
            {"dino_id2", entry.dino_id2},
            {"server_id", entry.server_id},
            {"reason", "ttl"},
            {"idempotency_key",
             "expire:" + std::to_string(entry.instance_id)},
        };
        ArkEventHunt::HttpClient::PostJsonDetached(
            "/api/event-hunt/b/instances/" +
                std::to_string(entry.instance_id) + "/expire",
            body.dump(), 3);
    }

    ArkEventHunt::Registry::Unbind(entry.dino_id1, entry.dino_id2);
    Log::GetLog()->info(
        "ArkEventHunt TTL expire: instance={} id1={} id2={}",
        entry.instance_id, entry.dino_id1, entry.dino_id2);
}

void TtlTick() {
    if (g_stopped) return;
    if (!ArkEventHunt::HuntConfig::Get().ModeBEnabled()) return;

    const int64_t now = ArkEventHunt::World::NowUnix();
    const auto entries = ArkEventHunt::Registry::Snapshot(
        ArkEventHunt::Registry::Mode::ModeB, true);

    for (const auto& e : entries) {
        if (e.expires_at_unix <= 0 || e.outcome_sent) continue;
        const int64_t remaining = e.expires_at_unix - now;
        if (remaining <= 0) {
            ExpireInstance(e, /*warn_only=*/false);
        } else if (remaining <= 60 && !e.ttl_warned) {
            ExpireInstance(e, /*warn_only=*/true);
        }
    }
}

void BindReconciledInstance(const nlohmann::json& row) {
    const uint32_t id1 = static_cast<uint32_t>(JsonInt64(row, "dino_id1", 0));
    const uint32_t id2 = static_cast<uint32_t>(JsonInt64(row, "dino_id2", 0));
    if (id1 == 0 && id2 == 0) return;

    ArkEventHunt::Registry::Entry existing;
    if (ArkEventHunt::Registry::Find(id1, id2, existing))
        return; // already tracked

    // Só rebind se o dino ainda existir no mapa.
    if (!ArkEventHunt::World::FindDinoByIds(id1, id2)) {
        Log::GetLog()->info(
            "ArkEventHunt reconcile: orphan API bind sem actor id1={} id2={} "
            "(deixado para API/admin)",
            id1, id2);
        return;
    }

    auto& cfg = ArkEventHunt::HuntConfig::Get();
    ArkEventHunt::Registry::Entry entry;
    entry.mode = ArkEventHunt::Registry::Mode::ModeB;
    entry.code = JsonStr(row, "event_code", JsonStr(row, "code", ""));
    entry.instance_id = JsonInt64(row, "instance_id", JsonInt64(row, "id", 0));
    entry.public_dino_id = JsonInt64(row, "public_dino_id", 0);
    entry.session_id = JsonInt64(row, "event_session_id",
                                 JsonInt64(row, "session_id", 0));
    entry.display_name = JsonStr(row, "display_name",
                                 JsonStr(row, "name", entry.code));
    entry.server_id = JsonStr(row, "server_id", ResolveServerId());
    entry.dino_id1 = id1;
    entry.dino_id2 = id2;
    entry.min_allowed_weapon_damage_ratio = JsonFloat(
        row, "min_allowed_weapon_damage_ratio",
        cfg.MinAllowedWeaponDamageRatio());
    entry.forbid_torpor = JsonBool(row, "forbid_torpor", cfg.ForbidTorpor());
    entry.official_weapons_only =
        JsonBool(row, "official_weapons_only", cfg.OfficialWeaponsOnly());
    entry.allow_personal_tames = JsonBool(
        row, "allow_personal_tames", cfg.AllowPersonalTamesDefault());
    entry.expires_at_unix = JsonInt64(row, "expires_at_unix", 0);
    if (entry.expires_at_unix <= 0) {
        const int ttl = JsonInt(row, "ttl_sec", 0);
        if (ttl > 0)
            entry.expires_at_unix = ArkEventHunt::World::NowUnix() + ttl;
    }
    entry.ttl_warned = JsonBool(row, "warned_1min", false);

    if (row.contains("allowed_weapons") && row["allowed_weapons"].is_array()) {
        for (const auto& w : row["allowed_weapons"]) {
            if (w.is_string() && !w.get<std::string>().empty())
                entry.allowed_weapons.push_back(w.get<std::string>());
        }
    }
    if (entry.allowed_weapons.empty()) {
        if (entry.official_weapons_only)
            entry.allowed_weapons = cfg.OfficialWeaponCatalog();
        else
            entry.allowed_weapons = cfg.WeaponWhitelist();
    }

    ArkEventHunt::Registry::Bind(entry);
    Log::GetLog()->info(
        "ArkEventHunt reconcile: rebound Mode B instance={} id1={} id2={}",
        entry.instance_id, id1, id2);
}

} // anonymous

namespace ArkEventHunt {
namespace Lifecycle {

void ReconcileOrphans() {
    if (!HuntConfig::Get().ModeBEnabled()) return;

    const std::string server_id = ResolveServerId();
    const std::string map_name = ResolveMapName();
    std::string path =
        "/api/event-hunt/b/instances?status=ALIVE&server_id=" +
        UrlEncode(server_id);
    if (!map_name.empty())
        path += "&map_name=" + UrlEncode(map_name);

    const auto resp = HttpClient::Get(path);
    if (resp.status == 0) {
        Log::GetLog()->warn("ArkEventHunt reconcile: API inacessível");
        return;
    }
    if (resp.status == 404) {
        Log::GetLog()->info(
            "ArkEventHunt reconcile: endpoint instances ainda não disponível "
            "(404) — skip");
        return;
    }
    if (resp.status >= 400 || resp.body.empty()) {
        Log::GetLog()->warn(
            "ArkEventHunt reconcile: HTTP {} — skip", resp.status);
        return;
    }

    try {
        const auto j = nlohmann::json::parse(resp.body);
        nlohmann::json arr = nlohmann::json::array();
        if (j.contains("instances") && j["instances"].is_array())
            arr = j["instances"];
        else if (j.contains("data") && j["data"].is_array())
            arr = j["data"];
        else if (j.is_array())
            arr = j;

        int n = 0;
        for (const auto& row : arr) {
            if (!row.is_object()) continue;
            BindReconciledInstance(row);
            ++n;
        }
        Log::GetLog()->info(
            "ArkEventHunt reconcile: processadas {} instâncias ALIVE", n);
    } catch (const std::exception& e) {
        Log::GetLog()->warn(
            "ArkEventHunt reconcile: parse error: {}", e.what());
    }
}

void Start() {
    g_stopped = false;
    if (!g_timer_started) {
        const int tick = HuntConfig::Get().TtlTickSeconds();
        API::Timer::Get().RecurringExecute(TtlTick, tick, -1, false);
        g_timer_started = true;
        Log::GetLog()->info(
            "ArkEventHunt: TTL timer a cada {}s", tick);
    }

    // Mundo pode ainda não estar pronto — delay curto para reconcile.
    API::Timer::Get().DelayExecute([]() {
        if (!g_stopped)
            ReconcileOrphans();
    }, 8);
}

void Stop() {
    g_stopped = true;
}

} // namespace Lifecycle
} // namespace ArkEventHunt
