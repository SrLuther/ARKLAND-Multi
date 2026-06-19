#include "pch.h"
#include "ShopCloudInventory.h"
#include "ShopBridge.h"
#include "ShopConfig.h"
#include "ShopEntitlements.h"

#include <chrono>
#include <unordered_map>
#include <unordered_set>

namespace {

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
    out.Empty();
    for (size_t i = 0; i < hex.size(); i += 2) {
        const int hi = HexNibble(hex[i]);
        const int lo = HexNibble(hex[i + 1]);
        if (hi < 0 || lo < 0) return false;
        out.Add(static_cast<unsigned char>((hi << 4) | lo));
    }
    return true;
}

std::string CurrentMapName() {
    return "";
}

std::unordered_map<std::string, std::chrono::steady_clock::time_point> g_cloud_cooldown;

void AddItemsToSet(TArray<UPrimalItem*> items, std::unordered_set<UPrimalItem*>& out) {
    for (int i = 0; i < items.Num(); ++i) {
        if (items[i]) out.insert(items[i]);
    }
}

bool IsUploadableItem(UPrimalItem* item,
                      UPrimalInventoryComponent* inv,
                      const std::unordered_set<UPrimalItem*>& excluded) {
    if (!item || !inv) return false;
    if (excluded.count(item)) return false;
    if (item->bPreventUpload().Get()) return false;
    if (item->bIsEngram().Get()) return false;

    const int qty = item->GetItemQuantity();
    if (qty <= 0) return false;

    UPrimalInventoryComponent* owner = item->OwnerInventoryField().Get();
    if (owner && owner != inv) return false;

    return true;
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

bool ShopCloudInventory::Escape(const std::string& in, char* out, size_t out_size) {
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
    const auto it = g_cloud_cooldown.find(steam_id);
    if (it == g_cloud_cooldown.end()) return true;
    const auto elapsed = std::chrono::duration_cast<std::chrono::seconds>(now - it->second).count();
    return elapsed >= secs;
}

void ShopCloudInventory::TouchCooldown(const std::string& steam_id) {
    g_cloud_cooldown[steam_id] = std::chrono::steady_clock::now();
}

bool ShopCloudInventory::IsPlayerReady(AShooterPlayerController* controller) const {
    if (!controller) return false;
    AShooterCharacter* character = controller->GetPlayerCharacter();
    if (!character) return false;
    if (character->IsDead()) return false;
    return true;
}

bool ShopCloudInventory::HasCloudLicense(const std::string& steam_id,
                                         bool for_upload) const {
    if (!for_upload && !ShopConfig::Get().CloudRequireLicenseForDownload())
        return true;
    return ShopEntitlements::Get().HasActive(steam_id, kCloudLicenseGroup);
}

bool ShopCloudInventory::HasStoredItems(const std::string& steam_id) {
    return GetStoredItemCount(steam_id) > 0;
}

int ShopCloudInventory::GetStoredItemCount(const std::string& steam_id) {
    if (!db_ || steam_id.empty()) return 0;

    char buf[64];
    if (!Escape(steam_id, buf, sizeof(buf))) return 0;

    const std::string sql =
        "SELECT item_count FROM player_cloud_inventory WHERE steam_id = '"
        + std::string(buf) + "' LIMIT 1;";

    if (mysql_query(db_, sql.c_str()) != 0) return 0;
    MYSQL_RES* res = mysql_store_result(db_);
    if (!res) return 0;

    int count = 0;
    if (MYSQL_ROW row = mysql_fetch_row(res)) {
        if (row[0]) count = std::max(0, std::atoi(row[0]));
    }
    mysql_free_result(res);
    return count;
}

std::vector<ShopCloudInventory::UploadEntry> ShopCloudInventory::CollectUploadableItems(
    UPrimalInventoryComponent* inv,
    const std::string& steam_id) {
    std::vector<UploadEntry> out;
    if (!inv) return out;

    // Cores de tinta, fila de craft e tributo ARK ficam no TArray interno mas nao
    // aparecem no inventario visivel — contam centenas de entradas fantasma.
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
    collect(inv->InventoryItemsField());
    collect(inv->ItemSlotsField());
    collect(inv->EquippedItemsField());

    const int raw_slots = inv->InventoryItemsField().Num();
    int skipped_null = 0;
    int skipped_dup = 0;
    int skipped_filtered = 0;
    int skipped_empty = 0;

    for (UPrimalItem* item : candidates) {
        if (!item) {
            ++skipped_null;
            continue;
        }
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

        out.push_back(UploadEntry{item, HexEncode(bytes)});
    }

    if (skipped_null > 0 || skipped_dup > 0 || skipped_empty > 0 || skipped_filtered > 0) {
        Log::GetLog()->info(
            "ShopCloudInventory: inventory scan steam={} raw={} candidates={} uploadable={} "
            "skipped(null={} dup={} filtered={} empty={} excluded_internal={})",
            steam_id, raw_slots, candidates.size(), out.size(),
            skipped_null, skipped_dup, skipped_filtered, skipped_empty, excluded.size());
    }

    return out;
}

CloudResult ShopCloudInventory::Upload(AShooterPlayerController* controller) {
    if (!db_ || !controller) return CloudResult::DbError;
    if (!ShopConfig::Get().CloudEnabled()) return CloudResult::Disabled;

    const std::string steam_id = Bridge::GetSteamId(controller);
    if (steam_id.empty()) return CloudResult::DbError;

    if (!CheckCooldown(steam_id)) return CloudResult::Cooldown;
    if (!IsPlayerReady(controller)) return CloudResult::PlayerBusy;
    if (!HasCloudLicense(steam_id, true)) return CloudResult::NoLicense;
    if (HasStoredItems(steam_id)) return CloudResult::AlreadyStored;

    UPrimalInventoryComponent* inv = controller->GetPlayerInventoryComponent();
    if (!inv) return CloudResult::DbError;

    const std::vector<UploadEntry> entries = CollectUploadableItems(inv, steam_id);
    last_diag_count_ = static_cast<int>(entries.size());
    if (entries.empty()) return CloudResult::EmptyInventory;

    const int max_items = ShopConfig::Get().CloudMaxItems();
    if (static_cast<int>(entries.size()) > max_items) {
        Log::GetLog()->warn(
            "ShopCloudInventory: upload rejected steam={} items={} max={} raw_slots={}",
            steam_id, entries.size(), max_items, inv->InventoryItemsField().Num());
        return CloudResult::TooManyItems;
    }

    char buf_id[64], buf_map[256];
    if (!Escape(steam_id, buf_id, sizeof(buf_id))) return CloudResult::DbError;
    const std::string map_name = CurrentMapName();
    if (!Escape(map_name, buf_map, sizeof(buf_map))) return CloudResult::DbError;

    if (!Exec("START TRANSACTION")) return CloudResult::DbError;

    const std::string header_sql =
        "INSERT INTO player_cloud_inventory (steam_id, item_count, source_map) VALUES ('"
        + std::string(buf_id) + "', "
        + std::to_string(static_cast<int>(entries.size())) + ", '"
        + std::string(buf_map) + "');";

    if (!Exec(header_sql.c_str())) {
        Exec("ROLLBACK");
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
            return CloudResult::DbError;
        }
    }

    if (!Exec("COMMIT")) {
        Exec("ROLLBACK");
        return CloudResult::DbError;
    }

    int removed = 0;
    for (const UploadEntry& entry : entries) {
        if (!entry.item) continue;
        if (entry.item->RemoveItemFromInventory(/*bForceRemoval=*/true, /*showHUDMessage=*/false))
            ++removed;
    }

    TouchCooldown(steam_id);
    last_op_count_ = static_cast<int>(entries.size());
    Log::GetLog()->info("ShopCloudInventory: upload ok steam={} items={} removed={}",
                        steam_id, entries.size(), removed);
    return CloudResult::Ok;
}

CloudResult ShopCloudInventory::Download(AShooterPlayerController* controller) {
    if (!db_ || !controller) return CloudResult::DbError;
    if (!ShopConfig::Get().CloudEnabled()) return CloudResult::Disabled;

    const std::string steam_id = Bridge::GetSteamId(controller);
    if (steam_id.empty()) return CloudResult::DbError;

    if (!CheckCooldown(steam_id)) return CloudResult::Cooldown;
    if (!IsPlayerReady(controller)) return CloudResult::PlayerBusy;
    if (!HasCloudLicense(steam_id, false)) return CloudResult::NoLicense;

    const int stored = GetStoredItemCount(steam_id);
    if (stored <= 0) return CloudResult::NothingStored;

    UPrimalInventoryComponent* inv = controller->GetPlayerInventoryComponent();
    if (!inv) return CloudResult::DbError;

    const int max_items = inv->MaxInventoryItemsField();
    const int current = inv->InventoryItemsField().Num();
    const int free_slots = max_items - current;
    if (free_slots < stored) return CloudResult::InventoryFull;

    char buf_id[64];
    if (!Escape(steam_id, buf_id, sizeof(buf_id))) return CloudResult::DbError;

    const std::string select_sql =
        "SELECT HEX(item_blob) FROM player_cloud_items WHERE steam_id = '"
        + std::string(buf_id) + "' ORDER BY sort_order ASC;";

    if (mysql_query(db_, select_sql.c_str()) != 0) return CloudResult::DbError;
    MYSQL_RES* res = mysql_store_result(db_);
    if (!res) return CloudResult::DbError;

    std::vector<std::string> hex_rows;
    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res))) {
        if (row[0] && row[0][0]) hex_rows.emplace_back(row[0]);
    }
    mysql_free_result(res);

    if (hex_rows.empty()) return CloudResult::NothingStored;

    AShooterCharacter* character = controller->GetPlayerCharacter();
    int restored = 0;
    for (const std::string& hex : hex_rows) {
        TArray<unsigned char> bytes;
        if (!HexDecode(hex, bytes)) {
            Log::GetLog()->error("ShopCloudInventory: hex decode failed steam={}", steam_id);
            return CloudResult::PartialRestore;
        }

        UPrimalItem* new_item = UPrimalItem::CreateFromBytes(&bytes);
        if (!new_item) {
            Log::GetLog()->error("ShopCloudInventory: CreateFromBytes failed steam={}", steam_id);
            return CloudResult::PartialRestore;
        }

        UPrimalItem* added = inv->AddItemObjectEx(
            new_item,
            /*bEquipItem=*/false,
            /*AddToSlot=*/false,
            /*bDontStack=*/false,
            /*ShowHUDNotification=*/false,
            /*bDontRecalcSpoilingTime=*/false,
            /*bForceIncompleteStacking=*/false,
            character,
            /*bClampStats=*/false,
            /*InsertAfterItem=*/nullptr,
            /*bInsertAtItemInstead=*/false);

        if (!added) {
            Log::GetLog()->error("ShopCloudInventory: AddItemObjectEx failed steam={}", steam_id);
            return CloudResult::PartialRestore;
        }
        ++restored;
    }

    if (restored != static_cast<int>(hex_rows.size()))
        return CloudResult::PartialRestore;

    const std::string del_sql =
        "DELETE FROM player_cloud_inventory WHERE steam_id = '" + std::string(buf_id) + "';";
    if (!Exec(del_sql.c_str())) return CloudResult::PartialRestore;

    TouchCooldown(steam_id);
    last_op_count_ = restored;
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
        return "Voce precisa de uma Licenca Nuvem ativa para enviar itens. Adquira na loja.";
    case CloudResult::AlreadyStored:
        return "Voce ja possui itens na nuvem. Use /download para recupera-los antes de um novo upload.";
    case CloudResult::EmptyInventory:
        return "Seu inventario esta vazio. Nada para enviar a nuvem.";
    case CloudResult::TooManyItems:
        return "Limite de itens na nuvem excedido. Reduza pilhas no inventario e tente novamente.";
    case CloudResult::DbError:
        return "Erro ao acessar a nuvem. Tente novamente ou contate um admin.";
    case CloudResult::InventoryFull:
        return "Inventario sem espaco suficiente. Libere slots e use /download novamente.";
    case CloudResult::PartialRestore:
        return "Falha ao restaurar alguns itens. Seu cofre na nuvem foi mantido — tente de novo.";
    case CloudResult::NothingStored:
        return "Nuvem: voce nao possui itens armazenados.";
    case CloudResult::Cooldown:
        return "Aguarde alguns segundos antes de usar a nuvem novamente.";
    case CloudResult::PlayerBusy:
        return "Voce precisa estar vivo e acordado para usar a nuvem.";
    default:
        return "Comando de nuvem indisponivel.";
    }
}

} // namespace CustomShop
