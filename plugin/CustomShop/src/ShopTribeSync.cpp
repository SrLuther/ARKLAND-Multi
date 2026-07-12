#include "pch.h"
#include "ShopTribeSync.h"
#include "ShopBridge.h"
#include "ShopConfig.h"
#include "ShopPoints.h"
#include "HttpClient.h"
#include "ShopDebug.h"

#include <Timer.h>
#include <algorithm>
#include <cctype>
#include <memory>
#include <string>
#include <vector>

namespace CustomShop {
namespace TribeSync {
namespace {

std::string SanitizeAscii(const std::string& in) {
    std::string out;
    out.reserve(in.size());
    for (unsigned char ch : in) {
        if (ch >= 32 && ch <= 126)
            out.push_back(static_cast<char>(ch));
        else if (ch == '\t')
            out.push_back(' ');
    }
    while (!out.empty() && (out.front() == ' ' || out.front() == '\t'))
        out.erase(out.begin());
    while (!out.empty() && (out.back() == ' ' || out.back() == '\t'))
        out.pop_back();
    return out;
}

std::string ToLowerAscii(std::string s) {
    for (char& c : s) {
        if (static_cast<unsigned char>(c) <= 127)
            c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    }
    return s;
}

bool RankImpliesOwner(const std::string& rank) {
    const std::string r = ToLowerAscii(SanitizeAscii(rank));
    if (r.empty()) return false;
    // ARK PT: "Proprietário" → SanitizeAscii remove acento → "proprietrio";
    // EN: "Owner". Não usar "Leader"/"Admin" sozinho.
    if (r == "owner" || r == "proprietario" || r == "founder")
        return true;
    if (r.find("propriet") != std::string::npos)
        return true;
    if (r.find("owner") != std::string::npos)
        return true;
    return false;
}

bool IsPlaceholderServerId(const std::string& id) {
    const std::string lower = ToLowerAscii(id);
    return lower.empty() || lower == "unknown" || lower == "server";
}

std::string CurrentMapName() {
    try {
        const auto& utils = ArkApi::GetApiUtils();
        if (utils.GetStatus() != ArkApi::ServerStatus::Ready)
            return "";
        AShooterGameMode* gm = utils.GetShooterGameMode();
        if (!gm) return "";
        FString map_name;
        gm->GetMapName(&map_name);
        return SanitizeAscii(map_name.ToString());
    } catch (...) {
        return "";
    }
}

/// ServerId independente de CrossChat.Enabled — TribeSync precisa do ID do mapa
/// mesmo com chat cluster off (plugin de terceiros).
std::string ResolveServerId() {
    const auto& settings = ShopConfig::Get().Settings();
    std::string id = SanitizeAscii(settings.value("ServerId", ""));
    if (!IsPlaceholderServerId(id)) return id;

    // CrossChat.ServerId continua a ser a fonte TEK por mapa (mesmo Enabled=false).
    id = SanitizeAscii(ShopConfig::Get().CrossChat().value("ServerId", ""));
    if (!IsPlaceholderServerId(id)) return id;

    id = CurrentMapName();
    if (!IsPlaceholderServerId(id)) return id;

    return "unknown";
}

std::string FStringToUtf8(const FString& fs) {
    if (fs.IsEmpty()) return "";
    return SanitizeAscii(fs.ToString());
}

unsigned int PlayerDataIdOf(AShooterPlayerController* player) {
    if (!player) return 0;
    const uint64 linked = ArkApi::GetApiUtils().GetPlayerID(player);
    if (linked != 0 && linked != static_cast<uint64>(-1))
        return static_cast<unsigned int>(linked);
    try {
        return static_cast<unsigned int>(player->GetLinkedPlayerID());
    } catch (...) {
        return 0;
    }
}

std::string SteamIdForPlayerDataId(unsigned int player_data_id) {
    if (player_data_id == 0) return "";
    try {
        const uint64 sid = ArkApi::GetApiUtils().GetSteamIDForPlayerID(
            static_cast<int>(player_data_id));
        if (sid != 0) return std::to_string(sid);
    } catch (...) {
    }
    const auto& pcs =
        ArkApi::GetApiUtils().GetWorld()->PlayerControllerListField();
    for (TWeakObjectPtr<APlayerController> wpc : pcs) {
        auto* sc = static_cast<AShooterPlayerController*>(wpc.Get());
        if (!sc) continue;
        if (static_cast<unsigned int>(ArkApi::GetApiUtils().GetPlayerID(sc))
            == player_data_id) {
            return Bridge::GetSteamId(sc);
        }
    }
    return "";
}

std::string RankNameFor(FTribeData* tribe, unsigned int player_data_id) {
    if (!tribe || player_data_id == 0) return "";
    try {
        FString result;
        tribe->GetRankNameForPlayerID(&result, player_data_id);
        return FStringToUtf8(result);
    } catch (...) {
        return "";
    }
}

/// ASE: MyTribeDataField() pode ser NULL mesmo com o jogador numa tribo.
/// GetTribeId / TargetingTeam são fontes alternativas para o TribeID.
FTribeData* ResolveTribeData(AShooterPlayerState* ps) {
    if (!ps) return nullptr;

    try {
        if (FTribeData* t = ps->MyTribeDataField()) {
            if (t->TribeIDField() > 0) return t;
        }
    } catch (...) {
    }

    return nullptr;
}

int ResolveTribeId(
    AShooterPlayerState* ps,
    AShooterPlayerController* player,
    FTribeData* tribe) {
    if (tribe) {
        try {
            const int id = tribe->TribeIDField();
            if (id > 0) return id;
        } catch (...) {
        }
    }

    if (ps) {
        try {
            const int id = ps->GetTribeId();
            if (id > 0) return id;
        } catch (...) {
        }
        try {
            // Em ASE TargetingTeam == TribeID para membros de tribo.
            const int id = ps->TargetingTeamField();
            if (id > 0) return id;
        } catch (...) {
        }
    }

    if (player) {
        try {
            const int id = player->TargetingTeamField();
            if (id > 0) return id;
        } catch (...) {
        }
    }
    return 0;
}

std::string ResolveTribeName(
    AShooterPlayerController* player,
    FTribeData* tribe) {
    if (tribe) {
        try {
            const std::string n = FStringToUtf8(tribe->TribeNameField());
            if (!n.empty()) return n;
        } catch (...) {
        }
    }
    if (player) {
        if (AShooterCharacter* ch = player->GetPlayerCharacter()) {
            try {
                const std::string n = FStringToUtf8(ch->TribeNameField());
                if (!n.empty()) return n;
            } catch (...) {
            }
        }
    }
    return "";
}

bool ResponseLooksOk(const std::string& resp) {
    if (resp.empty()) return false;
    // Resposta típica: {"ok":true} — evita marcar sucesso em 401/HTML/vazio.
    return resp.find("\"ok\"") != std::string::npos
        && resp.find("true") != std::string::npos
        && resp.find("\"ok\":false") == std::string::npos
        && resp.find("\"ok\": false") == std::string::npos;
}

AShooterPlayerController* ResolveOnlinePlayer(
    AShooterPlayerController* preferred,
    const std::string& steam_id) {
    if (!steam_id.empty()) {
        if (AShooterPlayerController* by_sid = Bridge::FindPlayer(steam_id))
            return by_sid;
    }
    if (!preferred) return nullptr;
    try {
        const auto& pcs =
            ArkApi::GetApiUtils().GetWorld()->PlayerControllerListField();
        for (TWeakObjectPtr<APlayerController> wpc : pcs) {
            if (static_cast<AShooterPlayerController*>(wpc.Get()) == preferred)
                return preferred;
        }
    } catch (...) {
    }
    return nullptr;
}

MYSQL* Db() {
    return ShopPoints::Get().GetDb();
}

bool EscapeSql(MYSQL* db, const std::string& in, std::string& out) {
    if (!db) {
        out = in;
        return false;
    }
    if (in.empty()) {
        out.clear();
        return true;
    }
    std::vector<char> buf(in.size() * 2 + 1);
    const unsigned long len = mysql_real_escape_string(
        db, buf.data(), in.c_str(), static_cast<unsigned long>(in.size()));
    out.assign(buf.data(), len);
    return true;
}

bool ExecSql(MYSQL* db, const std::string& sql) {
    if (!db) return false;
    if (mysql_query(db, sql.c_str()) != 0) {
        Log::GetLog()->warn(
            "TribeSync MySQL: {} — {}", mysql_error(db), sql.substr(0, 160));
        return false;
    }
    return true;
}

void UpsertMemberDb(
    MYSQL* db,
    const std::string& server_id,
    int tribe_id,
    const std::string& tribe_name,
    const nlohmann::json& member) {
    std::string esc_sid, esc_srv, esc_tn, esc_cn, esc_rn;
    const std::string sid = member.value("steam_id", "");
    if (sid.empty()) return;
    if (!EscapeSql(db, sid, esc_sid) ||
        !EscapeSql(db, server_id, esc_srv) ||
        !EscapeSql(db, tribe_name, esc_tn))
        return;
    EscapeSql(db, member.value("character_name", ""), esc_cn);
    EscapeSql(db, member.value("rank_name", ""), esc_rn);
    const int is_owner = member.value("is_owner", false) ? 1 : 0;

    const std::string sql =
        "INSERT INTO tribe_members "
        "(server_id, tribe_id, tribe_name, steam_id, character_name, is_owner, "
        "rank_name, joined_at, last_seen_at, updated_at) VALUES ('" +
        esc_srv + "', " + std::to_string(tribe_id) + ", '" + esc_tn + "', '" +
        esc_sid + "', '" + esc_cn + "', " + std::to_string(is_owner) + ", '" +
        esc_rn + "', UTC_TIMESTAMP(6), UTC_TIMESTAMP(6), UTC_TIMESTAMP(6)) "
        "ON DUPLICATE KEY UPDATE character_name=VALUES(character_name), "
        "is_owner=VALUES(is_owner), rank_name=VALUES(rank_name), "
        "tribe_name=VALUES(tribe_name), last_seen_at=UTC_TIMESTAMP(6), "
        "updated_at=UTC_TIMESTAMP(6)";
    ExecSql(db, sql);
}

void AutoLinkOwnerDb(
    MYSQL* db,
    const std::string& steam_id,
    const std::string& server_id,
    int tribe_id,
    const std::string& tribe_name) {
    if (IsPlaceholderServerId(server_id) || tribe_id <= 0) return;
    std::string esc_sid, esc_srv, esc_tn;
    if (!EscapeSql(db, steam_id, esc_sid) ||
        !EscapeSql(db, server_id, esc_srv) ||
        !EscapeSql(db, tribe_name.empty() ? ("Tribo " + std::to_string(tribe_id)) : tribe_name, esc_tn))
        return;

    // Se a web já tem outro proprietário para esta (server_id, tribe_id),
    // trata o sync actual como membro — não sobrescreve o dono.
    {
        const std::string check =
            "SELECT o.steam_id FROM tribe_map_links l "
            "JOIN tribe_owners o ON o.id = l.tribe_owner_id "
            "WHERE l.server_id = '" + esc_srv + "' AND l.tribe_id = " +
            std::to_string(tribe_id) + " AND l.is_active = 1 "
            "ORDER BY l.confirmed_at ASC LIMIT 1";
        if (mysql_query(db, check.c_str()) == 0) {
            MYSQL_RES* cres = mysql_store_result(db);
            if (cres) {
                MYSQL_ROW crow = mysql_fetch_row(cres);
                if (crow && crow[0] && steam_id != crow[0]) {
                    Log::GetLog()->info(
                        "TribeSync: auto-link skip — tribo {}@{} já tem dono web {} "
                        "(sync={})",
                        tribe_id, server_id, crow[0], steam_id);
                    mysql_free_result(cres);
                    return;
                }
                mysql_free_result(cres);
            }
        }
    }

    const std::string sel =
        "SELECT id FROM tribe_owners WHERE steam_id = '" + esc_sid + "' LIMIT 1";
    if (mysql_query(db, sel.c_str()) != 0) return;
    MYSQL_RES* res = mysql_store_result(db);
    if (!res) return;
    MYSQL_ROW row = mysql_fetch_row(res);
    if (!row || !row[0]) {
        mysql_free_result(res);
        return;
    }
    const std::string owner_id = row[0];
    mysql_free_result(res);

    const std::string link =
        "INSERT INTO tribe_map_links "
        "(tribe_owner_id, server_id, tribe_id, tribe_name_local, tribe_type, "
        "is_active, confirmed_at) VALUES (" +
        owner_id + ", '" + esc_srv + "', " + std::to_string(tribe_id) + ", '" +
        esc_tn + "', 'principal', 1, UTC_TIMESTAMP(6)) "
        "ON DUPLICATE KEY UPDATE tribe_id=VALUES(tribe_id), "
        "tribe_name_local=VALUES(tribe_name_local), "
        "confirmed_at=UTC_TIMESTAMP(6)";
    ExecSql(db, link);
}

/// Grava presença nas tabelas que a web já lê (caminho principal, sem RCON).
bool WritePresenceDb(
    const std::string& steam_id,
    const std::string& server_id,
    int tribe_id,
    const std::string& tribe_name,
    bool is_owner,
    const std::string& member_rank,
    const nlohmann::json& members,
    const std::string& source) {
    MYSQL* db = Db();
    if (!db) return false;

    std::string esc_sid, esc_srv, esc_tn, esc_mr, esc_src;
    if (!EscapeSql(db, steam_id, esc_sid) ||
        !EscapeSql(db, server_id, esc_srv) ||
        !EscapeSql(db, tribe_name, esc_tn) ||
        !EscapeSql(db, member_rank, esc_mr) ||
        !EscapeSql(db, source, esc_src))
        return false;

    const std::string sql =
        "INSERT INTO tribe_presences "
        "(steam_id, server_id, map_name, tribe_id, tribe_name, is_owner, "
        "member_rank, captured_at, source) VALUES ('" +
        esc_sid + "', '" + esc_srv + "', '" + esc_srv + "', " +
        std::to_string(tribe_id) + ", '" + esc_tn + "', " +
        (is_owner ? "1" : "0") + ", '" + esc_mr +
        "', UTC_TIMESTAMP(6), '" + esc_src + "')";
    if (!ExecSql(db, sql)) return false;

    if (members.is_array()) {
        for (const auto& m : members)
            UpsertMemberDb(db, server_id, tribe_id, tribe_name, m);
    }
    if (is_owner)
        AutoLinkOwnerDb(db, steam_id, server_id, tribe_id, tribe_name);

    Log::GetLog()->info(
        "TribeSync: presence MySQL OK steam={} server={} tribe_id={} is_owner={}",
        steam_id, server_id, tribe_id, is_owner ? "yes" : "no");
    return true;
}

bool PostPresenceHttp(const nlohmann::json& body) {
    try {
        const std::string resp =
            HttpClient::PostJson("/api/tribe/presence", body.dump());
        return ResponseLooksOk(resp);
    } catch (const std::exception& e) {
        Log::GetLog()->warn("TribeSync: HTTP presence failed: {}", e.what());
        return false;
    } catch (...) {
        Log::GetLog()->warn("TribeSync: HTTP presence failed: unknown");
        return false;
    }
}

struct PendingSyncClaim {
    uint64_t request_id = 0;
    std::string steam_id;
};

std::vector<PendingSyncClaim> ClaimPendingSyncRequestsDb(
    const std::vector<std::string>& online_steam_ids,
    const std::string& server_id) {
    std::vector<PendingSyncClaim> out;
    MYSQL* db = Db();
    if (!db || online_steam_ids.empty() || IsPlaceholderServerId(server_id))
        return out;

    // Expira pedidos antigos (mesmo TTL da web).
    ExecSql(db,
        "UPDATE tribe_sync_requests SET status='expired' "
        "WHERE status IN ('pending','claimed') AND expires_at < UTC_TIMESTAMP(6)");

    std::string esc_srv;
    if (!EscapeSql(db, server_id, esc_srv)) return out;

    for (const auto& sid : online_steam_ids) {
        if (sid.empty()) continue;
        std::string esc_sid;
        if (!EscapeSql(db, sid, esc_sid)) continue;
        const std::string sel =
            "SELECT id FROM tribe_sync_requests "
            "WHERE steam_id='" + esc_sid +
            "' AND status='pending' AND expires_at >= UTC_TIMESTAMP(6) "
            "ORDER BY requested_at ASC LIMIT 1";
        if (mysql_query(db, sel.c_str()) != 0) continue;
        MYSQL_RES* res = mysql_store_result(db);
        if (!res) continue;
        MYSQL_ROW row = mysql_fetch_row(res);
        if (!row || !row[0]) {
            mysql_free_result(res);
            continue;
        }
        uint64_t req_id = 0;
        try { req_id = std::stoull(row[0]); } catch (...) { req_id = 0; }
        mysql_free_result(res);
        if (req_id == 0) continue;

        const std::string upd =
            "UPDATE tribe_sync_requests SET status='claimed', "
            "claimed_at=UTC_TIMESTAMP(6), claimed_by_server_id='" + esc_srv +
            "' WHERE id=" + std::to_string(req_id) + " AND status='pending'";
        if (!ExecSql(db, upd)) continue;
        if (mysql_affected_rows(db) <= 0) continue;
        out.push_back({req_id, sid});
    }
    return out;
}

void CompleteSyncRequestDb(uint64_t request_id, bool ok, const std::string& error) {
    MYSQL* db = Db();
    if (!db || request_id == 0) return;
    if (ok) {
        ExecSql(db,
            "UPDATE tribe_sync_requests SET status='done', "
            "completed_at=UTC_TIMESTAMP(6), last_error=NULL WHERE id=" +
            std::to_string(request_id));
        return;
    }
    std::string esc_err;
    EscapeSql(db, error.empty() ? "sync_failed" : error, esc_err);
    ExecSql(db,
        "UPDATE tribe_sync_requests SET status='pending', "
        "claimed_at=NULL, claimed_by_server_id=NULL, last_error='" + esc_err +
        "' WHERE id=" + std::to_string(request_id) +
        " AND expires_at >= UTC_TIMESTAMP(6)");
}

} // namespace

bool SyncPlayer(AShooterPlayerController* player) {
    Debug::Fields f;
    f.correlation_id = Debug::NewCorrelationId();

    if (!player) {
        Log::GetLog()->warn("TribeSync: player null — skip");
        Debug::Warn("TribeSync", f, "skip: player null");
        return false;
    }

    const std::string steam_id = Bridge::GetSteamId(player);
    f.steam_id = steam_id;
    if (steam_id.empty()) {
        Log::GetLog()->warn("TribeSync: steam_id vazio — skip");
        Debug::Warn("TribeSync", f, "skip: steam_id vazio");
        return false;
    }

    const std::string server_id = ResolveServerId();
    f.server_id = server_id;
    const bool server_id_ok = !IsPlaceholderServerId(server_id);
    if (!server_id_ok) {
        Log::GetLog()->warn(
            "TribeSync: ServerId ausente (Settings.ServerId / CrossChat.ServerId / mapa) "
            "— presence com server_id=unknown (steam={}). "
            "Sincronize CustomShop no TEK para gravar CrossChat.ServerId "
            "(mesmo com CrossChat.Enabled=false).",
            steam_id);
        f.extra["reason"] = "server_id_placeholder";
        Debug::Warn("TribeSync", f, "ServerId ausente — presence com unknown");
    }

    Log::GetLog()->info(
        "TribeSync: tentativa steam={} server_id={} (ok={})",
        steam_id, server_id, server_id_ok ? "yes" : "no");
    Debug::Info("TribeSync", f,
                std::string("tentativa server_ok=") + (server_id_ok ? "yes" : "no"));

    auto* ps = static_cast<AShooterPlayerState*>(player->PlayerStateField());
    if (!ps) {
        Log::GetLog()->info("TribeSync: sem PlayerState ainda (steam={})", steam_id);
        Debug::Info("TribeSync", f, "skip: sem PlayerState ainda");
        return false;
    }

    FTribeData* tribe = ResolveTribeData(ps);
    const int tribe_id = ResolveTribeId(ps, player, tribe);
    if (tribe_id <= 0) {
        Log::GetLog()->info(
            "TribeSync: sem tribo / TribeID inválido (steam={} my_tribe={} "
            "get_tribe_id/targeting=0)",
            steam_id, tribe ? "ptr" : "null");
        f.extra["my_tribe"] = tribe ? "ptr" : "null";
        Debug::Info("TribeSync", f, "skip: sem tribo / TribeID invalido");
        return false;
    }

    const std::string tribe_name = ResolveTribeName(player, tribe);
    const unsigned int my_pdid = PlayerDataIdOf(player);
    unsigned int owner_pdid = 0;
    if (tribe) {
        try {
            owner_pdid = tribe->OwnerPlayerDataIDField();
        } catch (...) {
        }
    }

    bool is_owner = (owner_pdid != 0 && my_pdid != 0 && owner_pdid == my_pdid);
    try {
        if (my_pdid != 0 && ps->IsTribeOwner(my_pdid))
            is_owner = true;
    } catch (...) {
    }

    const std::string my_rank = RankNameFor(tribe, my_pdid);
    if (!is_owner && RankImpliesOwner(my_rank))
        is_owner = true;

    // Sem FTribeData completo mas GetTribeId/IsTribeOwner OK — ainda enviamos presença.
    // Se IsTribeOwner falhar e não houver rank, marca owner=false (API ainda grava presença).
    Log::GetLog()->info(
        "TribeSync: tribe steam={} tribe_id={} name='{}' is_owner={} rank='{}' "
        "pdid={} owner_pdid={} tribe_ptr={}",
        steam_id, tribe_id, tribe_name, is_owner ? "yes" : "no", my_rank,
        my_pdid, owner_pdid, tribe ? "yes" : "no");
    f.extra = {
        {"tribe_id", tribe_id},
        {"tribe_name", tribe_name},
        {"is_owner", is_owner},
        {"rank", my_rank},
        {"tribe_ptr", tribe != nullptr},
    };
    Debug::LogDebug("TribeSync", f, "tribe resolvida");

    nlohmann::json members = nlohmann::json::array();
    if (tribe) {
        try {
            const auto& ids = tribe->MembersPlayerDataIDField();
            const auto& names = tribe->MembersPlayerNameField();
            const int n = static_cast<int>(ids.Num());
            for (int i = 0; i < n; ++i) {
                const unsigned int mid = ids[i];
                std::string m_steam = SteamIdForPlayerDataId(mid);
                if (m_steam.empty() && mid == my_pdid)
                    m_steam = steam_id;
                if (m_steam.empty())
                    continue;

                std::string char_name;
                if (i < static_cast<int>(names.Num()))
                    char_name = FStringToUtf8(names[i]);

                const std::string rank = RankNameFor(tribe, mid);
                const bool m_owner =
                    (owner_pdid != 0 && mid == owner_pdid) || RankImpliesOwner(rank);

                members.push_back({
                    {"steam_id", m_steam},
                    {"character_name", char_name},
                    {"is_owner", m_owner},
                    {"rank_name", rank},
                });
            }
        } catch (const std::exception& e) {
            Log::GetLog()->warn("TribeSync: members parse failed: {}", e.what());
        }
    }

    bool self_listed = false;
    for (const auto& m : members) {
        if (m.value("steam_id", "") == steam_id) {
            self_listed = true;
            break;
        }
    }
    if (!self_listed) {
        std::string char_name;
        if (AShooterCharacter* ch = player->GetPlayerCharacter()) {
            try {
                char_name = FStringToUtf8(ch->PlayerNameField());
            } catch (...) {
            }
        }
        members.push_back({
            {"steam_id", steam_id},
            {"character_name", char_name},
            {"is_owner", is_owner},
            {"rank_name", my_rank},
        });
    }

    nlohmann::json body = {
        {"steam_id", steam_id},
        {"server_id", server_id},
        {"map_name", server_id},
        {"tribe_id", tribe_id},
        {"tribe_name", tribe_name},
        {"is_owner", is_owner},
        {"member_rank", my_rank},
        {"members", members},
        {"source", "plugin_sync"},
    };

    // Caminho principal: MySQL (mesma DB que a web lê). HTTP é redundância.
    const bool db_ok = WritePresenceDb(
        steam_id, server_id, tribe_id, tribe_name, is_owner, my_rank,
        members, "plugin_db");
    bool http_ok = false;
    try {
        http_ok = PostPresenceHttp(body);
        if (http_ok) {
            Log::GetLog()->info(
                "TribeSync: presence HTTP OK steam={} server={} tribe_id={} "
                "is_owner={} members={}",
                steam_id, server_id, tribe_id,
                is_owner ? "yes" : "no", members.size());
        }
    } catch (const std::exception& e) {
        Log::GetLog()->warn("TribeSync: HTTP presence exception: {}", e.what());
    }

    if (db_ok || http_ok) {
        Log::GetLog()->info(
            "TribeSync: presence OK steam={} server={} tribe_id={} name='{}' "
            "is_owner={} db={} http={}",
            steam_id, server_id, tribe_id, tribe_name,
            is_owner ? "yes" : "no",
            db_ok ? "yes" : "no", http_ok ? "yes" : "no");
        f.extra["db_ok"] = db_ok;
        f.extra["http_ok"] = http_ok;
        f.extra["tribe_id"] = tribe_id;
        Debug::Info("TribeSync", f, "presence OK");
        return true;
    }

    Log::GetLog()->error(
        "TribeSync: presença falhou (MySQL e HTTP) steam={} server={} tribe_id={}",
        steam_id, server_id, tribe_id);
    f.extra["tribe_id"] = tribe_id;
    f.extra["db_ok"] = false;
    f.extra["http_ok"] = false;
    Debug::Error("TribeSync", f, "presenca falhou (MySQL e HTTP)");
    return false;
}

void ScheduleSyncAfterLogin(AShooterPlayerController* player) {
    if (!player) {
        Log::GetLog()->warn("TribeSync: ScheduleSyncAfterLogin player null — skip");
        return;
    }

    const std::string steam_id = Bridge::GetSteamId(player);
    // Tentativas escalonadas: MyTribeData pode demorar; GetTribeId por vezes já
    // está pronto cedo. Inclui 2s para RCON/Verificar-de-novo e retries longos.
    static constexpr int kDelaysSec[] = {2, 8, 20, 45, 90};
    Log::GetLog()->info(
        "TribeSync: agendado pós-login steam={} delays=2/8/20/45/90s server_id={}",
        steam_id.empty() ? "(vazio)" : steam_id,
        ResolveServerId());

    auto done = std::make_shared<bool>(false);
    for (int delay : kDelaysSec) {
        AShooterPlayerController* raw = player;
        const std::string sid = steam_id;
        API::Timer::Get().DelayExecute([raw, sid, delay, done]() {
            if (*done) {
                Log::GetLog()->info(
                    "TribeSync: skip delay {}s — já sincronizado (steam={})",
                    delay, sid.empty() ? "?" : sid);
                return;
            }
            AShooterPlayerController* live = ResolveOnlinePlayer(raw, sid);
            if (!live) {
                Log::GetLog()->warn(
                    "TribeSync: skip delay {}s — jogador offline / PC inválido "
                    "(steam={})",
                    delay, sid.empty() ? "?" : sid);
                return;
            }
            try {
                Log::GetLog()->info(
                    "TribeSync: executando delay {}s (steam={})",
                    delay, sid.empty() ? "?" : sid);
                if (SyncPlayer(live)) {
                    *done = true;
                    Log::GetLog()->info(
                        "TribeSync: sync ok após {}s (steam={})",
                        delay, Bridge::GetSteamId(live));
                } else {
                    Log::GetLog()->info(
                        "TribeSync: delay {}s sem sucesso — próxima tentativa "
                        "se agendada (steam={})",
                        delay, sid.empty() ? "?" : sid);
                }
            } catch (const std::exception& e) {
                Log::GetLog()->error(
                    "TribeSync delay {}s failed: {}", delay, e.what());
            } catch (...) {
                Log::GetLog()->error("TribeSync delay {}s failed: unknown", delay);
            }
        }, delay);
    }
}

void SyncAllOnlinePlayers() {
    // Um sync por tick (1s de intervalo) — N POSTs seguidos no mesmo callback
    // bloqueavam o game thread o suficiente para o HangWatcher se a API atrasasse.
    try {
        const auto& pcs =
            ArkApi::GetApiUtils().GetWorld()->PlayerControllerListField();
        int scheduled = 0;
        for (TWeakObjectPtr<APlayerController> wpc : pcs) {
            auto* sc = static_cast<AShooterPlayerController*>(wpc.Get());
            if (!sc) continue;
            AShooterPlayerController* raw = sc;
            const std::string sid = Bridge::GetSteamId(sc);
            const int delay_sec = scheduled;
            ++scheduled;
            API::Timer::Get().DelayExecute([raw, sid]() {
                AShooterPlayerController* live = ResolveOnlinePlayer(raw, sid);
                if (!live) {
                    Log::GetLog()->warn(
                        "TribeSync online: skip — offline (steam={})",
                        sid.empty() ? "?" : sid);
                    return;
                }
                try {
                    SyncPlayer(live);
                } catch (const std::exception& e) {
                    Log::GetLog()->warn("TribeSync online: {}", e.what());
                } catch (...) {
                    Log::GetLog()->warn("TribeSync online: unknown error");
                }
            }, delay_sec);
        }
        Log::GetLog()->info(
            "TribeSync: SyncAllOnlinePlayers scheduled_count={} server_id={}",
            scheduled, ResolveServerId());
    } catch (const std::exception& e) {
        Log::GetLog()->error("TribeSync: SyncAllOnlinePlayers failed: {}", e.what());
    }
}

void PollPendingSyncRequests() {
    // «Verificar de novo» na web cria tribe_sync_requests — plugin puxa da MySQL.
    try {
        const std::string server_id = ResolveServerId();
        if (IsPlaceholderServerId(server_id)) {
            static bool warned_sid = false;
            if (!warned_sid) {
                warned_sid = true;
                Log::GetLog()->warn(
                    "TribeSync: PollPendingSyncRequests skip — ServerId inválido "
                    "(Settings.ServerId / CrossChat.ServerId / mapa). "
                    "Sincronize CustomShop no TEK.");
            }
            return;
        }

        if (!Db()) {
            static bool warned_db = false;
            if (!warned_db) {
                warned_db = true;
                Log::GetLog()->warn(
                    "TribeSync: PollPendingSyncRequests skip — MySQL offline "
                    "(mesma DB da web? Database.Host/Password no config do mapa)");
                Debug::Fields f;
                f.server_id = server_id;
                Debug::Error("TribeSync", f, "poll skip: MySQL offline");
            }
            return;
        }

        std::vector<std::string> online;
        const auto& pcs =
            ArkApi::GetApiUtils().GetWorld()->PlayerControllerListField();
        for (TWeakObjectPtr<APlayerController> wpc : pcs) {
            auto* sc = static_cast<AShooterPlayerController*>(wpc.Get());
            if (!sc) continue;
            const std::string sid = Bridge::GetSteamId(sc);
            if (!sid.empty()) online.push_back(sid);
        }
        if (online.empty()) return;

        const auto claims = ClaimPendingSyncRequestsDb(online, server_id);
        if (claims.empty()) return;

        Log::GetLog()->info(
            "TribeSync: pull sync-requests claimed={} server_id={}",
            claims.size(), server_id);

        int delay = 0;
        for (const auto& claim : claims) {
            const uint64_t req_id = claim.request_id;
            const std::string sid = claim.steam_id;
            API::Timer::Get().DelayExecute([req_id, sid]() {
                AShooterPlayerController* live = ResolveOnlinePlayer(nullptr, sid);
                if (!live) {
                    CompleteSyncRequestDb(req_id, false, "player_offline");
                    Log::GetLog()->warn(
                        "TribeSync: sync-request {} offline steam={}",
                        req_id, sid);
                    return;
                }
                bool ok = false;
                try {
                    ok = SyncPlayer(live);
                } catch (const std::exception& e) {
                    Log::GetLog()->warn(
                        "TribeSync: sync-request {} failed: {}", req_id, e.what());
                } catch (...) {
                    Log::GetLog()->warn(
                        "TribeSync: sync-request {} failed: unknown", req_id);
                }
                CompleteSyncRequestDb(
                    req_id, ok, ok ? "" : "sync_player_failed");
            }, delay);
            ++delay;
        }
    } catch (const std::exception& e) {
        Log::GetLog()->error(
            "TribeSync: PollPendingSyncRequests failed: {}", e.what());
    }
}

} // namespace TribeSync
} // namespace CustomShop
