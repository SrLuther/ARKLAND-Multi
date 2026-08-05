#include "pch.h"
#include "HuntWorld.h"
#include "HuntConfig.h"

namespace ArkEventHunt {
namespace World {

int64_t NowUnix() {
    return static_cast<int64_t>(
        std::chrono::duration_cast<std::chrono::seconds>(
            std::chrono::system_clock::now().time_since_epoch())
            .count());
}

APrimalDinoCharacter* FindDinoByIds(uint32_t id1, uint32_t id2) {
    if (id1 == 0 && id2 == 0) return nullptr;
    UWorld* world = ArkApi::GetApiUtils().GetWorld();
    if (!world) return nullptr;

    TArray<AActor*> actors;
    UGameplayStatics::GetAllActorsOfClass(
        world, APrimalDinoCharacter::GetPrivateStaticClass(), &actors);

    for (AActor* actor : actors) {
        auto* dino = static_cast<APrimalDinoCharacter*>(actor);
        if (!dino) continue;
        int a = 0;
        int b = 0;
        dino->GetDinoIDs(&a, &b);
        if (static_cast<uint32_t>(a) == id1 &&
            static_cast<uint32_t>(b) == id2)
            return dino;
    }
    return nullptr;
}

bool DespawnDino(uint32_t id1, uint32_t id2) {
    APrimalDinoCharacter* dino = FindDinoByIds(id1, id2);
    if (!dino) return false;
    try {
        dino->Destroy(true, false);
        Log::GetLog()->info(
            "ArkEventHunt despawn: id1={} id2={}", id1, id2);
        return true;
    } catch (...) {
        Log::GetLog()->warn(
            "ArkEventHunt despawn failed: id1={} id2={}", id1, id2);
        return false;
    }
}

void BroadcastChat(const std::string& message) {
    if (message.empty()) return;
    UWorld* world = ArkApi::GetApiUtils().GetWorld();
    if (!world) return;

    const std::string sender_s = HuntConfig::Get().SenderName();
    const std::wstring wsender(sender_s.begin(), sender_s.end());
    const std::wstring wmsg(message.begin(), message.end());

    FChatMessage chat;
    chat.SenderName = FString(wsender.c_str());
    chat.Message = FString(wmsg.c_str());
    chat.SenderSteamName = FString();
    chat.SenderTribeName = FString();
    chat.SenderId = 0;
    chat.SenderIcon = nullptr;
    chat.UserId = FString();

    const auto& pcs = world->PlayerControllerListField();
    for (TWeakObjectPtr<APlayerController> pc : pcs) {
        auto* shooter = static_cast<AShooterPlayerController*>(pc.Get());
        if (shooter)
            shooter->ClientChatMessage(chat);
    }
}

bool IsPersonalTameActor(AActor* actor) {
    if (!actor) return false;
    if (!actor->IsA(APrimalDinoCharacter::GetPrivateStaticClass()))
        return false;
    auto* dino = static_cast<APrimalDinoCharacter*>(actor);
    return dino->TamingTeamIDField() != 0;
}

} // namespace World
} // namespace ArkEventHunt
