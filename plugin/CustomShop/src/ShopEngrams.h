#pragma once

#include "pch.h"

namespace CustomShop {
namespace Engrams {

// Itera EngramBlueprintEntries do PrimalGameData (vanilla + mods).
bool UnlockAll(AShooterPlayerController* controller, bool tek_only = false,
               int* out_unlocked = nullptr);

// /engramas passo 1 — pendencia de confirmacao (TTL 2 min).
bool RequestUnlockAll(AShooterPlayerController* controller);

enum class EngramConfirmResult {
    Ok,
    NoPending,
    Expired,
    PaymentFailed,
    UnlockFailed,
};

// /confirmar — cobra ambares e executa desbloqueio pendente.
EngramConfirmResult ConfirmUnlockAll(const std::string& steam_id,
                                     AShooterPlayerController* controller,
                                     int* out_unlocked = nullptr,
                                     int* out_price = nullptr,
                                     int* out_balance = nullptr);

bool HasPendingUnlock(const std::string& steam_id);

bool IsUnlockAllCommand(const std::string& cmd);
bool ParseTekOnlyFlag(const std::string& cmd);

} // namespace Engrams
} // namespace CustomShop
