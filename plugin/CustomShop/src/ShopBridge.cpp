#include "pch.h"
#include "ShopBridge.h"
#include "ShopConfig.h"
#include "ShopData.h"
#include "ShopPoints.h"
#include "HttpClient.h"

namespace CustomShop {
namespace Bridge {

std::string GetSteamId(AShooterPlayerController* controller) {
    if (!controller) return "";
    const uint64 id = ArkApi::GetApiUtils().GetSteamIdFromController(controller);
    return (id != 0) ? std::to_string(id) : "";
}

AShooterPlayerController* FindPlayer(const std::string& steam_id) {
    if (steam_id.empty()) return nullptr;
    const auto& controllers =
        ArkApi::GetApiUtils().GetWorld()->PlayerControllerListField();
    for (TWeakObjectPtr<APlayerController> wpc : controllers) {
        auto* sc = static_cast<AShooterPlayerController*>(wpc.Get());
        if (sc && GetSteamId(sc) == steam_id)
            return sc;
    }
    return nullptr;
}

// ── Legacy stubs — MX-E Ark Shop UI não é mais necessário ─────────

APrimalBuff* GetOrAddShopBuff(AShooterPlayerController* /*controller*/) {
    return nullptr;
}

bool SendInitData(AShooterPlayerController* /*controller*/,
                  const nlohmann::json& /*shop_data*/,
                  int /*points*/) {
    return false;
}

bool SendPointsRefresh(AShooterPlayerController* /*controller*/, int /*points*/) {
    return false;
}

bool SendStashRefresh(AShooterPlayerController* /*controller*/,
                      const nlohmann::json& /*stash*/) {
    return false;
}

bool SendPayload(AShooterPlayerController* /*controller*/,
                 const nlohmann::json& /*payload*/) {
    return false;
}

bool SendPayload(const std::string& steam_id,
                 const nlohmann::json& payload) {
    return SendPayload(FindPlayer(steam_id), payload);
}

// ── Diagnostics ──────────────────────────────────────────────────

void DiagnosePlayer(AShooterPlayerController* player,
                    AShooterPlayerController* admin) {
    auto notify = [&](FLinearColor col, float dur, const wchar_t* msg) {
        ArkApi::GetApiUtils().SendNotification(admin, col, 1.2f, dur, nullptr, msg);
    };

    if (!player) {
        notify({1, 0, 0, 1}, 8.f, L"[DBG] FAIL: player ptr null");
        return;
    }

    const std::string sid = GetSteamId(player);
    {
        const std::wstring msg = sid.empty()
            ? L"[DBG] FAIL: SteamID vazio"
            : L"[DBG] SteamID: " + std::wstring(sid.begin(), sid.end());
        notify(sid.empty() ? FLinearColor{1, 0, 0, 1} : FLinearColor{0, 1, 0.5f, 1},
               10.f, msg.c_str());
    }

    auto* character = static_cast<APrimalCharacter*>(player->GetPlayerCharacter());
    if (!character) {
        notify({1, 0.4f, 0, 1}, 8.f, L"[DBG] FAIL: personagem nao spawnou");
        return;
    }

    const int pts = sid.empty() ? 0 : ShopPoints::Get().GetPoints(sid);
    notify({0, 1, 1, 1}, 6.f,
           (L"[DBG] Pontos: " + std::to_wstring(pts)).c_str());

    const auto& cfg = ShopConfig::Get();
    notify({0, 1, 0, 1}, 6.f,
           (L"[DBG] Itens: " + std::to_wstring(cfg.Items().size())
            + L" | Kits: " + std::to_wstring(cfg.Kits().size())).c_str());

    const std::string web_url = cfg.WebApiUrl();
    notify({1, 1, 0, 1}, 8.f,
           (L"[DBG] Web API: " + std::wstring(web_url.begin(), web_url.end())).c_str());

    notify({1, 1, 0, 1}, 5.f, L"[DBG] Verificando entregas pendentes...");
    const bool delivered = HttpClient::DeliverPending(player);
    notify(delivered ? FLinearColor{0, 1, 0, 1} : FLinearColor{1, 0.4f, 0, 1},
           8.f, delivered ? L"[DBG] Entregas pendentes processadas"
                          : L"[DBG] Nenhuma entrega pendente ou falha na API");
}

} // namespace Bridge
} // namespace CustomShop
