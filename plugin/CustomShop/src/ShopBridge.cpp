#include "pch.h"
#include "ShopBridge.h"

namespace {
    // Blueprint path of the buff that ships with the MX-E Ark Shop UI mod (Workshop 2693727499).
    // Mod internal name: FC_ArkShopUI — must match exactly.
    constexpr const char* kShopBuffPath =
        "Blueprint'/Game/Mods/FC_ArkShopUI/ArkShopUI_Buff_FCAS.ArkShopUI_Buff_FCAS'";

    UFunction* FindReceiveCallback(APrimalBuff* buff) {
        if (!buff) return nullptr;
        UFunction* fn = buff->ClassField()->FindFunctionByName(
            FName("ClientReceiveCallback"),
            EIncludeSuperFlag::IncludeSuper);
        if (!fn) {
            // Some mod versions use the _Implementation suffix
            fn = buff->ClassField()->FindFunctionByName(
                FName("ClientReceiveCallback_Implementation"),
                EIncludeSuperFlag::IncludeSuper);
        }
        return fn;
    }
} // anonymous namespace

namespace CustomShop {
namespace Bridge {

std::string GetSteamId(AShooterPlayerController* controller) {
    if (!controller) return "";
    // ArkApi v3 ASE: GetSteamIdFromController returns the Steam64 ID as uint64.
    // If your SDK uses a different method, adjust here.
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
    if (!character) return nullptr;

    FString buff_path(kShopBuffPath);
    UClass* buff_class = UVictoryCore::BPLoadClass(&buff_path);
    if (!buff_class) {
        Log::GetLog()->error("ShopBridge: Failed to load buff class '{}'",
                             kShopBuffPath);
        return nullptr;
    }

    TSubclassOf<APrimalBuff> subclass(buff_class);
    if (APrimalBuff* existing = character->GetBuff(subclass))
        return existing;

    return APrimalBuff::StaticAddBuff(subclass, character,
                                      nullptr, controller, true);
}

bool CanUseMod(AShooterPlayerController* controller) {
    APrimalBuff* buff = GetOrAddShopBuff(controller);
    return FindReceiveCallback(buff) != nullptr;
}

bool SendPayload(AShooterPlayerController* controller,
                 const nlohmann::json& payload) {
    APrimalBuff* buff = GetOrAddShopBuff(controller);
    if (!buff) return false;

    UFunction* fn = FindReceiveCallback(buff);
    if (!fn) {
        Log::GetLog()->warn("ShopBridge: ClientReceiveCallback not found — "
                            "is the MX-E mod loaded on this client?");
        return false;
    }

    const std::string dumped = payload.dump();
    Log::GetLog()->debug("ShopBridge → client [{}]: {}",
                         payload.value("Command", "?"), dumped);

    // The mod event expects a single FString parameter.
    struct { FString Payload; } params;
    params.Payload = FString(ArkApi::Tools::Utf8Decode(dumped));
    buff->ProcessEvent(fn, &params);
    return true;
}

bool SendPayload(const std::string& steam_id,
                 const nlohmann::json& payload) {
    return SendPayload(FindPlayer(steam_id), payload);
}

} // namespace Bridge
} // namespace CustomShop
