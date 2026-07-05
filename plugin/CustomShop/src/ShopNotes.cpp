#include "pch.h"
#include "ShopNotes.h"
#include "ShopBridge.h"
#include "ShopConfig.h"
#include "ShopPoints.h"

#include <chrono>
#include <cctype>
#include <mutex>
#include <unordered_map>

namespace {

struct PendingNotesUnlock {
    std::chrono::steady_clock::time_point expires;
};

std::mutex g_notes_pending_mutex;
std::unordered_map<std::string, PendingNotesUnlock> g_notes_pending;

std::string NormalizeCommandToken(std::string cmd) {
    while (!cmd.empty() && std::isspace(static_cast<unsigned char>(cmd.front())))
        cmd.erase(cmd.begin());
    while (!cmd.empty() && std::isspace(static_cast<unsigned char>(cmd.back())))
        cmd.pop_back();
    for (char& ch : cmd)
        ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
    return cmd;
}

bool RunGiveAllExplorerNotes(AShooterPlayerController* controller) {
    if (!controller) return false;

    if (auto* cheat = static_cast<UShooterCheatManager*>(controller->CheatManagerField())) {
        cheat->GiveAllExplorerNotes();
        return true;
    }

    const bool was_admin = controller->bIsAdmin()();
    if (!was_admin)
        controller->bIsAdmin() = true;

    FString fscmd("GiveAllExplorerNotes");
    FString result;
    controller->ConsoleCommand(&result, &fscmd, true);

    if (!was_admin)
        controller->bIsAdmin() = false;
    return true;
}

} // anonymous namespace

namespace CustomShop {
namespace Notes {

bool UnlockAll(AShooterPlayerController* controller) {
    if (!controller) return false;

    if (ArkApi::IApiUtils::IsPlayerDead(controller)) {
        Log::GetLog()->warn("ShopNotes: cannot unlock notes for dead player");
        return false;
    }

    if (!RunGiveAllExplorerNotes(controller)) {
        Log::GetLog()->warn("ShopNotes: GiveAllExplorerNotes failed");
        return false;
    }

    if (AShooterCharacter* character = controller->GetPlayerCharacter())
        character->BPUnlockedAllExplorerNotes();

    Log::GetLog()->info(
        "ShopNotes: GiveAllExplorerNotes completed (all explorer notes + Fjordur runes)");
    return true;
}

bool RequestUnlockAll(AShooterPlayerController* controller) {
    if (!controller) return false;

    if (!ShopConfig::Get().NotasCommandEnabled()) {
        Log::GetLog()->warn("ShopNotes: /notas is disabled in config");
        return false;
    }

    if (ArkApi::IApiUtils::IsPlayerDead(controller)) {
        Log::GetLog()->warn("ShopNotes: cannot request unlock for dead player");
        return false;
    }

    const std::string sid = Bridge::GetSteamId(controller);
    if (sid.empty()) return false;

    PendingNotesUnlock pending;
    pending.expires = std::chrono::steady_clock::now() + std::chrono::minutes(2);
    {
        std::lock_guard<std::mutex> lock(g_notes_pending_mutex);
        g_notes_pending[sid] = pending;
    }

    Log::GetLog()->info(
        "ShopNotes: /notas pending confirmation for steam_id={} (TTL 2 min, price={})",
        sid, ShopConfig::Get().NotasCommandPrice());
    return true;
}

bool HasPendingUnlock(const std::string& steam_id) {
    std::lock_guard<std::mutex> lock(g_notes_pending_mutex);
    const auto it = g_notes_pending.find(steam_id);
    if (it == g_notes_pending.end()) return false;
    return std::chrono::steady_clock::now() <= it->second.expires;
}

NotesConfirmResult ConfirmUnlockAll(const std::string& steam_id,
                                    AShooterPlayerController* controller,
                                    int* out_price,
                                    int* out_balance) {
    if (!controller || steam_id.empty()) return NotesConfirmResult::NoPending;

    if (!ShopConfig::Get().NotasCommandEnabled())
        return NotesConfirmResult::Disabled;

    {
        std::lock_guard<std::mutex> lock(g_notes_pending_mutex);
        const auto it = g_notes_pending.find(steam_id);
        if (it == g_notes_pending.end()) return NotesConfirmResult::NoPending;
        if (std::chrono::steady_clock::now() > it->second.expires) {
            g_notes_pending.erase(it);
            return NotesConfirmResult::Expired;
        }
    }

    const int price = ShopConfig::Get().NotasCommandPrice();
    const int balance_before = ShopPoints::Get().GetPoints(steam_id);
    if (out_price) *out_price = price;
    if (out_balance) *out_balance = balance_before;

    if (price > 0 && balance_before < price)
        return NotesConfirmResult::PaymentFailed;

    if (price > 0 && !ShopPoints::Get().SpendPoints(steam_id, price))
        return NotesConfirmResult::PaymentFailed;

    {
        std::lock_guard<std::mutex> lock(g_notes_pending_mutex);
        g_notes_pending.erase(steam_id);
    }

    if (!UnlockAll(controller)) {
        if (price > 0)
            ShopPoints::Get().AddPoints(steam_id, price);
        return NotesConfirmResult::UnlockFailed;
    }

    if (out_balance) *out_balance = ShopPoints::Get().GetPoints(steam_id);
    return NotesConfirmResult::Ok;
}

bool IsUnlockAllCommand(const std::string& cmd) {
    const std::string n = NormalizeCommandToken(cmd);
    if (n == "shop.unlockallexplorernotes"
        || n == "shop.giveallexplorernotes"
        || n == "cheat giveallexplorernotes"
        || n == "giveallexplorernotes")
        return true;
    if (n.rfind("shop.unlockallexplorernotes ", 0) == 0) return true;
    if (n.rfind("shop.giveallexplorernotes ", 0) == 0) return true;
    return false;
}

} // namespace Notes
} // namespace CustomShop
