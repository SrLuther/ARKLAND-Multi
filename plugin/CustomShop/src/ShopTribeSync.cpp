#include "pch.h"
#include "ShopTribeSync.h"
#include "ShopBridge.h"
#include "ShopConfig.h"
#include "HttpClient.h"

#include <algorithm>
#include <cctype>
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
    // ARK PT: "Proprietário"; EN: "Owner". Não usar "Leader"/"Admin" sozinho —
    // ranks customizados podem chamar-se Leader sem serem o dono.
    if (r == "owner" || r == "proprietario" || r == "founder")
        return true;
    if (r.find("propriet") != std::string::npos)
        return true;
    if (r.find("owner") != std::string::npos)
        return true;
    return false;
}

std::string ResolveServerId() {
    const auto& settings = ShopConfig::Get().Settings();
    std::string id = SanitizeAscii(settings.value("ServerId", ""));
    if (!id.empty()) return id;

    id = SanitizeAscii(ShopConfig::Get().CrossChat().value("ServerId", ""));
    if (!id.empty()) return id;

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
    // Fallback: jogador online com o mesmo LinkedPlayerID
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

} // namespace

void SyncPlayer(AShooterPlayerController* player) {
    if (!player) return;

    const std::string steam_id = Bridge::GetSteamId(player);
    if (steam_id.empty()) {
        Log::GetLog()->warn("TribeSync: steam_id vazio — skip");
        return;
    }

    const std::string server_id = ResolveServerId();
    if (server_id == "unknown") {
        Log::GetLog()->warn(
            "TribeSync: ServerId ausente (Settings.ServerId / CrossChat.ServerId) "
            "— presence com server_id=unknown (steam={})",
            steam_id);
    }

    auto* ps = static_cast<AShooterPlayerState*>(player->PlayerStateField());
    if (!ps) {
        Log::GetLog()->info("TribeSync: sem PlayerState ainda (steam={})", steam_id);
        return;
    }

    FTribeData* tribe = ps->MyTribeDataField();
    if (!tribe) {
        Log::GetLog()->info("TribeSync: sem tribo (steam={})", steam_id);
        return;
    }

    const int tribe_id = tribe->TribeIDField();
    if (tribe_id <= 0) {
        Log::GetLog()->info("TribeSync: TribeID inválido (steam={})", steam_id);
        return;
    }

    const std::string tribe_name = FStringToUtf8(tribe->TribeNameField());
    const unsigned int my_pdid = PlayerDataIdOf(player);
    const unsigned int owner_pdid = tribe->OwnerPlayerDataIDField();

    bool is_owner = (owner_pdid != 0 && my_pdid != 0 && owner_pdid == my_pdid);
    try {
        if (ps->IsTribeOwner(my_pdid))
            is_owner = true;
    } catch (...) {
    }

    const std::string my_rank = RankNameFor(tribe, my_pdid);
    if (!is_owner && RankImpliesOwner(my_rank))
        is_owner = true;

    nlohmann::json members = nlohmann::json::array();
    try {
        const auto& ids = tribe->MembersPlayerDataIDField();
        const auto& names = tribe->MembersPlayerNameField();
        const int n = static_cast<int>(ids.Num());
        for (int i = 0; i < n; ++i) {
            const unsigned int mid = ids[i];
            std::string m_steam = SteamIdForPlayerDataId(mid);
            // Sem SteamID conhecido: ainda reporta o jogador logado
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

    // Garante que o jogador atual aparece na lista
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
        Log::GetLog()->info(
            "TribeSync: presence steam={} server={} tribe_id={} name='{}' "
            "is_owner={} rank='{}' members={} resp_len={}",
            steam_id, server_id, tribe_id, tribe_name,
            is_owner ? "yes" : "no", my_rank, members.size(), resp.size());
    } catch (const std::exception& e) {
        Log::GetLog()->error("TribeSync: POST failed: {}", e.what());
    }
}

} // namespace TribeSync
} // namespace CustomShop
