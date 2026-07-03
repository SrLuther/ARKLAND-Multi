#pragma once

#include "pch.h"

namespace CustomShop {
namespace Engrams {

// Itera EngramBlueprintEntries do PrimalGameData (vanilla + mods).
bool UnlockAll(AShooterPlayerController* controller, bool tek_only = false,
               int* out_unlocked = nullptr);

// /engramas passo 1 — pendencia de confirmacao (TTL 2 min).
bool RequestUnlockAll(AShooterPlayerController* controller);

// /confirmar — executa desbloqueio pendente.
bool ConfirmUnlockAll(const std::string& steam_id, AShooterPlayerController* controller,
                      int* out_unlocked = nullptr);

bool HasPendingUnlock(const std::string& steam_id);

bool IsUnlockAllCommand(const std::string& cmd);
bool ParseTekOnlyFlag(const std::string& cmd);

} // namespace Engrams
} // namespace CustomShop
