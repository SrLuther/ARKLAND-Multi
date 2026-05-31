#include "pch.h"
#include "ShopBridge.h"
#include "ShopConfig.h"
#include "ShopData.h"
namespace {
    constexpr const char* kShopBuffPath =
        "Blueprint'/Game/Mods/FC_ArkShopUI/Assets/ArkShopUI_Buff_FCAS.ArkShopUI_Buff_FCAS'";

    // ── Low-level ProcessEvent helpers ───────────────────────────────

    // Call a UFunction with no parameters.
    bool CallNoParam(APrimalBuff* buff, const char* fn_name) {
        if (!buff) return false;
        UFunction* fn = buff->ClassField()->FindFunctionByName(
            FName(fn_name), EIncludeSuperFlag::IncludeSuper);
        if (!fn) {
            Log::GetLog()->warn("ShopBridge: function '{}' not found on buff", fn_name);
            return false;
        }
        buff->ProcessEvent(fn, nullptr);
        Log::GetLog()->info("ShopBridge: called {}()", fn_name);
        return true;
    }

    // Call a UFunction with a single FString parameter.
    bool CallFString(APrimalBuff* buff, const char* fn_name,
                     const std::string& utf8_value) {
        if (!buff) return false;
        UFunction* fn = buff->ClassField()->FindFunctionByName(
            FName(fn_name), EIncludeSuperFlag::IncludeSuper);
        if (!fn) {
            Log::GetLog()->warn("ShopBridge: function '{}' not found on buff", fn_name);
            return false;
        }
        struct { FString Value; } params;
        params.Value = FString(ArkApi::Tools::Utf8Decode(utf8_value));
        buff->ProcessEvent(fn, &params);
        Log::GetLog()->info("ShopBridge: called {}({} chars)", fn_name,
                            utf8_value.size());
        return true;
    }

    // Call a UFunction with a single int32 parameter.
    bool CallInt32(APrimalBuff* buff, const char* fn_name, int32 value) {
        if (!buff) return false;
        UFunction* fn = buff->ClassField()->FindFunctionByName(
            FName(fn_name), EIncludeSuperFlag::IncludeSuper);
        if (!fn) {
            Log::GetLog()->warn("ShopBridge: function '{}' not found on buff", fn_name);
            return false;
        }
        struct { int32 Value; } params;
        params.Value = value;
        buff->ProcessEvent(fn, &params);
        Log::GetLog()->info("ShopBridge: called {}({})", fn_name, value);
        return true;
    }

} // anonymous namespace

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

APrimalBuff* GetOrAddShopBuff(AShooterPlayerController* controller) {
    if (!controller) return nullptr;

    auto* character =
        static_cast<APrimalCharacter*>(controller->GetPlayerCharacter());
    if (!character) {
        Log::GetLog()->warn("ShopBridge: GetOrAddShopBuff — player has no character");
        return nullptr;
    }

    FString buff_path(kShopBuffPath);
    UClass* buff_class = UVictoryCore::BPLoadClass(&buff_path);
    if (!buff_class) {
        Log::GetLog()->error("ShopBridge: Failed to load buff class");
        return nullptr;
    }
    Log::GetLog()->info("ShopBridge: buff class loaded OK");

    TSubclassOf<APrimalBuff> subclass(buff_class);
    if (APrimalBuff* existing = character->GetBuff(subclass)) {
        Log::GetLog()->info("ShopBridge: reusing existing buff");
        return existing;
    }

    APrimalBuff* buff = APrimalBuff::StaticAddBuff(subclass, character,
                                                    nullptr, controller, true);
    if (buff)
        Log::GetLog()->info("ShopBridge: buff applied");
    else
        Log::GetLog()->error("ShopBridge: StaticAddBuff returned null");
    return buff;
}

// ── Specific mod RPCs ─────────────────────────────────────────────

bool SendInitData(AShooterPlayerController* controller,
                  const nlohmann::json& shop_data,
                  int points) {
    if (!controller) return false;

    APrimalBuff* buff = GetOrAddShopBuff(controller);
    if (!buff) {
        ArkApi::GetApiUtils().SendNotification(
            controller, FLinearColor(1, 0, 0, 1), 1.2f, 8.f, nullptr,
            L"[Shop] ERRO: buff nao aplicado");
        return false;
    }

    const auto& cfg = ShopConfig::Get();

    // 1. Set the hotkey the mod should listen on
    const bool keyOk = CallFString(buff, "SetUiKey", cfg.UiKey());
    ArkApi::GetApiUtils().SendNotification(
        controller, FLinearColor(0, 1, 1, 1), 1.0f, 4.f, nullptr,
        keyOk ? L"[Shop] SetUiKey OK" : L"[Shop] SetUiKey FALHOU");

    // 2. Send shop items + kits as raw JSON
    const std::string shop_raw = shop_data.dump();
    const bool dataOk = CallFString(buff, "ROC_ShopDataReceived", shop_raw);
    ArkApi::GetApiUtils().SendNotification(
        controller, FLinearColor(0, 1, 0, 1), 1.2f, 6.f, nullptr,
        dataOk ? L"[Shop] ROC_ShopDataReceived OK" : L"[Shop] ROC_ShopDataReceived FALHOU");

    // 3. Send player point balance
    CallInt32(buff, "ROC_GetPointsReturn", points);

    // 4. Signal server initialised — called LAST so mod has data before activating UI
    CallNoParam(buff, "OnServerInitFinished");

    return dataOk;
}

bool SendPointsRefresh(AShooterPlayerController* controller, int points) {
    if (!controller) return false;
    APrimalBuff* buff = GetOrAddShopBuff(controller);
    return CallInt32(buff, "ROC_GetPointsReturn", points);
}

bool SendStashRefresh(AShooterPlayerController* controller,
                      const nlohmann::json& stash) {
    if (!controller) return false;
    APrimalBuff* buff = GetOrAddShopBuff(controller);
    return CallFString(buff, "FCAS_OnStashReceived", stash.dump());
}

// ── Legacy generic payload (kept for buy/sell result responses) ───

bool SendPayload(AShooterPlayerController* controller,
                 const nlohmann::json& payload) {
    // For now, buy/sell responses are sent as points refresh only.
    // Full per-command RPC mapping can be added once the shop is working.
    const std::string cmd = payload.value("Command", "");
    Log::GetLog()->debug("ShopBridge: SendPayload cmd='{}' (legacy)", cmd);

    APrimalBuff* buff = GetOrAddShopBuff(controller);
    if (!buff) return false;

    // For point-related responses, refresh the balance.
    if (payload.contains("Result") && payload["Result"].contains("Point")) {
        int pts = payload["Result"]["Point"].get<int>();
        return CallInt32(buff, "ROC_GetPointsReturn", pts);
    }
    return true;
}

bool SendPayload(const std::string& steam_id,
                 const nlohmann::json& payload) {
    return SendPayload(FindPlayer(steam_id), payload);
}

// ── Diagnostics ──────────────────────────────────────────────────

void DiagnosePlayer(AShooterPlayerController* player,
                    AShooterPlayerController* admin) {
    // All output via SendNotification — the only channel confirmed to work.
    auto notify = [&](FLinearColor col, float dur, const wchar_t* msg) {
        ArkApi::GetApiUtils().SendNotification(admin, col, 1.2f, dur, nullptr, msg);
    };

    // 1. Player pointer
    if (!player) {
        notify({1,0,0,1}, 8.f, L"[DBG] FAIL: player ptr null");
        return;
    }

    // 2. Steam ID
    const std::string sid = GetSteamId(player);
    {
        const std::wstring msg = sid.empty()
            ? L"[DBG] FAIL: SteamID vazio"
            : L"[DBG] SteamID: " + std::wstring(sid.begin(), sid.end());
        notify(sid.empty() ? FLinearColor{1,0,0,1} : FLinearColor{0,1,0.5f,1},
               10.f, msg.c_str());
    }

    // 3. Character
    auto* character = static_cast<APrimalCharacter*>(player->GetPlayerCharacter());
    if (!character) {
        notify({1,0.4f,0,1}, 8.f, L"[DBG] FAIL: personagem nao spawnou");
        return;
    }

    // 4. Load buff class
    FString buff_path(kShopBuffPath);
    UClass* buff_class = UVictoryCore::BPLoadClass(&buff_path);
    if (!buff_class) {
        notify({1,0,0,1}, 10.f, L"[DBG] FAIL: BPLoadClass retornou null");
        return;
    }

    // 5. Buff status
    TSubclassOf<APrimalBuff> subclass(buff_class);
    APrimalBuff* buff = character->GetBuff(subclass);
    notify({0,1,1,1}, 6.f, buff ? L"[DBG] Buff ja aplicado" : L"[DBG] Buff ausente - aplicando agora");

    if (!buff) {
        buff = APrimalBuff::StaticAddBuff(subclass, character, nullptr, player, true);
        notify(buff ? FLinearColor{0,1,0,1} : FLinearColor{1,0,0,1},
               6.f, buff ? L"[DBG] StaticAddBuff OK" : L"[DBG] FAIL: StaticAddBuff null");
    }
    if (!buff) return;

    // 6. Check RPCs — list missing ones in a single notification
    static const char* kRpcs[] = {
        "SetUiKey", "OnServerInitFinished",
        "ROC_ShopDataReceived", "ROC_GetPointsReturn",
        "FCAS_OnStashReceived", nullptr
    };
    int found = 0, total = 0;
    std::wstring missing;
    for (int i = 0; kRpcs[i]; ++i) {
        ++total;
        UFunction* fn = buff->ClassField()->FindFunctionByName(
            FName(kRpcs[i]), EIncludeSuperFlag::IncludeSuper);
        if (fn) {
            ++found;
        } else {
            if (!missing.empty()) missing += L", ";
            missing += std::wstring(kRpcs[i], kRpcs[i] + strlen(kRpcs[i]));
        }
    }
    {
        std::wstring rpc_msg = L"[DBG] RPCs: " + std::to_wstring(found)
                             + L"/" + std::to_wstring(total);
        if (!missing.empty()) rpc_msg += L" | FALTAM: " + missing;
        notify(missing.empty() ? FLinearColor{0,1,0,1} : FLinearColor{1,0.4f,0,1},
               12.f, rpc_msg.c_str());
    }

    // 7. Full InitShop
    notify({1,1,0,1}, 5.f, L"[DBG] Chamando InitShop...");
    CustomShop::Data::InitShop(player);
}

} // namespace Bridge
} // namespace CustomShop

