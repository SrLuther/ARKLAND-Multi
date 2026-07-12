#include "pch.h"
#include "ShopTribeSync.h"
#include "ShopBridge.h"
#include "ShopConfig.h"
#include "HttpClient.h"

#include <Timer.h>
#include <algorithm>
#include <cctype>
#include <memory>
#include <string>

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

} // namespace

bool SyncPlayer(AShooterPlayerController* player) {
    if (!player) {
        Log::GetLog()->warn("TribeSync: player null — skip");
        return false;
    }

    const std::string steam_id = Bridge::GetSteamId(player);
    if (steam_id.empty()) {
        Log::GetLog()->warn("TribeSync: steam_id vazio — skip");
        return false;
    }

    const std::string server_id = ResolveServerId();
    const bool server_id_ok = !IsPlaceholderServerId(server_id);
    if (!server_id_ok) {
        Log::GetLog()->warn(
            "TribeSync: ServerId ausente (Settings.ServerId / CrossChat.ServerId / mapa) "
            "— presence com server_id=unknown (steam={}). "
            "Sincronize CustomShop no TEK para gravar CrossChat.ServerId "
            "(mesmo com CrossChat.Enabled=false).",
            steam_id);
    }

    Log::GetLog()->info(
        "TribeSync: tentativa steam={} server_id={} (ok={})",
        steam_id, server_id, server_id_ok ? "yes" : "no");

    auto* ps = static_cast<AShooterPlayerState*>(player->PlayerStateField());
    if (!ps) {
        Log::GetLog()->info("TribeSync: sem PlayerState ainda (steam={})", steam_id);
        return false;
    }

    FTribeData* tribe = ps->MyTribeDataField();
    if (!tribe) {
        Log::GetLog()->info("TribeSync: sem tribo (steam={})", steam_id);
        return false;
    }

    const int tribe_id = tribe->TribeIDField();
    if (tribe_id <= 0) {
        Log::GetLog()->info("TribeSync: TribeID inválido (steam={})", steam_id);
        return false;
    }

    const std::string tribe_name = FStringToUtf8(tribe->TribeNameField());
    const unsigned int my_pdid = PlayerDataIdOf(player);
    const unsigned int owner_pdid = tribe->OwnerPlayerDataIDField();

    bool is_owner = (owner_pdid != 0 && my_pdid != 0 && owner_pdid == my_pdid);
    try {
        if (my_pdid != 0 && ps->IsTribeOwner(my_pdid))
            is_owner = true;
    } catch (...) {
    }

    const std::string my_rank = RankNameFor(tribe, my_pdid);
    if (!is_owner && RankImpliesOwner(my_rank))
        is_owner = true;

    Log::GetLog()->info(
        "TribeSync: tribe steam={} tribe_id={} name='{}' is_owner={} rank='{}' "
        "pdid={} owner_pdid={}",
        steam_id, tribe_id, tribe_name, is_owner ? "yes" : "no", my_rank,
        my_pdid, owner_pdid);

    nlohmann::json members = nlohmann::json::array();
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
    };

    try {
        const std::string resp =
            HttpClient::PostJson("/api/tribe/presence", body.dump());
        const bool ok = ResponseLooksOk(resp);
        if (ok) {
            Log::GetLog()->info(
                "TribeSync: presence OK steam={} server={} tribe_id={} name='{}' "
                "is_owner={} rank='{}' members={} resp_len={}",
                steam_id, server_id, tribe_id, tribe_name,
                is_owner ? "yes" : "no", my_rank, members.size(), resp.size());
            return true;
        }
        Log::GetLog()->error(
            "TribeSync: POST /api/tribe/presence falhou ou resposta inválida "
            "steam={} server={} tribe_id={} resp_len={} resp_prefix='{}'",
            steam_id, server_id, tribe_id, resp.size(),
            resp.substr(0, std::min<size_t>(resp.size(), 120)));
        return false;
    } catch (const std::exception& e) {
        Log::GetLog()->error("TribeSync: POST failed: {}", e.what());
        return false;
    }
}

void ScheduleSyncAfterLogin(AShooterPlayerController* player) {
    if (!player) {
        Log::GetLog()->warn("TribeSync: ScheduleSyncAfterLogin player null — skip");
        return;
    }

    const std::string steam_id = Bridge::GetSteamId(player);
    // Tentativas escalonadas: a tribo ASE por vezes só está pronta >12s após login.
    // Para no primeiro sucesso — evita 4 POSTs síncronos por login no game thread.
    static constexpr int kDelaysSec[] = {8, 20, 45, 90};
    Log::GetLog()->info(
        "TribeSync: agendado pós-login steam={} delays=8/20/45/90s server_id={}",
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
    // Um POST por tick (1s de intervalo) — N POSTs seguidos no mesmo callback
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

} // namespace TribeSync
} // namespace CustomShop
