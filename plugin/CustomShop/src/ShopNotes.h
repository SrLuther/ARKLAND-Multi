#pragma once

#include "pch.h"

namespace CustomShop {
namespace Notes {

// Desbloqueia todas as notas de explorador e runas de Fjordur (GiveAllExplorerNotes).
bool UnlockAll(AShooterPlayerController* controller);

// /notas passo 1 — pendencia de confirmacao (TTL 2 min).
bool RequestUnlockAll(AShooterPlayerController* controller);

enum class NotesConfirmResult {
    Ok,
    NoPending,
    Expired,
    PaymentFailed,
    UnlockFailed,
    Disabled,
};

// /confirmar — cobra ambares e executa desbloqueio pendente.
NotesConfirmResult ConfirmUnlockAll(const std::string& steam_id,
                                    AShooterPlayerController* controller,
                                    int* out_price = nullptr,
                                    int* out_balance = nullptr);

bool HasPendingUnlock(const std::string& steam_id);

bool IsUnlockAllCommand(const std::string& cmd);

} // namespace Notes
} // namespace CustomShop
