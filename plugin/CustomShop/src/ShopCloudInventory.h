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
    RemovalFailed,
    NothingStored,
    Cooldown,
    PlayerBusy,
    OperationInProgress,
    DataInconsistent,
};

struct CloudStatusInfo {
    bool has_header = false;
    int  header_count = 0;
    int  blob_count = 0;
    int  local_occupied = 0;
    int  local_capacity = 0;
    int  local_free = 0;
};

class ShopCloudInventory {
public:
    static ShopCloudInventory& Get();

    void SetDb(MYSQL* db);

    bool HasStoredItems(const std::string& steam_id);
    int  GetStoredItemCount(const std::string& steam_id);
    int  GetStoredBlobCount(const std::string& steam_id);

    CloudResult Upload(AShooterPlayerController* controller);
    CloudResult Download(AShooterPlayerController* controller);
    CloudStatusInfo QueryStatus(AShooterPlayerController* controller) const;

    bool HasCloudLicense(const std::string& steam_id, bool for_upload) const;
    bool RemovePlayerItem(UPrimalItem* item,
                          UPrimalInventoryComponent* inv,
                          AShooterPlayerController* controller) const;

    int LastOperationCount() const { return last_op_count_; }
    int LastDiagnosticCount() const { return last_diag_count_; }
    int LastFreeSlots() const { return last_free_slots_; }

    static const char* ResultMessage(CloudResult result, int item_count = 0);

    static void ClearOperationInProgress(const std::string& steam_id);

private:
    ShopCloudInventory() = default;

    struct UploadEntry {
        UPrimalItem* item = nullptr;
        std::string  hex;
    };

    struct CloudSnapshot {
        bool has_header = false;
        int  header_count = 0;
        int  blob_count = 0;
    };

    static std::vector<UploadEntry> CollectUploadableItems(UPrimalInventoryComponent* inv,
                                                           const std::string& steam_id);

    CloudSnapshot QueryCloudSnapshot(const std::string& steam_id) const;
    int  CountOccupiedSlots(UPrimalInventoryComponent* inv,
                            const std::string& steam_id) const;
    int  InventoryCapacity(UPrimalInventoryComponent* inv) const;
    bool RemoveUploadedItem(UPrimalItem* item,
                            UPrimalInventoryComponent* inv,
                            AShooterPlayerController* controller = nullptr) const;
    void SyncInventoryToClient(UPrimalInventoryComponent* inv,
                               AShooterPlayerController* controller) const;
    bool TryAddItemToInventory(UPrimalInventoryComponent* inv,
                               UPrimalItem* item,
                               AShooterCharacter* character,
                               UPrimalItem** out_added = nullptr) const;
    int  RestoreItemsFromHex(UPrimalInventoryComponent* inv,
                             const std::vector<std::string>& hex_rows,
                             AShooterCharacter* character) const;
    int  RestoreItemsFromBytes(UPrimalInventoryComponent* inv,
                               const std::vector<std::vector<unsigned char>>& blob_rows,
                               AShooterCharacter* character) const;
    bool PurgeCloudRecord(const std::string& steam_id);

    bool Exec(const char* sql);
    bool Escape(const std::string& in, char* out, size_t out_size) const;
    bool CheckCooldown(const std::string& steam_id);
    void TouchCooldown(const std::string& steam_id);
    bool IsPlayerReady(AShooterPlayerController* controller) const;

    MYSQL* db_ = nullptr;
    int last_op_count_ = 0;
    int last_diag_count_ = 0;
    int last_free_slots_ = 0;
};

} // namespace CustomShop
