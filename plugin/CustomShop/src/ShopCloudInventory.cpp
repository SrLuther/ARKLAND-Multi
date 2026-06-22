#include "pch.h"
#include "ShopCloudInventory.h"
#include "ShopBridge.h"
#include "ShopConfig.h"
#include "ShopEntitlements.h"

#include <algorithm>
#include <chrono>
#include <mutex>
#include <unordered_map>
#include <unordered_set>

namespace {

constexpr size_t kMaxItemHexChars = 32u * 1024u * 1024u * 2u;

std::unordered_map<std::string, std::chrono::steady_clock::time_point> g_cloud_cooldown;
std::unordered_set<std::string> g_cloud_in_progress;
std::mutex g_cloud_mutex;

class CloudOperationGuard {
public:
    explicit CloudOperationGuard(const std::string& steam_id)
        : steam_id_(steam_id), acquired_(false) {
        std::lock_guard<std::mutex> lock(g_cloud_mutex);
        acquired_ = g_cloud_in_progress.insert(steam_id_).second;
    }

    ~CloudOperationGuard() {
        if (acquired_) {
            std::lock_guard<std::mutex> lock(g_cloud_mutex);
            g_cloud_in_progress.erase(steam_id_);
        }
    }

    bool acquired() const { return acquired_; }

private:
    std::string steam_id_;
    bool acquired_;
};

int HexNibble(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

std::string HexEncode(const TArray<unsigned char>& bytes) {
    static const char* kHex = "0123456789ABCDEF";
    std::string out;
    const int n = bytes.Num();
    out.reserve(static_cast<size_t>(n) * 2);
    for (int i = 0; i < n; ++i) {
        const unsigned char b = bytes[i];
        out.push_back(kHex[b >> 4]);
        out.push_back(kHex[b & 0x0F]);
    }
    return out;
}

bool HexDecode(const std::string& hex, TArray<unsigned char>& out) {
    if (hex.empty() || (hex.size() % 2) != 0) return false;
    if (hex.size() > kMaxItemHexChars) return false;
    out.Empty();
    for (size_t i = 0; i < hex.size(); i += 2) {
        const int hi = HexNibble(hex[i]);
        const int lo = HexNibble(hex[i + 1]);
        if (hi < 0 || lo < 0) return false;
        out.Add(static_cast<unsigned char>((hi << 4) | lo));
    }
    return true;
}

bool IsValidHexBlob(const std::string& hex) {
    if (hex.empty() || (hex.size() % 2) != 0) return false;
    if (hex.size() > kMaxItemHexChars) return false;
    for (char c : hex) {
        if (HexNibble(c) < 0) return false;
    }
    return true;
}

std::string CurrentMapName() {
    const auto& utils = ArkApi::GetApiUtils();
    if (utils.GetStatus() != ArkApi::ServerStatus::Ready)
        return "";
    AShooterGameMode* gm = utils.GetShooterGameMode();
    if (!gm) return "";
    FString map_name;
    gm->GetMapName(&map_name);
    return map_name.ToString();
}

void AddItemsToSet(TArray<UPrimalItem*> items, std::unordered_set<UPrimalItem*>& out) {
    for (int i = 0; i < items.Num(); ++i) {
        if (items[i]) out.insert(items[i]);
    }
}

// Specimen Implant (PrimalItem_StartingNote) — permanente no personagem; nunca na nuvem.
constexpr const char* kSpecimenImplantBlueprint =
    "Blueprint'/Game/PrimalEarth/CoreBlueprints/Items/Notes/"
    "PrimalItem_StartingNote.PrimalItem_StartingNote'";

UClass* SpecimenImplantClass() {
    static UClass* cached = nullptr;
    static bool tried = false;
    if (!tried) {
        tried = true;
        FString bp(kSpecimenImplantBlueprint);
        cached = UVictoryCore::BPLoadClass(&bp);
    }
    return cached;
}

bool IsSpecimenImplant(UPrimalItem* item) {
    if (!item) return false;

    if (UClass* implant_cls = SpecimenImplantClass()) {
        if (item->IsA(implant_cls))
            return true;
    }

    UClass* item_cls = item->ClassField();
    if (!item_cls) return false;

    FString class_name;
    item_cls->GetFullName(&class_name, nullptr);
    const std::string name = class_name.ToString();
    return name.find("PrimalItem_StartingNote") != std::string::npos
        || name.find("StartingNote") != std::string::npos;
}

bool IsUploadableItem(UPrimalItem* item,
                      UPrimalInventoryComponent* inv,
                      const std::unordered_set<UPrimalItem*>& excluded) {
    if (!item || !inv) return false;
    if (excluded.count(item)) return false;
    if (IsSpecimenImplant(item)) return false;
    if (item->bPreventUpload().Get()) return false;
    if (item->bIsEngram().Get()) return false;

    const int qty = item->GetItemQuantity();
    if (qty <= 0) return false;

    UPrimalInventoryComponent* owner = item->OwnerInventoryField().Get();
    if (owner && owner != inv) return false;

    return true;
}

bool ItemStillInInventory(UPrimalInventoryComponent* inv, const FItemNetID& item_id) {
    if (!inv) return false;
    int idx = 0;
    FItemNetID id = item_id;
    return inv->FindItem(&id, /*bEquippedItems=*/true, /*bAllItems=*/true, &idx) != nullptr;
}

} // anonymous namespace

namespace CustomShop {

ShopCloudInventory& ShopCloudInventory::Get() {
    static ShopCloudInventory instance;
    return instance;
}

void ShopCloudInventory::SetDb(MYSQL* db) {
    db_ = db;
}

bool ShopCloudInventory::Escape(const std::string& in, char* out, size_t out_size) const {
    if (!db_ || !out || out_size == 0) return false;
    mysql_real_escape_string(db_, out, in.c_str(),
        static_cast<unsigned long>(in.size()));
    return true;
}

bool ShopCloudInventory::Exec(const char* sql) {
    if (!db_) return false;
    if (mysql_query(db_, sql) != 0) {
        Log::GetLog()->error("ShopCloudInventory::Exec failed: {}", mysql_error(db_));
        return false;
    }
    return true;
}

bool ShopCloudInventory::CheckCooldown(const std::string& steam_id) {
    const int secs = ShopConfig::Get().CloudCooldownSeconds();
    if (secs <= 0) return true;
    const auto now = std::chrono::steady_clock::now();
    std::lock_guard<std::mutex> lock(g_cloud_mutex);
    const auto it = g_cloud_cooldown.find(steam_id);
    if (it == g_cloud_cooldown.end()) return true;
    const auto elapsed =
        std::chrono::duration_cast<std::chrono::seconds>(now - it->second).count();
    return elapsed >= secs;
}

void ShopCloudInventory::TouchCooldown(const std::string& steam_id) {
    std::lock_guard<std::mutex> lock(g_cloud_mutex);
    g_cloud_cooldown[steam_id] = std::chrono::steady_clock::now();
}

bool ShopCloudInventory::IsPlayerReady(AShooterPlayerController* controller) const {
    if (!controller) return false;
    AShooterCharacter* character = controller->GetPlayerCharacter();
    if (!character) return false;
    if (character->IsDead()) return false;
    UPrimalInventoryComponent* inv = controller->GetPlayerInventoryComponent();
    if (!inv) return false;
    return true;
}

bool ShopCloudInventory::RemovePlayerItem(UPrimalItem* item,
                                          UPrimalInventoryComponent* inv,
                                          AShooterPlayerController* controller) const {
    return RemoveUploadedItem(item, inv, controller);
}

bool ShopCloudInventory::HasCloudLicense(const std::string& steam_id,
                                         bool for_upload) const {
    if (!for_upload && !ShopConfig::Get().CloudRequireLicenseForDownload())
        return true;
    return ShopEntitlements::Get().HasActive(steam_id, kCloudLicenseGroup);
}

ShopCloudInventory::CloudSnapshot ShopCloudInventory::QueryCloudSnapshot(
    const std::string& steam_id) const {
    CloudSnapshot snap;
    if (!db_ || steam_id.empty()) return snap;

    char buf[64];
    if (!Escape(steam_id, buf, sizeof(buf))) return snap;

    const std::string header_sql =
        "SELECT item_count FROM player_cloud_inventory WHERE steam_id = '"
        + std::string(buf) + "' LIMIT 1;";
    if (mysql_query(db_, header_sql.c_str()) == 0) {
        MYSQL_RES* hres = mysql_store_result(db_);
        if (hres) {
            if (MYSQL_ROW row = mysql_fetch_row(hres)) {
                snap.has_header = true;
                if (row[0]) snap.header_count = std::max(0, std::atoi(row[0]));
            }
            mysql_free_result(hres);
        }
    }

    const std::string blob_sql =
        "SELECT COUNT(*) FROM player_cloud_items WHERE steam_id = '"
        + std::string(buf) + "';";
    if (mysql_query(db_, blob_sql.c_str()) == 0) {
        MYSQL_RES* bres = mysql_store_result(db_);
        if (bres) {
            if (MYSQL_ROW row = mysql_fetch_row(bres)) {
                if (row[0]) snap.blob_count = std::max(0, std::atoi(row[0]));
            }
            mysql_free_result(bres);
        }
    }

    return snap;
}

bool ShopCloudInventory::HasStoredItems(const std::string& steam_id) {
    return GetStoredBlobCount(steam_id) > 0;
}

int ShopCloudInventory::GetStoredBlobCount(const std::string& steam_id) {
    return QueryCloudSnapshot(steam_id).blob_count;
}

int ShopCloudInventory::GetStoredItemCount(const std::string& steam_id) {
    const CloudSnapshot snap = QueryCloudSnapshot(steam_id);
    if (snap.blob_count > 0) return snap.blob_count;
    return snap.header_count;
}

bool ShopCloudInventory::PurgeCloudRecord(const std::string& steam_id) {
    if (!db_ || steam_id.empty()) return false;
    char buf[64];
    if (!Escape(steam_id, buf, sizeof(buf))) return false;
    const std::string sql =
        "DELETE FROM player_cloud_inventory WHERE steam_id = '" + std::string(buf) + "';";
    return Exec(sql.c_str());
}

std::vector<ShopCloudInventory::UploadEntry> ShopCloudInventory::CollectUploadableItems(
    UPrimalInventoryComponent* inv,
    const std::string& steam_id) {
    std::vector<UploadEntry> out;
    if (!inv) return out;

    std::unordered_set<UPrimalItem*> excluded;
    AddItemsToSet(inv->AllDyeColorItemsField(), excluded);
    AddItemsToSet(inv->ArkTributeItemsField(), excluded);
    AddItemsToSet(inv->CraftingItemsField(), excluded);

    std::unordered_set<UPrimalItem*> seen;
    std::vector<UPrimalItem*> candidates;
    const auto collect = [&](TArray<UPrimalItem*> items) {
        for (int i = 0; i < items.Num(); ++i) {
            UPrimalItem* item = items[i];
            if (!item || !seen.insert(item).second) continue;
            candidates.push_back(item);
        }
    };

    // Equipados e hotbar primeiro na lista de remocao (ordem inversa na coleta).
    collect(inv->EquippedItemsField());
    collect(inv->ItemSlotsField());
    collect(inv->InventoryItemsField());

    const int raw_slots = inv->InventoryItemsField().Num();
    int skipped_filtered = 0;
    int skipped_empty = 0;
    int skipped_invalid_hex = 0;

    for (UPrimalItem* item : candidates) {
        if (!IsUploadableItem(item, inv, excluded)) {
            ++skipped_filtered;
            continue;
        }

        TArray<unsigned char> bytes;
        item->GetItemBytes(&bytes);
        if (bytes.Num() <= 0) {
            ++skipped_empty;
            continue;
        }

        const std::string hex = HexEncode(bytes);
        if (!IsValidHexBlob(hex)) {
            ++skipped_invalid_hex;
            continue;
        }

        out.push_back(UploadEntry{item, hex});
    }

    Log::GetLog()->info(
        "ShopCloudInventory: scan steam={} raw_array={} candidates={} uploadable={} "
        "skipped(filtered={} empty_bytes={} invalid_hex={} internal_excluded={})",
        steam_id, raw_slots, candidates.size(), out.size(),
        skipped_filtered, skipped_empty, skipped_invalid_hex, excluded.size());

    return out;
}

int ShopCloudInventory::CountOccupiedSlots(UPrimalInventoryComponent* inv,
                                             const std::string& steam_id) const {
    return static_cast<int>(CollectUploadableItems(inv, steam_id).size());
}

int ShopCloudInventory::InventoryCapacity(UPrimalInventoryComponent* inv) const {
    if (!inv) return 0;
    const int from_native = inv->GetMaxInventoryItems(true);
    if (from_native > 0) return from_native;
    const int field_max = inv->MaxInventoryItemsField();
    if (field_max > 0) return field_max;
    return inv->AbsoluteMaxInventoryItemsField();
}

bool ShopCloudInventory::RemoveUploadedItem(UPrimalItem* item,
                                            UPrimalInventoryComponent* inv,
                                            AShooterPlayerController* controller) const {
    if (!item || !inv) return false;

    const bool was_equipped = item->bEquippedItem().Get();
    FItemNetID item_id = item->ItemIDField();

    // Hotbar / equipados precisam sair do slot antes da remocao.
    item->RemoveFromSlot(/*bForce=*/true);

    if (inv->RemoveItem(
            &item_id,
            /*bDoDrop=*/false,
            /*bSecondryAction=*/false,
            /*bForceRemoval=*/true,
            /*showHUDMessage=*/false)) {
        if (controller)
            controller->ClientRemoveActorItem(inv, item_id, /*showHUDMessage=*/false);
        return true;
    }

    if (item->RemoveItemFromInventory(/*bForceRemoval=*/true, /*showHUDMessage=*/false)) {
        inv->NotifyItemRemoved(item);
        inv->NotifyClientsItemStatus(
            item, was_equipped, /*bRemovedItem=*/true,
            false, false, false,
            nullptr, nullptr,
            false, false, false);
        if (controller)
            controller->ClientRemoveActorItem(inv, item_id, /*showHUDMessage=*/false);
        return true;
    }

    if (controller) {
        controller->ServerRemovePawnItem(item_id, /*bSecondryAction=*/false);
        if (!ItemStillInInventory(inv, item_id))
            return true;
    }

    return !ItemStillInInventory(inv, item_id);
}

void ShopCloudInventory::SyncInventoryToClient(UPrimalInventoryComponent* inv,
                                               AShooterPlayerController* controller) const {
    if (!inv || !controller) return;

    // Handshake completo (mesmo padrao do respawn/morte): reenvia inventario vazio ao cliente.
    controller->ClientStartReceivingActorItems(inv, /*bEquippedItems=*/false);
    controller->ServerRequestActorItems(inv, /*bInventoryItems=*/true, /*bIsFirstSpawn=*/false);
    controller->ClientFinishedReceivingActorItems(inv, false);

    controller->ClientStartReceivingActorItems(inv, /*bEquippedItems=*/true);
    controller->ServerRequestActorItems(inv, /*bInventoryItems=*/false, /*bIsFirstSpawn=*/false);
    controller->ClientFinishedReceivingActorItems(inv, true);

    inv->InventoryRefresh();

    if (AShooterCharacter* character = controller->GetPlayerCharacter())
        character->RefreshDefaultAttachments(character, /*bIsSnapshot=*/false);
}

bool ShopCloudInventory::TryAddItemToInventory(UPrimalInventoryComponent* inv,
                                               UPrimalItem* item,
                                               AShooterCharacter* character,
                                               UPrimalItem** out_added) const {
    if (!inv || !item) return false;

    UPrimalItem* added = inv->AddItemObject(item);
    if (!added) {
        added = inv->AddItemObjectEx(
            item,
            /*bEquipItem=*/false,
            /*AddToSlot=*/false,
            /*bDontStack=*/false,
            /*ShowHUDNotification=*/true,
            /*bDontRecalcSpoilingTime=*/false,
            /*bForceIncompleteStacking=*/false,
            character,
            /*bClampStats=*/false,
            /*InsertAfterItem=*/nullptr,
            /*bInsertAtItemInstead=*/false);
    }

    if (!added) return false;
    if (out_added) *out_added = added;
    return true;
}

int ShopCloudInventory::RestoreItemsFromHex(UPrimalInventoryComponent* inv,
                                            const std::vector<std::string>& hex_rows,
                                            AShooterCharacter* character) const {
    if (!inv) return 0;
    int restored = 0;
    for (const std::string& hex : hex_rows) {
        TArray<unsigned char> bytes;
        if (!HexDecode(hex, bytes)) continue;

        UPrimalItem* new_item = UPrimalItem::CreateFromBytes(&bytes);
        if (!new_item) continue;

        if (!TryAddItemToInventory(inv, new_item, character))
            continue;
        ++restored;
    }
    return restored;
}

CloudStatusInfo ShopCloudInventory::QueryStatus(
    AShooterPlayerController* controller) const {
    CloudStatusInfo info;
    if (!controller) return info;

    const std::string steam_id = Bridge::GetSteamId(controller);
    if (steam_id.empty()) return info;

    const CloudSnapshot snap = QueryCloudSnapshot(steam_id);
    info.has_header = snap.has_header;
    info.header_count = snap.header_count;
    info.blob_count = snap.blob_count;

    UPrimalInventoryComponent* inv = controller->GetPlayerInventoryComponent();
    if (inv) {
        info.local_capacity = InventoryCapacity(inv);
        info.local_occupied = CountOccupiedSlots(inv, steam_id);
        info.local_free = std::max(0, info.local_capacity - info.local_occupied);
    }

    return info;
}

CloudResult ShopCloudInventory::Upload(AShooterPlayerController* controller) {
    if (!db_ || !controller) return CloudResult::DbError;
    if (!ShopConfig::Get().CloudEnabled()) return CloudResult::Disabled;

    const std::string steam_id = Bridge::GetSteamId(controller);
    if (steam_id.empty()) return CloudResult::DbError;

    CloudOperationGuard op_guard(steam_id);
    if (!op_guard.acquired()) return CloudResult::OperationInProgress;

    if (!CheckCooldown(steam_id)) return CloudResult::Cooldown;
    if (!IsPlayerReady(controller)) return CloudResult::PlayerBusy;
    if (!HasCloudLicense(steam_id, true)) return CloudResult::NoLicense;

    const CloudSnapshot existing = QueryCloudSnapshot(steam_id);
    if (existing.blob_count > 0) return CloudResult::AlreadyStored;
    if (existing.has_header && existing.blob_count == 0) {
        Log::GetLog()->warn(
            "ShopCloudInventory: orphan header steam={} — purging before upload",
            steam_id);
        PurgeCloudRecord(steam_id);
    }

    UPrimalInventoryComponent* inv = controller->GetPlayerInventoryComponent();
    if (!inv) return CloudResult::DbError;

    AShooterCharacter* character = controller->GetPlayerCharacter();

    const std::vector<UploadEntry> entries = CollectUploadableItems(inv, steam_id);
    last_diag_count_ = static_cast<int>(entries.size());
    if (entries.empty()) return CloudResult::EmptyInventory;

    const int max_items = ShopConfig::Get().CloudMaxItems();
    if (static_cast<int>(entries.size()) > max_items) {
        Log::GetLog()->warn(
            "ShopCloudInventory: upload rejected steam={} uploadable={} max={}",
            steam_id, entries.size(), max_items);
        return CloudResult::TooManyItems;
    }

    // Fase 1: remover TODOS os itens do inventario antes de gravar no banco.
    std::vector<std::string> removed_hexes;
    removed_hexes.reserve(entries.size());

    for (size_t i = 0; i < entries.size(); ++i) {
        const UploadEntry& entry = entries[i];
        if (!entry.item) {
            Log::GetLog()->error(
                "ShopCloudInventory: null item pointer steam={} index={}", steam_id, i);
            const int rollback = RestoreItemsFromHex(inv, removed_hexes, character);
            Log::GetLog()->error(
                "ShopCloudInventory: upload rollback steam={} restored={}/{}",
                steam_id, rollback, removed_hexes.size());
            return CloudResult::RemovalFailed;
        }

        if (!RemoveUploadedItem(entry.item, inv, controller)) {
            Log::GetLog()->error(
                "ShopCloudInventory: remove failed steam={} at {}/{}",
                steam_id, i, entries.size());
            const int rollback = RestoreItemsFromHex(inv, removed_hexes, character);
            Log::GetLog()->error(
                "ShopCloudInventory: upload rollback steam={} restored={}/{}",
                steam_id, rollback, removed_hexes.size());
            last_diag_count_ = static_cast<int>(entries.size());
            return CloudResult::RemovalFailed;
        }
        removed_hexes.push_back(entry.hex);
    }

    SyncInventoryToClient(inv, controller);

    const int remaining = CountOccupiedSlots(inv, steam_id);
    if (remaining > 0) {
        Log::GetLog()->warn(
            "ShopCloudInventory: upload steam={} removed={} but {} uploadable remain — rolling back",
            steam_id, entries.size(), remaining);
        const int rollback = RestoreItemsFromHex(inv, removed_hexes, character);
        Log::GetLog()->error(
            "ShopCloudInventory: upload rollback (remaining items) steam={} restored={}/{}",
            steam_id, rollback, removed_hexes.size());
        return CloudResult::RemovalFailed;
    }

    char buf_id[64], buf_map[256];
    if (!Escape(steam_id, buf_id, sizeof(buf_id))) {
        RestoreItemsFromHex(inv, removed_hexes, character);
        return CloudResult::DbError;
    }
    const std::string map_name = CurrentMapName();
    if (!Escape(map_name, buf_map, sizeof(buf_map))) {
        RestoreItemsFromHex(inv, removed_hexes, character);
        return CloudResult::DbError;
    }

    if (!Exec("START TRANSACTION")) {
        RestoreItemsFromHex(inv, removed_hexes, character);
        return CloudResult::DbError;
    }

    const std::string header_sql =
        "INSERT INTO player_cloud_inventory (steam_id, item_count, source_map) VALUES ('"
        + std::string(buf_id) + "', "
        + std::to_string(static_cast<int>(entries.size())) + ", '"
        + std::string(buf_map) + "');";

    if (!Exec(header_sql.c_str())) {
        Exec("ROLLBACK");
        RestoreItemsFromHex(inv, removed_hexes, character);
        const unsigned err = mysql_errno(db_);
        if (err == 1062) return CloudResult::AlreadyStored;
        return CloudResult::DbError;
    }

    for (size_t i = 0; i < entries.size(); ++i) {
        const std::string item_sql =
            "INSERT INTO player_cloud_items (steam_id, sort_order, item_blob) VALUES ('"
            + std::string(buf_id) + "', "
            + std::to_string(static_cast<int>(i)) + ", UNHEX('"
            + entries[i].hex + "'));";
        if (!Exec(item_sql.c_str())) {
            Exec("ROLLBACK");
            RestoreItemsFromHex(inv, removed_hexes, character);
            return CloudResult::DbError;
        }
    }

    if (!Exec("COMMIT")) {
        Exec("ROLLBACK");
        RestoreItemsFromHex(inv, removed_hexes, character);
        return CloudResult::DbError;
    }

    TouchCooldown(steam_id);
    last_op_count_ = static_cast<int>(entries.size());
    SyncInventoryToClient(inv, controller);
    Log::GetLog()->info(
        "ShopCloudInventory: upload ok steam={} items={} map='{}'",
        steam_id, entries.size(), map_name);
    return CloudResult::Ok;
}

CloudResult ShopCloudInventory::Download(AShooterPlayerController* controller) {
    if (!db_ || !controller) return CloudResult::DbError;
    if (!ShopConfig::Get().CloudEnabled()) return CloudResult::Disabled;

    const std::string steam_id = Bridge::GetSteamId(controller);
    if (steam_id.empty()) return CloudResult::DbError;

    CloudOperationGuard op_guard(steam_id);
    if (!op_guard.acquired()) return CloudResult::OperationInProgress;

    if (!CheckCooldown(steam_id)) return CloudResult::Cooldown;
    if (!IsPlayerReady(controller)) return CloudResult::PlayerBusy;
    if (!HasCloudLicense(steam_id, false)) return CloudResult::NoLicense;

    const CloudSnapshot snap = QueryCloudSnapshot(steam_id);
    if (snap.blob_count <= 0) {
        if (snap.has_header) {
            Log::GetLog()->warn(
                "ShopCloudInventory: header without blobs steam={} — purging",
                steam_id);
            PurgeCloudRecord(steam_id);
        }
        return CloudResult::NothingStored;
    }

    if (snap.has_header && snap.header_count != snap.blob_count) {
        Log::GetLog()->warn(
            "ShopCloudInventory: count mismatch steam={} header={} blobs={} — using blob count",
            steam_id, snap.header_count, snap.blob_count);
    }

    const int to_restore = snap.blob_count;

    UPrimalInventoryComponent* inv = controller->GetPlayerInventoryComponent();
    if (!inv) return CloudResult::DbError;

    AShooterCharacter* character = controller->GetPlayerCharacter();

    const int capacity = InventoryCapacity(inv);
    const int occupied = CountOccupiedSlots(inv, steam_id);
    const int free_slots = std::max(0, capacity - occupied);
    last_free_slots_ = free_slots;

    char buf_id[64];
    if (!Escape(steam_id, buf_id, sizeof(buf_id))) return CloudResult::DbError;

    const std::string select_sql =
        "SELECT HEX(item_blob) FROM player_cloud_items WHERE steam_id = '"
        + std::string(buf_id) + "' ORDER BY sort_order ASC;";

    if (mysql_query(db_, select_sql.c_str()) != 0) return CloudResult::DbError;
    MYSQL_RES* res = mysql_store_result(db_);
    if (!res) return CloudResult::DbError;

    std::vector<std::string> hex_rows;
    hex_rows.reserve(static_cast<size_t>(to_restore));
    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res))) {
        if (row[0] && row[0][0] && IsValidHexBlob(row[0]))
            hex_rows.emplace_back(row[0]);
    }
    mysql_free_result(res);

    if (hex_rows.empty()) {
        PurgeCloudRecord(steam_id);
        return CloudResult::DataInconsistent;
    }

    if (static_cast<int>(hex_rows.size()) != to_restore) {
        Log::GetLog()->error(
            "ShopCloudInventory: blob row mismatch steam={} expected={} loaded={}",
            steam_id, to_restore, hex_rows.size());
        return CloudResult::DataInconsistent;
    }

    // Ignora implantes antigos gravados na nuvem antes deste filtro.
    std::vector<std::string> restore_rows;
    restore_rows.reserve(hex_rows.size());
    int skipped_implants = 0;
    for (const std::string& hex : hex_rows) {
        TArray<unsigned char> bytes;
        if (!HexDecode(hex, bytes)) {
            Log::GetLog()->error(
                "ShopCloudInventory: hex decode failed steam={} during pre-scan", steam_id);
            return CloudResult::DataInconsistent;
        }
        UPrimalItem* probe = UPrimalItem::CreateFromBytes(&bytes);
        if (!probe) {
            Log::GetLog()->error(
                "ShopCloudInventory: CreateFromBytes failed steam={} during pre-scan", steam_id);
            return CloudResult::DataInconsistent;
        }
        if (IsSpecimenImplant(probe)) {
            ++skipped_implants;
            Log::GetLog()->warn(
                "ShopCloudInventory: skipping specimen implant blob steam={}", steam_id);
            continue;
        }
        restore_rows.push_back(hex);
    }

    last_diag_count_ = static_cast<int>(restore_rows.size());

    if (restore_rows.empty()) {
        Log::GetLog()->warn(
            "ShopCloudInventory: cloud only had specimen implants steam={} count={} — purging",
            steam_id, skipped_implants);
        PurgeCloudRecord(steam_id);
        TouchCooldown(steam_id);
        last_op_count_ = 0;
        return CloudResult::Ok;
    }

    if (free_slots < static_cast<int>(restore_rows.size())) {
        Log::GetLog()->warn(
            "ShopCloudInventory: download rejected steam={} need={} free={} "
            "(skipped_implants={} capacity={} occupied={})",
            steam_id, restore_rows.size(), free_slots, skipped_implants,
            capacity, occupied);
        return CloudResult::InventoryFull;
    }

    std::vector<UPrimalItem*> added_items;
    added_items.reserve(restore_rows.size());
    int restored = 0;

    for (size_t i = 0; i < restore_rows.size(); ++i) {
        TArray<unsigned char> bytes;
        if (!HexDecode(restore_rows[i], bytes)) {
            Log::GetLog()->error(
                "ShopCloudInventory: hex decode failed steam={} index={}", steam_id, i);
            for (UPrimalItem* rollback_item : added_items)
                RemoveUploadedItem(rollback_item, inv, controller);
            return CloudResult::PartialRestore;
        }

        UPrimalItem* new_item = UPrimalItem::CreateFromBytes(&bytes);
        if (!new_item) {
            Log::GetLog()->error(
                "ShopCloudInventory: CreateFromBytes failed steam={} index={}", steam_id, i);
            for (UPrimalItem* rollback_item : added_items)
                RemoveUploadedItem(rollback_item, inv, controller);
            return CloudResult::PartialRestore;
        }

        if (IsSpecimenImplant(new_item)) {
            Log::GetLog()->warn(
                "ShopCloudInventory: unexpected implant at restore steam={} index={}",
                steam_id, i);
            continue;
        }

        UPrimalItem* added = nullptr;
        if (!TryAddItemToInventory(inv, new_item, character, &added) || !added) {
            Log::GetLog()->error(
                "ShopCloudInventory: add failed steam={} index={}/{}",
                steam_id, i, restore_rows.size());
            for (UPrimalItem* rollback_item : added_items)
                RemoveUploadedItem(rollback_item, inv, controller);
            return CloudResult::PartialRestore;
        }

        added_items.push_back(added);
        ++restored;
    }

    if (restored != static_cast<int>(restore_rows.size())) {
        for (UPrimalItem* rollback_item : added_items)
            RemoveUploadedItem(rollback_item, inv, controller);
        return CloudResult::PartialRestore;
    }

    if (!PurgeCloudRecord(steam_id)) {
        Log::GetLog()->error(
            "ShopCloudInventory: purge failed after restore steam={} — keeping cloud intact",
            steam_id);
        for (UPrimalItem* rollback_item : added_items)
            RemoveUploadedItem(rollback_item, inv, controller);
        return CloudResult::PartialRestore;
    }

    TouchCooldown(steam_id);
    last_op_count_ = restored;
    SyncInventoryToClient(inv, controller);
    Log::GetLog()->info("ShopCloudInventory: download ok steam={} items={}", steam_id, restored);
    return CloudResult::Ok;
}

const char* ShopCloudInventory::ResultMessage(CloudResult result, int item_count) {
    switch (result) {
    case CloudResult::Ok:
        return item_count > 0 ? "ok" : "ok";
    case CloudResult::Disabled:
        return "Inventario na nuvem desativado neste servidor.";
    case CloudResult::NoLicense:
        return "Voce precisa de uma Licenca Nuvem ativa. Adquira na loja.";
    case CloudResult::AlreadyStored:
        return "Voce ja possui itens na nuvem. Use /download antes de um novo /upload.";
    case CloudResult::EmptyInventory:
        return "Nenhum item valido para enviar (pilhas vazias ou itens bloqueados).";
    case CloudResult::TooManyItems:
        return "Limite de itens na nuvem excedido.";
    case CloudResult::DbError:
        return "Erro ao acessar a nuvem. Tente novamente ou contate um admin.";
    case CloudResult::InventoryFull:
        return "Inventario sem espaco suficiente para todos os itens da nuvem.";
    case CloudResult::PartialRestore:
        return "Falha ao restaurar itens. Nada foi alterado na nuvem.";
    case CloudResult::RemovalFailed:
        return "Falha ao remover itens. Nada foi salvo na nuvem.";
    case CloudResult::NothingStored:
        return "Voce nao possui itens armazenados.";
    case CloudResult::Cooldown:
        return "Aguarde alguns segundos antes de usar a nuvem novamente.";
    case CloudResult::PlayerBusy:
        return "Voce precisa estar vivo para usar a nuvem.";
    case CloudResult::OperationInProgress:
        return "Aguarde a operacao anterior da nuvem terminar.";
    case CloudResult::DataInconsistent:
        return "Dados da nuvem inconsistentes. Contate um admin.";
    default:
        return "Comando de nuvem indisponivel.";
    }
}

} // namespace CustomShop
