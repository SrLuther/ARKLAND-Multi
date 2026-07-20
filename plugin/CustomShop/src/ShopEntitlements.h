#pragma once

#include "pch.h"

// ShopEntitlements — player_entitlements table (multiple license rows per steam_id).

namespace CustomShop {

static constexpr const char* kPaidLicenseGroups[] = {
    "Delta", "Gamma", "Beta", "Alfa", "Omega", "Transcendente",
    "Etereo", "Universal", "Onipotente", "Surreal", "Imaterial", "Exotico"
};

// Sem limite de tiers pagos distintos; renovar o mesmo group empilha +N dias.

class ShopEntitlements {
public:
    static ShopEntitlements& Get();

    void SetDb(MYSQL* db);

    bool Grant(const std::string& steam_id,
               const std::string& group,
               int days,
               const std::string& source = "",
               const std::string& notes = "");

    bool Revoke(const std::string& steam_id, const std::string& group);

    bool HasActive(const std::string& steam_id, const std::string& group);

    bool HasAnyActive(const std::string& steam_id,
                      const std::vector<std::string>& groups);

    std::vector<std::string> GetActiveGroups(const std::string& steam_id);

    void PruneExpired();

    void SyncPermissionsCommand(const std::string& steam_id,
                                const std::string& group,
                                int days);

    // Horas restantes no DB (−1 = permanente / ausente).
    int QueryHoursRemaining(const std::string& steam_id, const std::string& group);

    // Reaplica entitlements do DB no Permissions quando o jogador entra.
    // Grupos temporários são sempre realinhados ao expires (fonte de verdade).
    void SyncPlayerOnJoin(const std::string& steam_id);

    bool ApplyLicenseGrant(AShooterPlayerController* controller,
                           const nlohmann::json& entry,
                           const std::string& kit_or_item_id);

    bool CanRedeem(uint64_t steam_id, const nlohmann::json& entry);

private:
    ShopEntitlements() = default;

    MYSQL* db_ = nullptr;
};

} // namespace CustomShop
