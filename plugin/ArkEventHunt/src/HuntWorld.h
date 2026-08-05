#pragma once

#include "pch.h"

namespace ArkEventHunt {
namespace World {

enum class GiveItemResult : uint8_t {
    Ok = 0,
    NoController,
    NoInventory,
    LoadFailed,
    InventoryFull,
    Failed,
};

struct LootEntry {
    std::string blueprint;
    int qty = 1;
};

int64_t NowUnix();

std::wstring Utf8ToWide(const std::string& text);
// SendServerMessage espera char* na codepage do processo — UTF-8 → ACP.
std::string Utf8ToAnsi(const std::string& text);

APrimalDinoCharacter* FindDinoByIds(uint32_t id1, uint32_t id2);

// Despawn limpo (Destroy). Devolve true se o actor foi encontrado e destruído.
bool DespawnDino(uint32_t id1, uint32_t id2);

void BroadcastChat(const std::string& message);

bool IsPersonalTameActor(AActor* actor);

AShooterPlayerController* FindPlayerBySteamId(const std::string& steam_id);

GiveItemResult GiveItemToPlayer(AShooterPlayerController* controller,
                                const std::string& blueprint, int quantity);

// Entrega tabela de loot; devolve quantos stacks OK. Warn chat se inventário cheio.
int GiveLootTable(AShooterPlayerController* controller,
                  const std::vector<LootEntry>& loot);

} // namespace World
} // namespace ArkEventHunt
