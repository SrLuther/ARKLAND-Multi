#include "pch.h"
#include "DinoBridge.h"

namespace CustomDinoDeliver {
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

} // namespace Bridge
} // namespace CustomDinoDeliver
