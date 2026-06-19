#pragma once

#include "pch.h"

namespace CustomShop {

inline constexpr const char* kCloudLicenseGroup = "keyvault";
inline constexpr int         kDefaultCloudMaxItems = 250;
inline constexpr int         kDefaultCloudCooldownSec = 30;

enum class CloudResult {
    Ok,
    Disabled,
    NoLicense,
    AlreadyStored,
    EmptyInventory,
    TooManyItems,
    DbError,
    InventoryFull,
    PartialRestore,
    NothingStored,
    Cooldown,
    PlayerBusy,
};

class ShopCloudInventory {
public:
    static ShopCloudInventory& Get();

    void SetDb(MYSQL* db);

    bool HasStoredItems(const std::string& steam_id);
    int  GetStoredItemCount(const std::string& steam_id);

    CloudResult Upload(AShooterPlayerController* controller);
    CloudResult Download(AShooterPlayerController* controller);

    int LastOperationCount() const { return last_op_count_; }

    static const char* ResultMessage(CloudResult result, int item_count = 0);

private:
    ShopCloudInventory() = default;

    bool Exec(const char* sql);
    bool Escape(const std::string& in, char* out, size_t out_size);
    bool CheckCooldown(const std::string& steam_id);
    void TouchCooldown(const std::string& steam_id);
    bool IsPlayerReady(AShooterPlayerController* controller) const;
    bool HasCloudLicense(const std::string& steam_id, bool for_upload) const;

    MYSQL* db_ = nullptr;
    int last_op_count_ = 0;
};

} // namespace CustomShop
