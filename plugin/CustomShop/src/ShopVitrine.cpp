#include "pch.h"
#include "ShopVitrine.h"
#include "ShopDebug.h"
#include "VitrineMatch.h"
#include "ShopBridge.h"
#include "ShopCloudInventory.h"
#include "ShopConfig.h"
#include "ShopEngrams.h"
#include "ShopMarket.h"
#include "ShopNotes.h"
#include "ShopStore.h"
#include "ShopTeams.h"
#include "HttpClient.h"

#include <algorithm>
#include <chrono>
#include <fstream>
#include <cmath>
#include <ctime>
#include <mutex>
#include <random>
#include <set>
#include <unordered_map>
#include <unordered_set>

// ─────────────────────────────────────────────────────────────────
//  Vitrine de Recursos — ver docs/VITRINE_RECURSOS_SPEC.md (§6 e "Notas do plugin").
// ─────────────────────────────────────────────────────────────────

namespace CustomShop {
namespace Vitrine {
namespace {

constexpr const char* kApi = "/api/market/resources/plugin";
constexpr int kMaxUploadLines = 64;          // = MAX_UPLOAD_LINES do backend
constexpr int kMaxQtyPerLine = 1000000;      // = MAX_UPLOAD_QTY_PER_LINE do backend
constexpr int kMaxChatLines = 20;

// ── Tipos ────────────────────────────────────────────────────────

struct Resource {
    int id = 0;
    std::string blueprint;   // canonico /Game/.../X.X
    std::string key;         // minusculo, sempre re-normalizado do blueprint
    std::string short_key;   // token da classe (ex.: primalitemresource_metal)
    std::string name;
    std::string name_ascii;
    int stack_size = 0;
};

struct Line {
    int resource_id = 0;
    std::string key;
    std::string blueprint;   // do cadastro (enviado na API)
    std::string bp_class;    // classe real do item (para devolver)
    std::string name_ascii;
    int stack_size = 0;
    int quantity = 0;
};

struct PendingVitrine {
    std::chrono::steady_clock::time_point expires;
    std::vector<Line> lines;
};

std::mutex g_pending_mutex;
std::unordered_map<std::string, PendingVitrine> g_pending;

// Serializa recuperacao/confirmacao/entrega (callbacks de timer podem vir de outra thread).
std::recursive_mutex g_op_mutex;

// ── Utilidades ───────────────────────────────────────────────────

/** Chat ASE: so ASCII imprimivel; sem {} / % (SendChatMessage formata o texto). */
std::string ChatSafe(const std::string& in) {
    std::string out;
    out.reserve(in.size());
    for (unsigned char ch : in) {
        if (ch < 32 || ch > 126) continue;
        if (ch == '{' || ch == '}' || ch == '%') continue;
        out.push_back(static_cast<char>(ch));
    }
    while (!out.empty() && out.back() == ' ')
        out.pop_back();
    return out.empty() ? std::string("-") : out;
}

void SendMsg(AShooterPlayerController* c, const std::string& msg) {
    if (!c || msg.empty()) return;
    static const FString kSender(L"Vitrine");
    ArkApi::GetApiUtils().SendChatMessage(c, kSender, ChatSafe(msg).c_str());
}

std::string FormatQty(long long value) {
    std::string s = std::to_string(value);
    for (int i = static_cast<int>(s.size()) - 3; i > 0; i -= 3)
        s.insert(static_cast<size_t>(i), ".");
    return s;
}

std::string ToLower(std::string s) {
    for (char& ch : s)
        ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
    return s;
}

bool ParseObject(const std::string& text, nlohmann::json& out) {
    if (text.empty()) return false;
    try {
        out = nlohmann::json::parse(text);
        return out.is_object();
    } catch (...) {
        return false;
    }
}

template <typename T>
T JsonGet(const nlohmann::json& obj, const char* key, T fallback) {
    try {
        if (obj.is_object() && obj.contains(key) && !obj[key].is_null())
            return obj[key].get<T>();
    } catch (...) {}
    return fallback;
}

long long NowUnix() {
    return static_cast<long long>(std::time(nullptr));
}

/**
 * Espelha `normalize_blueprint` do backend (resource_vitrine_service.py).
 * Aceita o que o admin cola e o que o ARK reporta do mesmo item:
 * Blueprint'/Game/.../X.X', /Game/.../X.X(_C|_c), "BlueprintGeneratedClass /Game/.../X.X_C"
 * e o CDO "…/X.Default__X_C". canonical = /Game/.../X.X (sem _C); key = minusculo.
 */
bool NormalizeBlueprint(const std::string& raw, std::string* canonical, std::string* key) {
    const VitrineMatch::Identity id = VitrineMatch::Identify(raw);
    if (id.path.empty()) return false;
    if (canonical) *canonical = id.path;
    if (key) *key = id.key;
    return true;
}

/** Token da classe: `PrimalItemResource_Metal` a partir do path, do CDO ou de "Package.Class_C". */
std::string ShortToken(const std::string& s) {
    return VitrineMatch::Identify(s).short_key;
}

std::string NewUploadId() {
    std::random_device rd;
    std::mt19937_64 rng(
        (static_cast<uint64_t>(rd()) << 32) ^ static_cast<uint64_t>(rd())
        ^ static_cast<uint64_t>(
              std::chrono::high_resolution_clock::now().time_since_epoch().count()));
    static const char* kHex = "0123456789abcdef";
    std::string out = "vr";
    out.reserve(32);
    for (int i = 0; i < 30; ++i)
        out.push_back(kHex[rng() & 0xF]);
    return out;
}

bool IsSafeToken(const std::string& s) {
    if (s.empty() || s.size() > 64) return false;
    for (unsigned char ch : s) {
        if (!(std::isalnum(ch) || ch == '_' || ch == '-')) return false;
    }
    return true;
}

// ── Inventario ───────────────────────────────────────────────────

bool PlayerReady(AShooterPlayerController* player) {
    if (!player) return false;
    AShooterCharacter* character = player->GetPlayerCharacter();
    if (!character || character->IsDead()) return false;
    return player->GetPlayerInventoryComponent() != nullptr;
}

struct ItemIdentity {
    std::string full_key;
    std::string alt_key;
    std::string short_key;
    std::string canonical;
    std::string raw;
    std::vector<std::string> keys;
};

/**
 * Identidade do item no inventario.
 * 1) ClassToStringReference — o mesmo texto do giveitem / do cadastro admin.
 * 2) GetFullName — "BlueprintGeneratedClass /Game/.../X.X_C" ou, sem path,
 *    "BlueprintGeneratedClass Package.X_C" (cai no token curto).
 */
ItemIdentity IdentifyItem(UPrimalItem* item) {
    ItemIdentity id;
    if (!item) return id;
    UClass* cls = item->ClassField();
    if (!cls) return id;

    const auto remember = [&](const std::string& key) {
        if (key.empty()) return;
        if (std::find(id.keys.begin(), id.keys.end(), key) == id.keys.end())
            id.keys.push_back(key);
    };
    const auto take = [&](const std::string& raw) {
        if (raw.empty()) return;
        if (id.raw.empty()) id.raw = raw;
        const VitrineMatch::Identity parsed = VitrineMatch::Identify(raw);
        if (!parsed.key.empty()) {
            if (id.full_key.empty()) {
                id.full_key = parsed.key;
                id.canonical = parsed.path;
            } else if (parsed.key != id.full_key && id.alt_key.empty()) {
                id.alt_key = parsed.key;
            }
            remember(parsed.key);
        }
        if (!parsed.short_key.empty()) {
            if (id.short_key.empty()) id.short_key = parsed.short_key;
            remember(parsed.short_key);
        }
    };

    FString ref;
    UVictoryCore::ClassToStringReference(&ref, TSubclassOf<UObject>(cls));
    take(ref.ToString());

    FString class_name;
    cls->GetFullName(&class_name, nullptr);
    take(class_name.ToString());
    return id;
}

std::string ItemClassKey(UPrimalItem* item, std::string* canonical) {
    const ItemIdentity id = IdentifyItem(item);
    if (!id.full_key.empty()) {
        if (canonical) *canonical = id.canonical;
        return id.full_key;
    }
    if (canonical && !id.short_key.empty()) *canonical = id.short_key;
    return id.short_key;
}

enum class PlainReject : int {
    Ok = 0,
    Engram = 1,
    Blueprint = 2,
    Equipped = 3,
    Durability = 4,
    Rating = 5,
    Owner = 6,
    MaxStack = 7,
    Qty = 8,
};

/** Stack maximo da classe (CDO) ou da instancia — o que for maior. Recurso comum e > 1. */
int MaxStackOf(UPrimalItem* item, UWorld* world) {
    int best = 0;
    if (!item || !world) return 0;
    if (UClass* cls = item->ClassField()) {
        if (UPrimalItem* cdo = static_cast<UPrimalItem*>(cls->GetDefaultObject(true))) {
            const int q = cdo->GetMaxItemQuantity(world);
            if (q > best) best = q;
        }
    }
    const int inst = item->GetMaxItemQuantity(world);
    if (inst > best) best = inst;
    return best;
}

/**
 * Item "comum empilhavel": sem engrama/blueprint/equipado/durabilidade/rating
 * e com stack maximo > 1. Mesmo predicado para listar E remover.
 */
PlainReject ClassifyPlain(UPrimalItem* item, UPrimalInventoryComponent* inv) {
    if (!item || !inv) return PlainReject::Qty;
    if (item->bIsEngram().Get()) return PlainReject::Engram;
    if (item->bIsBlueprint().Get()) return PlainReject::Blueprint;
    if (item->bEquippedItem().Get()) return PlainReject::Equipped;
    if (item->bUseItemDurability().Get()) return PlainReject::Durability;
    if (item->ItemRatingField() > 0.0001f) return PlainReject::Rating;
    const int qty = item->GetItemQuantity();
    if (qty <= 0) return PlainReject::Qty;

    UPrimalInventoryComponent* owner = item->OwnerInventoryField().Get();
    if (owner && owner != inv) return PlainReject::Owner;

    UWorld* world = ArkApi::GetApiUtils().GetWorld();
    if (!world) return PlainReject::Qty;
    // Stack do cadastro nao filtra. Quantidade acima do maximo vanilla (Couro x100000
    // com hide em 100/200) continua sendo o recurso. So rejeita item realmente nao empilhavel.
    if (MaxStackOf(item, world) <= 1 && qty <= 1) return PlainReject::MaxStack;
    return PlainReject::Ok;
}

bool IsPlainStackable(UPrimalItem* item, UPrimalInventoryComponent* inv) {
    return ClassifyPlain(item, inv) == PlainReject::Ok;
}

const char* BlockedReasonMessage(int reason) {
    switch (static_cast<PlainReject>(reason)) {
    case PlainReject::Engram:
        return "So o engrama desse recurso foi encontrado. A vitrine precisa do item solto no inventario.";
    case PlainReject::Blueprint:
        return "Voce tem o blueprint desse recurso, nao o item. A vitrine so aceita o item fabricado, solto no inventario.";
    case PlainReject::Equipped:
        return "O recurso autorizado esta equipado. Tire do corpo e deixe solto no inventario pessoal.";
    case PlainReject::Durability:
        return "O recurso autorizado tem durabilidade (equipamento ou perecivel). "
               "A vitrine so aceita recurso comum sem durabilidade.";
    case PlainReject::Rating:
        return "O item autorizado tem qualidade (rating). A vitrine so aceita recurso comum sem rating.";
    case PlainReject::MaxStack:
        return "O recurso autorizado nao e empilhavel. A vitrine so aceita itens com stack maior que 1.";
    default:
        return nullptr;
    }
}

/** Inventario pessoal: itens + hotbar (dedup por ponteiro). Sem cofres/criaturas. */
std::vector<UPrimalItem*> CollectPersonalItems(UPrimalInventoryComponent* inv) {
    std::vector<UPrimalItem*> out;
    if (!inv) return out;
    std::unordered_set<UPrimalItem*> seen;
    const auto add = [&](TArray<UPrimalItem*> arr) {
        for (int i = 0; i < arr.Num(); ++i) {
            UPrimalItem* item = arr[i];
            if (item && seen.insert(item).second)
                out.push_back(item);
        }
    };
    add(inv->InventoryItemsField());
    add(inv->ItemSlotsField());
    return out;
}

/** key -> (quantidade total, classe canonica, chave que CountPlain entende). */
struct Totals {
    int quantity = 0;
    std::string bp_class;
    std::string match_key;
};

struct InventoryScan {
    std::unordered_map<std::string, Totals> plain;
    std::unordered_map<std::string, int> blocked;  // chave -> PlainReject
    std::vector<std::string> sample;
    int plain_stacks = 0;
    int items_read = 0;
    std::string trace_raw;
    std::string trace_key;
    bool saw_hide = false;
};

InventoryScan ScanInventory(AShooterPlayerController* player) {
    InventoryScan scan;
    if (!player) return scan;
    UPrimalInventoryComponent* inv = player->GetPlayerInventoryComponent();
    if (!inv) return scan;

    struct Row {
        ItemIdentity id;
        int qty = 0;
        int reject = 0;
    };
    std::vector<Row> rows;
    std::unordered_map<std::string, std::string> short_full;
    std::unordered_set<std::string> short_ambiguous;

    for (UPrimalItem* item : CollectPersonalItems(inv)) {
        ++scan.items_read;
        const ItemIdentity id = IdentifyItem(item);
        const std::string blob = ToLower(id.raw + " " + id.canonical + " " + id.short_key + " " + id.full_key);
        const bool is_hide = blob.find("primalitemresource_hide") != std::string::npos;
        if (!scan.saw_hide && (scan.trace_raw.empty() || is_hide)) {
            scan.trace_raw = id.raw;
            scan.trace_key = !id.full_key.empty() ? id.full_key : id.short_key;
            if (is_hide) scan.saw_hide = true;
        }
        if (id.full_key.empty() && id.short_key.empty() && id.alt_key.empty()) continue;
        Row row;
        row.id = id;
        row.reject = static_cast<int>(ClassifyPlain(item, inv));
        row.qty = row.reject == static_cast<int>(PlainReject::Ok) ? item->GetItemQuantity() : 0;
        rows.push_back(row);
        if (!id.full_key.empty() && !id.short_key.empty() && id.short_key != id.full_key) {
            const auto it = short_full.find(id.short_key);
            if (it == short_full.end()) short_full.emplace(id.short_key, id.full_key);
            else if (it->second != id.full_key) short_ambiguous.insert(id.short_key);
        }
        if (scan.sample.size() < 4 && row.reject != static_cast<int>(PlainReject::Engram)) {
            if (!id.canonical.empty()) scan.sample.push_back(id.canonical);
            else if (!id.short_key.empty()) scan.sample.push_back(id.short_key);
        }
    }

    const auto bump = [&](const std::string& key, const Row& row) {
        if (key.empty() || row.qty <= 0) return;
        Totals& t = scan.plain[key];
        const long long next = static_cast<long long>(t.quantity) + row.qty;
        t.quantity = static_cast<int>(std::min<long long>(next, 2000000000LL));
        if (t.bp_class.empty())
            t.bp_class = !row.id.canonical.empty() ? row.id.canonical : row.id.short_key;
        if (t.match_key.empty())
            t.match_key = !row.id.full_key.empty() ? row.id.full_key : row.id.short_key;
    };
    const auto note_blocked = [&](const std::string& key, int reason) {
        if (key.empty() || reason == static_cast<int>(PlainReject::Ok)) return;
        if (!scan.blocked.count(key)) scan.blocked.emplace(key, reason);
    };

    for (const Row& row : rows) {
        const bool plain = row.reject == static_cast<int>(PlainReject::Ok) && row.qty > 0;
        if (!plain) {
            // Engrama fica no inventario o tempo todo: nao e "o item na mao".
            if (row.reject != static_cast<int>(PlainReject::Engram)
                && row.reject != static_cast<int>(PlainReject::Qty)
                && row.reject != static_cast<int>(PlainReject::Owner)) {
                note_blocked(row.id.full_key, row.reject);
                note_blocked(row.id.alt_key, row.reject);
                if (!short_ambiguous.count(row.id.short_key))
                    note_blocked(row.id.short_key, row.reject);
            }
            continue;
        }
        ++scan.plain_stacks;
        for (const std::string& key : row.id.keys) {
            if (key.find('/') == std::string::npos && short_ambiguous.count(key)) continue;
            bump(key, row);
        }
    }
    return scan;
}

int CountPlain(AShooterPlayerController* player, const std::string& key) {
    if (!player || key.empty()) return 0;
    UPrimalInventoryComponent* inv = player->GetPlayerInventoryComponent();
    if (!inv) return 0;
    long long total = 0;
    for (UPrimalItem* item : CollectPersonalItems(inv)) {
        if (!IsPlainStackable(item, inv)) continue;
        if (ItemClassKey(item, nullptr) != key) continue;
        total += item->GetItemQuantity();
    }
    return static_cast<int>(std::min<long long>(total, 2000000000LL));
}

/** Remove ate `amount` unidades do recurso (stacks menores primeiro). Retorna o que a API reportou. */
int RemovePlain(AShooterPlayerController* player, const std::string& key, int amount) {
    if (!player || key.empty() || amount <= 0) return 0;
    UPrimalInventoryComponent* inv = player->GetPlayerInventoryComponent();
    if (!inv) return 0;

    std::vector<std::pair<int, UPrimalItem*>> stacks;
    for (UPrimalItem* item : CollectPersonalItems(inv)) {
        if (!IsPlainStackable(item, inv)) continue;
        if (ItemClassKey(item, nullptr) != key) continue;
        stacks.emplace_back(item->GetItemQuantity(), item);
    }
    std::sort(stacks.begin(), stacks.end(),
              [](const auto& a, const auto& b) { return a.first < b.first; });

    auto& cloud = ShopCloudInventory::Get();
    int remaining = amount;
    int removed = 0;
    for (auto& entry : stacks) {
        if (remaining <= 0) break;
        UPrimalItem* item = entry.second;
        const int qty = entry.first;
        if (!item || qty <= 0) continue;

        if (qty <= remaining) {
            if (!cloud.RemovePlayerItem(item, inv, player)) {
                Log::GetLog()->error(
                    "ShopVitrine: falha ao remover stack key={} qty={}", key, qty);
                break;
            }
            removed += qty;
            remaining -= qty;
        } else {
            const int left = qty - remaining;
            item->SetQuantity(left, /*ShowHUDNotification=*/false);
            inv->NotifyItemQuantityUpdated(item, -remaining);
            inv->NotifyClientsItemStatus(
                item, /*bEquippedItem=*/false, /*bRemovedItem=*/false,
                /*bOnlyUpdateQuantity=*/true, false, false,
                nullptr, nullptr, false, false, false);
            removed += remaining;
            remaining = 0;
        }
    }
    return removed;
}

int InventoryCapacity(UPrimalInventoryComponent* inv) {
    if (!inv) return 0;
    const int from_native = inv->GetMaxInventoryItems(true);
    if (from_native > 0) return from_native;
    const int field_max = inv->MaxInventoryItemsField();
    if (field_max > 0) return field_max;
    return inv->AbsoluteMaxInventoryItemsField();
}

int CountOccupiedSlots(UPrimalInventoryComponent* inv) {
    if (!inv) return 0;
    std::unordered_set<UPrimalItem*> excluded;
    const auto add_excl = [&](TArray<UPrimalItem*> arr) {
        for (int i = 0; i < arr.Num(); ++i)
            if (arr[i]) excluded.insert(arr[i]);
    };
    add_excl(inv->AllDyeColorItemsField());
    add_excl(inv->ArkTributeItemsField());
    add_excl(inv->CraftingItemsField());

    std::unordered_set<UPrimalItem*> seen;
    const auto count = [&](TArray<UPrimalItem*> arr) {
        for (int i = 0; i < arr.Num(); ++i) {
            UPrimalItem* item = arr[i];
            if (!item || excluded.count(item)) continue;
            if (item->bIsEngram().Get()) continue;
            if (item->GetItemQuantity() <= 0) continue;
            seen.insert(item);
        }
    };
    count(inv->EquippedItemsField());
    count(inv->ItemSlotsField());
    count(inv->InventoryItemsField());
    return static_cast<int>(seen.size());
}

/** Stack efetivo = admin limitado ao maximo real do jogo (0 se a classe nao carrega). */
int EffectiveStack(const std::string& blueprint, int admin_stack) {
    std::string canonical;
    if (!NormalizeBlueprint(blueprint, &canonical, nullptr)) return 0;
    FString fbp(canonical.c_str());
    UClass* cls = UVictoryCore::BPLoadClass(&fbp);
    if (!cls) return 0;
    int per = admin_stack;
    if (UPrimalItem* cdo = static_cast<UPrimalItem*>(cls->GetDefaultObject(true))) {
        const int real_max = cdo->GetMaxItemQuantity(ArkApi::GetApiUtils().GetWorld());
        if (real_max > 1 && (per <= 0 || per > real_max)) per = real_max;
    }
    return per < 1 ? 1 : per;
}

/** true se ha (ou nao da para saber que nao ha) espaco para `quantity` unidades. */
bool HasRoomFor(AShooterPlayerController* player, const std::string& key,
                const std::string& blueprint, int quantity, int admin_stack) {
    if (!player) return false;
    UPrimalInventoryComponent* inv = player->GetPlayerInventoryComponent();
    if (!inv) return false;
    const int eff = EffectiveStack(blueprint, admin_stack);
    if (eff <= 0) return false;  // classe nao carrega: nao tentar entregar
    const int cap = InventoryCapacity(inv);
    if (cap <= 0) return true;

    long long room_in_partials = 0;
    for (UPrimalItem* item : CollectPersonalItems(inv)) {
        if (!IsPlainStackable(item, inv)) continue;
        if (ItemClassKey(item, nullptr) != key) continue;
        room_in_partials += std::max(0, eff - item->GetItemQuantity());
    }
    const long long need_units = std::max<long long>(0, quantity - room_in_partials);
    const long long need_slots = (need_units + eff - 1) / eff;
    const int free_slots = std::max(0, cap - CountOccupiedSlots(inv));
    return free_slots >= need_slots;
}

/** Entrega e MEDE o delta real no inventario (fonte de verdade). */
int GiveAndMeasure(AShooterPlayerController* player, const std::string& key,
                   const std::string& blueprint, int quantity, int admin_stack) {
    if (!player || quantity <= 0) return 0;
    const int before = CountPlain(player, key);
    Store::GiveResourceStacks(player, blueprint, quantity, admin_stack);
    const int after = CountPlain(player, key);
    return std::max(0, std::min(quantity, after - before));
}

// ── Journal ──────────────────────────────────────────────────────

struct JLine {
    int resource_id = 0;
    std::string key;
    std::string blueprint;
    std::string bp_class;
    std::string name;
    int stack_size = 0;
    int quantity = 0;   // pretendido
    int removed = 0;    // medido no inventario
    int returned = 0;   // devolvido ao jogador (rollback)
};

struct Journal {
    std::string path;
    std::string kind = "upload";  // "upload" | "ack"
    std::string upload_id;
    std::string steam_id;
    std::string state = "planned";  // planned | removed
    bool abort = false;             // upload CANCELLED confirmado: so devolver itens
    long long created_at = 0;
    std::vector<JLine> lines;
    int claim_id = 0;               // kind=ack
};

std::string JournalDir() {
    return ArkApi::Tools::GetCurrentDir() + "/ArkApi/Plugins/CustomShop/vitrine_journal";
}

bool EnsureJournalDir() {
    const std::string dir = JournalDir();
    if (CreateDirectoryA(dir.c_str(), nullptr)) return true;
    return GetLastError() == ERROR_ALREADY_EXISTS;
}

std::string ToWinPath(std::string p) {
    std::replace(p.begin(), p.end(), '/', '\\');
    return p;
}

bool WriteFileAtomic(const std::string& path, const std::string& data) {
    const std::string final_path = ToWinPath(path);
    const std::string tmp_path = final_path + ".tmp";
    HANDLE h = CreateFileA(tmp_path.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS,
                           FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) return false;
    bool ok = true;
    size_t offset = 0;
    while (ok && offset < data.size()) {
        DWORD written = 0;
        const DWORD chunk = static_cast<DWORD>(std::min<size_t>(data.size() - offset, 1u << 20));
        if (!WriteFile(h, data.data() + offset, chunk, &written, nullptr) || written == 0)
            ok = false;
        offset += written;
    }
    if (ok && !FlushFileBuffers(h)) ok = false;
    CloseHandle(h);
    if (!ok) {
        DeleteFileA(tmp_path.c_str());
        return false;
    }
    if (!MoveFileExA(tmp_path.c_str(), final_path.c_str(),
                     MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        DeleteFileA(tmp_path.c_str());
        return false;
    }
    return true;
}

bool ReadWholeFile(const std::string& path, std::string& out) {
    std::ifstream in(ToWinPath(path), std::ios::binary);
    if (!in) return false;
    std::ostringstream ss;
    ss << in.rdbuf();
    out = ss.str();
    return true;
}

nlohmann::json JournalToJson(const Journal& j) {
    nlohmann::json lines = nlohmann::json::array();
    for (const JLine& l : j.lines) {
        lines.push_back({
            {"resource_id", l.resource_id},
            {"key", l.key},
            {"blueprint", l.blueprint},
            {"bp_class", l.bp_class},
            {"name", l.name},
            {"stack_size", l.stack_size},
            {"quantity", l.quantity},
            {"removed", l.removed},
            {"returned", l.returned},
        });
    }
    return {
        {"version", 1},
        {"kind", j.kind},
        {"upload_id", j.upload_id},
        {"steam_id", j.steam_id},
        {"state", j.state},
        {"abort", j.abort},
        {"created_at", j.created_at},
        {"claim_id", j.claim_id},
        {"lines", lines},
    };
}

bool JournalFromJson(const nlohmann::json& js, Journal& j) {
    if (!js.is_object()) return false;
    j.kind = JsonGet<std::string>(js, "kind", "upload");
    j.upload_id = JsonGet<std::string>(js, "upload_id", "");
    j.steam_id = JsonGet<std::string>(js, "steam_id", "");
    j.state = JsonGet<std::string>(js, "state", "planned");
    j.abort = JsonGet<bool>(js, "abort", false);
    j.created_at = JsonGet<long long>(js, "created_at", 0);
    j.claim_id = JsonGet<int>(js, "claim_id", 0);
    j.lines.clear();
    if (js.contains("lines") && js["lines"].is_array()) {
        for (const auto& item : js["lines"]) {
            JLine l;
            l.resource_id = JsonGet<int>(item, "resource_id", 0);
            l.key = JsonGet<std::string>(item, "key", "");
            l.blueprint = JsonGet<std::string>(item, "blueprint", "");
            l.bp_class = JsonGet<std::string>(item, "bp_class", "");
            l.name = JsonGet<std::string>(item, "name", "");
            l.stack_size = JsonGet<int>(item, "stack_size", 0);
            l.quantity = JsonGet<int>(item, "quantity", 0);
            l.removed = JsonGet<int>(item, "removed", 0);
            l.returned = JsonGet<int>(item, "returned", 0);
            j.lines.push_back(std::move(l));
        }
    }
    if (j.steam_id.empty()) return false;
    if (j.kind == "upload") return IsSafeToken(j.upload_id);
    if (j.kind == "ack") return j.claim_id > 0;
    return false;
}

bool SaveJournal(const Journal& j) {
    if (j.path.empty() || !EnsureJournalDir()) return false;
    return WriteFileAtomic(j.path, JournalToJson(j).dump());
}

void DeleteJournal(const Journal& j) {
    if (!j.path.empty())
        DeleteFileA(ToWinPath(j.path).c_str());
}

std::vector<Journal> LoadJournals() {
    std::vector<Journal> out;
    const std::string dir = ToWinPath(JournalDir());
    WIN32_FIND_DATAA fd{};
    HANDLE h = FindFirstFileA((dir + "\\*.json").c_str(), &fd);
    if (h == INVALID_HANDLE_VALUE) return out;
    do {
        if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) continue;
        const std::string name = fd.cFileName;
        if (name.size() < 6 || name.compare(name.size() - 5, 5, ".json") != 0) continue;
        Journal j;
        j.path = dir + "\\" + name;
        std::string text;
        nlohmann::json js;
        bool ok = false;
        try {
            ok = ReadWholeFile(j.path, text) && ParseObject(text, js) && JournalFromJson(js, j);
        } catch (...) {
            ok = false;
        }
        if (!ok) {
            Log::GetLog()->error("ShopVitrine: journal ilegivel/invalido (mantido): {}", name);
            continue;
        }
        out.push_back(std::move(j));
    } while (FindNextFileA(h, &fd));
    FindClose(h);
    return out;
}

std::string UploadJournalPath(const std::string& upload_id) {
    return JournalDir() + "/" + upload_id + ".json";
}

bool HasUploadJournal(const std::string& steam_id) {
    for (const Journal& j : LoadJournals()) {
        if (j.kind == "upload" && j.steam_id == steam_id) return true;
    }
    return false;
}

// ── HTTP ─────────────────────────────────────────────────────────

bool IsDefinitiveCode(const std::string& code) {
    return code == "invalid_input" || code == "not_authorized_resource"
        || code == "type_limit" || code == "stock_cap" || code == "upload_cancelled";
}

enum class PostKind { Applied, Definitive, Transient };

struct UploadReply {
    PostKind kind = PostKind::Transient;
    std::string code;
    std::string error;
    nlohmann::json credited = nlohmann::json::array();
};

UploadReply PostUpload(const Journal& j) {
    UploadReply reply;
    nlohmann::json items = nlohmann::json::array();
    for (const JLine& l : j.lines) {
        const int qty = l.removed - l.returned;
        if (qty <= 0) continue;
        items.push_back({{"blueprint", l.blueprint}, {"quantity", qty}});
    }
    if (items.empty()) {
        reply.kind = PostKind::Definitive;
        reply.code = "invalid_input";
        reply.error = "nenhum item";
        return reply;
    }
    const nlohmann::json body = {
        {"steam_id", j.steam_id},
        {"upload_id", j.upload_id},
        {"items", items},
    };
    const std::string resp =
        HttpClient::PostJson(std::string(kApi) + "/upload", body.dump());
    nlohmann::json json;
    if (!ParseObject(resp, json)) return reply;  // sem resposta = transitorio
    if (JsonGet<bool>(json, "ok", false)) {
        reply.kind = PostKind::Applied;
        if (json.contains("credited") && json["credited"].is_array())
            reply.credited = json["credited"];
        return reply;
    }
    reply.code = JsonGet<std::string>(json, "code", "");
    reply.error = JsonGet<std::string>(json, "error", "");
    reply.kind = IsDefinitiveCode(reply.code) ? PostKind::Definitive : PostKind::Transient;
    return reply;
}

/** "CANCELLED" | "APPLIED" | "" (sem resposta util). */
std::string CancelUpload(const Journal& j) {
    const nlohmann::json body = {{"steam_id", j.steam_id}, {"upload_id", j.upload_id}};
    const std::string resp =
        HttpClient::PostJson(std::string(kApi) + "/upload/cancel", body.dump());
    nlohmann::json json;
    if (!ParseObject(resp, json) || !JsonGet<bool>(json, "ok", false)) return {};
    const std::string status = JsonGet<std::string>(json, "status", "");
    return (status == "CANCELLED" || status == "APPLIED") ? status : std::string();
}

/** "APPLIED" | "CANCELLED" | "UNKNOWN" | "" (sem resposta). */
std::string GetUploadStatus(const std::string& upload_id) {
    const std::string resp = HttpClient::Get(std::string(kApi) + "/upload/" + upload_id);
    nlohmann::json json;
    if (!ParseObject(resp, json) || !JsonGet<bool>(json, "ok", false)) return {};
    const std::string status = JsonGet<std::string>(json, "status", "");
    if (status == "APPLIED" || status == "CANCELLED" || status == "UNKNOWN") return status;
    return {};
}

enum class AckResult { Ok, Final, Retry };

AckResult PostDelivered(const std::string& steam_id, int claim_id) {
    const nlohmann::json body = {{"steam_id", steam_id}, {"claim_id", claim_id}};
    const std::string resp =
        HttpClient::PostJson(std::string(kApi) + "/claims/delivered", body.dump());
    nlohmann::json json;
    if (!ParseObject(resp, json)) return AckResult::Retry;
    if (JsonGet<bool>(json, "ok", false)) return AckResult::Ok;
    const std::string code = JsonGet<std::string>(json, "code", "");
    if (code == "claim_expired" || code == "not_found" || code == "invalid_input")
        return AckResult::Final;
    return AckResult::Retry;
}

void PostRelease(const std::string& steam_id, int claim_id) {
    const nlohmann::json body = {
        {"steam_id", steam_id}, {"claim_ids", nlohmann::json::array({claim_id})}};
    for (int attempt = 0; attempt < 2; ++attempt) {
        const std::string resp =
            HttpClient::PostJson(std::string(kApi) + "/claims/release", body.dump());
        nlohmann::json json;
        if (ParseObject(resp, json) && JsonGet<bool>(json, "ok", false)) return;
    }
    Log::GetLog()->warn(
        "ShopVitrine: release do claim {} sem confirmacao (expira por TTL/grace)", claim_id);
}

// ── Devolucao / recuperacao ──────────────────────────────────────

std::string LineLabel(const JLine& l) {
    return FormatQty(l.removed) + " " + (l.name.empty() ? std::string("recurso") : l.name);
}

/** Devolve ao jogador o que foi removido e ainda nao devolvido. true = tudo devolvido (journal apagado). */
bool ReturnItems(Journal& j, AShooterPlayerController* player) {
    if (!PlayerReady(player)) return false;
    j.abort = true;
    j.state = "removed";
    SaveJournal(j);  // abort=true persistido antes de devolver (nao reenviar)

    bool all = true;
    for (JLine& l : j.lines) {
        const int remaining = l.removed - l.returned;
        if (remaining <= 0) continue;
        const std::string bp = !l.bp_class.empty() ? l.bp_class : l.blueprint;
        const int given = GiveAndMeasure(player, l.key, bp, remaining, l.stack_size);
        l.returned += given;
        SaveJournal(j);
        if (given < remaining) {
            all = false;
            Log::GetLog()->error(
                "ShopVitrine: devolucao parcial steam={} upload={} key={} faltam={}",
                j.steam_id, j.upload_id, l.key, remaining - given);
        }
    }
    if (all) {
        DeleteJournal(j);
        Log::GetLog()->info("ShopVitrine: itens devolvidos steam={} upload={}",
                            j.steam_id, j.upload_id);
    }
    return all;
}

std::string DescribeLines(const Journal& j) {
    std::string out;
    int n = 0;
    for (const JLine& l : j.lines) {
        if (l.removed <= 0) continue;
        if (!out.empty()) out += ", ";
        out += LineLabel(l);
        if (++n >= 6) { out += ", ..."; break; }
    }
    return out;
}

enum class JournalOutcome { Done, Kept };

/**
 * Processa um journal. `player` pode ser nulo (offline): conclui o que nao exige o jogador
 * (reenvio/limpeza) e deixa a devolucao de itens para o login.
 */
JournalOutcome ProcessJournal(Journal& j, AShooterPlayerController* player) {
    if (j.kind == "ack") {
        const AckResult r = PostDelivered(j.steam_id, j.claim_id);
        if (r == AckResult::Retry) return JournalOutcome::Kept;
        if (r == AckResult::Final)
            Log::GetLog()->error(
                "ShopVitrine: ack delivered claim={} steam={} rejeitado (claim ja processado) — conferir suporte",
                j.claim_id, j.steam_id);
        DeleteJournal(j);
        return JournalOutcome::Done;
    }

    if (j.state == "planned" && !j.abort) {
        // Remocao nunca foi confirmada (journal gravado antes de tirar itens): nada a fazer.
        Log::GetLog()->warn(
            "ShopVitrine: journal 'planned' descartado upload={} steam={}", j.upload_id, j.steam_id);
        DeleteJournal(j);
        return JournalOutcome::Done;
    }

    const auto try_return = [&]() -> JournalOutcome {
        if (!player || !PlayerReady(player)) return JournalOutcome::Kept;
        const bool ok = ReturnItems(j, player);
        if (ok)
            SendMsg(player, "Envio anterior da vitrine nao foi concluido: itens devolvidos ao inventario ("
                                + DescribeLines(j) + ").");
        else
            SendMsg(player, "Nao foi possivel devolver todos os itens da vitrine (inventario cheio?). "
                            "Libere espaco e entre/digite /vitrine para tentar de novo.");
        return ok ? JournalOutcome::Done : JournalOutcome::Kept;
    };

    if (j.abort) return try_return();

    // state == removed, upload ainda nao resolvido
    const std::string status = GetUploadStatus(j.upload_id);
    if (status == "APPLIED") {
        DeleteJournal(j);
        Log::GetLog()->info("ShopVitrine: recuperacao — upload {} ja APPLIED", j.upload_id);
        if (player)
            SendMsg(player, "Envio anterior da vitrine concluido (" + DescribeLines(j) + ").");
        return JournalOutcome::Done;
    }

    bool cancelled = (status == "CANCELLED");
    if (status == "UNKNOWN") {
        const UploadReply reply = PostUpload(j);
        if (reply.kind == PostKind::Applied) {
            DeleteJournal(j);
            Log::GetLog()->info("ShopVitrine: recuperacao — upload {} reenviado com sucesso",
                                j.upload_id);
            if (player)
                SendMsg(player, "Envio anterior da vitrine concluido (" + DescribeLines(j) + ").");
            return JournalOutcome::Done;
        }
        if (reply.kind == PostKind::Definitive) {
            const std::string c = CancelUpload(j);
            if (c == "APPLIED") {
                DeleteJournal(j);
                return JournalOutcome::Done;
            }
            cancelled = (c == "CANCELLED");
        }
        // Transient: web fora -> mantem journal.
    }

    if (!cancelled) return JournalOutcome::Kept;

    j.abort = true;
    j.state = "removed";
    SaveJournal(j);
    return try_return();
}

// ── Config / estoque (API) ───────────────────────────────────────

bool FetchConfig(std::vector<Resource>& out, int& max_types) {
    out.clear();
    max_types = 0;
    nlohmann::json json;
    if (!ParseObject(HttpClient::Get(std::string(kApi) + "/config"), json)) return false;
    if (!JsonGet<bool>(json, "ok", false)) return false;
    max_types = std::max(1, JsonGet<int>(json, "max_types_per_player", 5));
    if (!json.contains("resources") || !json["resources"].is_array()) return false;
    for (const auto& r : json["resources"]) {
        Resource res;
        res.id = JsonGet<int>(r, "id", 0);
        res.blueprint = JsonGet<std::string>(r, "blueprint", "");
        res.name = JsonGet<std::string>(r, "name", "");
        res.name_ascii = JsonGet<std::string>(r, "name_ascii", res.name);
        res.stack_size = JsonGet<int>(r, "stack_size", 0);
        std::string key = ToLower(JsonGet<std::string>(r, "key", ""));
        std::string canonical;
        std::string my_key;
        if (NormalizeBlueprint(res.blueprint, &canonical, &my_key)) {
            res.blueprint = canonical;
            key = my_key;
        }
        res.key = key;
        res.short_key = ShortToken(res.key);
        if (res.short_key.empty()) res.short_key = ShortToken(res.blueprint);
        if (res.id <= 0 || res.key.empty() || res.blueprint.empty()) continue;
        if (res.name_ascii.empty()) res.name_ascii = "Recurso " + std::to_string(res.id);
        out.push_back(std::move(res));
    }
    return true;
}

bool FillCatalogResource(const nlohmann::json& r, Resource& res, bool require_id) {
    if (!r.is_object()) return false;
    if (r.contains("enabled") && !r["enabled"].is_null()) {
        bool enabled = true;
        if (r["enabled"].is_boolean()) enabled = r["enabled"].get<bool>();
        else if (r["enabled"].is_number()) enabled = r["enabled"].get<int>() != 0;
        if (!enabled) return false;
    }
    res.id = JsonGet<int>(r, "id", 0);
    res.blueprint = JsonGet<std::string>(r, "blueprint", "");
    res.name = JsonGet<std::string>(r, "name", "");
    res.name_ascii = JsonGet<std::string>(r, "name_ascii", res.name);
    res.stack_size = JsonGet<int>(r, "stack_size", 0);
    const VitrineMatch::Identity ident = VitrineMatch::Identify(res.blueprint);
    if (!ident.key.empty()) {
        res.blueprint = ident.path;
        res.key = ident.key;
    } else if (!ident.short_key.empty()) {
        res.key = ident.short_key;
        if (res.blueprint.empty()) res.blueprint = ident.short_key;
    }
    res.short_key = !ident.short_key.empty() ? ident.short_key : ShortToken(res.key);
    if (require_id && res.id <= 0) return false;
    if (res.key.empty()) return false;
    if (res.name_ascii.empty()) res.name_ascii = res.name.empty() ? std::string("Recurso") : res.name;
    return true;
}

/** true se o arquivo tem o bloco (mesmo com zero recursos habilitados). */
bool ParseVitrineBlock(const nlohmann::json& root, std::vector<Resource>& out, int& max_types) {
    const nlohmann::json* block = nullptr;
    if (root.contains("ResourceVitrine") && root["ResourceVitrine"].is_object())
        block = &root["ResourceVitrine"];
    else if (root.contains("VitrineResources") && root["VitrineResources"].is_object())
        block = &root["VitrineResources"];
    if (!block) return false;
    if (block->contains("resources") && !(*block)["resources"].is_array()) return false;
    max_types = std::max(1, JsonGet<int>(*block, "max_types_per_player", max_types > 0 ? max_types : 5));
    out.clear();
    if (block->contains("resources")) {
        for (const auto& r : (*block)["resources"]) {
            Resource res;
            if (!FillCatalogResource(r, res, false)) continue;
            out.push_back(std::move(res));
        }
    }
    return true;
}

bool LoadResourcesFromCatalogFile(std::vector<Resource>& out, int& max_types, std::string& path_used) {
    out.clear();
    path_used.clear();
    const ShopConfig& cfg = ShopConfig::Get();
    std::vector<std::string> paths;
    if (!cfg.SharedCatalogPath().empty()) paths.push_back(cfg.SharedCatalogPath());
    if (!cfg.LocalConfigPath().empty() && cfg.LocalConfigPath() != cfg.SharedCatalogPath())
        paths.push_back(cfg.LocalConfigPath());
    for (const std::string& path : paths) {
        std::ifstream file(path);
        if (!file.is_open()) continue;
        nlohmann::json root;
        try {
            file >> root;
        } catch (...) {
            continue;
        }
        if (!root.is_object()) continue;
        std::vector<Resource> parsed;
        int mt = max_types;
        if (!ParseVitrineBlock(root, parsed, mt)) continue;
        path_used = path;
        max_types = mt;
        out = std::move(parsed);
        return true;
    }
    return false;
}

void LogVitrineRead(const std::string& origem, const std::string& arquivo,
                    const std::vector<Resource>& resources, const InventoryScan& scan) {
    std::string chave = scan.trace_key;
    std::string cru = scan.trace_raw;
    if (cru.size() > 180) cru.resize(180);
    for (char& ch : cru) {
        if (ch == '\n' || ch == '\r') ch = ' ';
    }
    std::string msg = "vitrine origem=" + origem
        + " recursos=" + std::to_string(resources.size())
        + " itens=" + std::to_string(scan.items_read)
        + " chave=" + (chave.empty() ? std::string("-") : chave)
        + " cru=" + (cru.empty() ? std::string("-") : cru);
    if (!resources.empty()) {
        const std::string cadastro = !resources[0].key.empty() ? resources[0].key : resources[0].short_key;
        if (!cadastro.empty()) msg += " cadastro=" + cadastro;
    }
    if (!arquivo.empty()) msg += " arquivo=" + arquivo;
    Debug::WriteAlways("Vitrine", msg);
    Log::GetLog()->info("ShopVitrine: {}", msg);
}

bool FetchStock(const std::string& steam_id, std::set<int>& types, int& max_types) {
    types.clear();
    nlohmann::json json;
    if (!ParseObject(HttpClient::Get(std::string(kApi) + "/stock/" + steam_id), json)) return false;
    if (!JsonGet<bool>(json, "ok", false)) return false;
    max_types = std::max(1, JsonGet<int>(json, "max_types", max_types));
    if (json.contains("types") && json["types"].is_array()) {
        for (const auto& t : json["types"]) {
            try { types.insert(t.get<int>()); } catch (...) {}
        }
    }
    return true;
}

// ── Pending ──────────────────────────────────────────────────────

bool PendingStillValid(const std::string& steam_id) {
    std::lock_guard<std::mutex> lock(g_pending_mutex);
    const auto it = g_pending.find(steam_id);
    if (it == g_pending.end()) return false;
    if (std::chrono::steady_clock::now() > it->second.expires) {
        g_pending.erase(it);
        return false;
    }
    return true;
}

std::string OtherPendingName(const std::string& sid) {
    if (Engrams::HasPendingUnlock(sid)) return "/engramas";
    if (Notes::HasPendingUnlock(sid)) return "/notas";
    if (Teams::HasPendingDeposit(sid)) return "/marco";
    if (ShopMarket::HasPendingEnviar(sid)) return "/enviar";
    return {};
}

// ── /vitrine ─────────────────────────────────────────────────────

void CmdVitrine(AShooterPlayerController* player, FString*, EChatSendMode::Type) {
    if (!player) return;
    if (!ShopConfig::Get().VitrineCommandEnabled()) {
        SendMsg(player, "O comando /vitrine esta desativado no momento.");
        return;
    }
    const std::string sid = Bridge::GetSteamId(player);
    if (sid.empty()) return;

    if (!PlayerReady(player)) {
        SendMsg(player, "Nao foi possivel iniciar /vitrine. Voce precisa estar vivo.");
        return;
    }

    std::lock_guard<std::recursive_mutex> op_lock(g_op_mutex);

    RecoverForPlayer(player);
    if (HasUploadJournal(sid)) {
        SendMsg(player, "Ha um envio anterior da vitrine em recuperacao. "
                        "Aguarde alguns instantes e libere espaco no inventario; tente /vitrine de novo.");
        return;
    }

    const std::string other = OtherPendingName(sid);
    if (!other.empty()) {
        SendMsg(player, "Voce tem uma confirmacao pendente de " + other
                            + ". Digite /confirmar (ou aguarde expirar) antes de usar /vitrine.");
        return;
    }

    std::vector<Resource> resources;
    int max_types = 0;
    std::string origem = "vazio";
    std::string arquivo;
    const bool http_ok = FetchConfig(resources, max_types);
    if (http_ok && !resources.empty()) {
        origem = "mysql";
    } else {
        std::vector<Resource> from_file;
        int file_max = max_types;
        std::string file_path;
        const bool saw_block = LoadResourcesFromCatalogFile(from_file, file_max, file_path);
        if (!from_file.empty()) {
            resources = std::move(from_file);
            max_types = file_max > 0 ? file_max : max_types;
            origem = "arquivo";
            arquivo = file_path;
        } else if (!http_ok && !saw_block) {
            LogVitrineRead("vazio", "", resources, InventoryScan{});
            SendMsg(player, "Vitrine indisponivel no momento (web). Nada foi removido. Tente mais tarde.");
            return;
        } else {
            LogVitrineRead(saw_block ? "arquivo" : "mysql", file_path, resources, InventoryScan{});
            SendMsg(player, "Nenhum recurso esta autorizado na vitrine ainda. Veja a loja web.");
            return;
        }
    }

    std::set<int> stock_types;
    const bool stock_ok = FetchStock(sid, stock_types, max_types);

    // Soma do inventario pessoal por recurso autorizado.
    // Path completo casa primeiro; token da classe so se for unico no cadastro
    // (GetFullName sem /Game/, ou pasta colada diferente do mesmo item).
    std::unordered_map<std::string, int> short_count;
    for (const Resource& res : resources) {
        if (!res.short_key.empty()) short_count[res.short_key] += 1;
    }
    const InventoryScan scan = ScanInventory(player);
    LogVitrineRead(origem, arquivo, resources, scan);
    std::vector<Line> found;
    int blocked_reason = 0;
    for (const Resource& res : resources) {
        const Totals* hit = nullptr;
        const auto it = scan.plain.find(res.key);
        if (it != scan.plain.end() && it->second.quantity > 0) hit = &it->second;
        else if (!res.short_key.empty() && short_count[res.short_key] == 1) {
            const auto sit = scan.plain.find(res.short_key);
            if (sit != scan.plain.end() && sit->second.quantity > 0) hit = &sit->second;
        }
        if (!hit) {
            if (blocked_reason == 0) {
                auto bit = scan.blocked.find(res.key);
                if (bit == scan.blocked.end() && !res.short_key.empty() && short_count[res.short_key] == 1)
                    bit = scan.blocked.find(res.short_key);
                if (bit != scan.blocked.end()) blocked_reason = bit->second;
            }
            continue;
        }
        Line l;
        l.resource_id = res.id;
        l.key = !hit->match_key.empty() ? hit->match_key : res.key;
        l.blueprint = res.blueprint;
        l.bp_class = !hit->bp_class.empty() ? hit->bp_class : res.blueprint;
        l.name_ascii = res.name_ascii;
        l.stack_size = res.stack_size;
        l.quantity = std::min(hit->quantity, kMaxQtyPerLine);
        found.push_back(std::move(l));
    }

    if (found.empty()) {
        const char* specific = BlockedReasonMessage(blocked_reason);
        if (specific)
            SendMsg(player, specific);
        else
            SendMsg(player, "Nenhum recurso autorizado no seu inventario pessoal "
                            "(cofres, criaturas e itens equipados nao contam).");
        std::string amostra;
        for (size_t i = 0; i < scan.sample.size(); ++i) {
            if (i) amostra += " | ";
            amostra += scan.sample[i];
        }
        Log::GetLog()->info(
            "ShopVitrine: /vitrine sem envio steam={} autorizados={} stacks={} bloqueio={} amostra={}",
            sid, resources.size(), scan.plain_stacks, blocked_reason, amostra);
        return;
    }

    if (!stock_ok) {
        SendMsg(player, "Estoque da vitrine na web nao respondeu. O /confirmar pode falhar; nada foi removido ainda.");
    }

    // Limite de tipos: tipos ja no estoque sempre cabem; novos so ate o limite.
    const int type_count = static_cast<int>(stock_types.size());
    int new_slots = std::max(0, max_types - type_count);
    std::vector<Line> accepted;
    std::vector<std::string> skipped;
    for (Line& l : found) {
        if (stock_types.count(l.resource_id)) {
            accepted.push_back(std::move(l));
        } else if (new_slots > 0) {
            --new_slots;
            accepted.push_back(std::move(l));
        } else {
            skipped.push_back(l.name_ascii);
        }
    }
    if (static_cast<int>(accepted.size()) > kMaxUploadLines)
        accepted.resize(kMaxUploadLines);

    if (!skipped.empty()) {
        std::string names;
        for (size_t i = 0; i < skipped.size(); ++i) {
            if (i) names += ", ";
            names += skipped[i];
        }
        SendMsg(player, "Limite de " + std::to_string(max_types)
                            + " tipos de recurso na vitrine. Ficam de fora (nada removido): " + names);
    }
    if (accepted.empty()) {
        SendMsg(player, "Sua vitrine ja esta no limite de tipos. Venda/retire um tipo na loja web "
                        "antes de enviar outro.");
        return;
    }

    PendingVitrine pending;
    const int ttl = ShopConfig::Get().VitrinePreviewTtlSeconds();
    pending.expires = std::chrono::steady_clock::now() + std::chrono::seconds(ttl);
    pending.lines = accepted;
    {
        std::lock_guard<std::mutex> lock(g_pending_mutex);
        g_pending[sid] = pending;
    }

    SendMsg(player, "Vitrine de Recursos - serao enviados do seu inventario pessoal:");
    int shown = 0;
    for (const Line& l : accepted) {
        if (shown >= kMaxChatLines) {
            SendMsg(player, "... e mais " + std::to_string(accepted.size() - shown) + " tipo(s).");
            break;
        }
        SendMsg(player, "- " + l.name_ascii + ": " + FormatQty(l.quantity));
        ++shown;
    }
    SendMsg(player, "Cofres, criaturas e itens equipados nao entram. Os itens serao REMOVIDOS do inventario.");
    SendMsg(player, "Digite /confirmar em ate " + std::to_string(ttl)
                        + " segundos para enviar. Depois defina lote e preco na loja web (Comercio).");
    Log::GetLog()->info("ShopVitrine: /vitrine preview steam={} tipos={} ttl={}s",
                        sid, accepted.size(), ttl);
}

} // anonymous namespace

// ── API publica ──────────────────────────────────────────────────

bool HasPending(const std::string& steam_id) {
    if (steam_id.empty()) return false;
    return PendingStillValid(steam_id);
}

void ClearPending(const std::string& steam_id) {
    if (steam_id.empty()) return;
    std::lock_guard<std::mutex> lock(g_pending_mutex);
    g_pending.erase(steam_id);
}

void ConfirmPending(AShooterPlayerController* player) {
    if (!player) return;
    const std::string sid = Bridge::GetSteamId(player);
    if (sid.empty()) return;

    std::lock_guard<std::recursive_mutex> op_lock(g_op_mutex);

    PendingVitrine pending;
    {
        std::lock_guard<std::mutex> lock(g_pending_mutex);
        auto it = g_pending.find(sid);
        if (it == g_pending.end()) {
            SendMsg(player, "Nenhum envio da vitrine pendente. Use /vitrine primeiro.");
            return;
        }
        if (std::chrono::steady_clock::now() > it->second.expires) {
            g_pending.erase(it);
            SendMsg(player, "Preview da vitrine expirado. Use /vitrine novamente.");
            return;
        }
        pending = it->second;
        g_pending.erase(it);
    }

    const auto restore_pending = [&]() {
        std::lock_guard<std::mutex> lock(g_pending_mutex);
        g_pending[sid] = pending;
    };

    if (!PlayerReady(player)) {
        restore_pending();
        SendMsg(player, "Voce precisa estar vivo para confirmar a vitrine.");
        return;
    }

    RecoverForPlayer(player);
    if (HasUploadJournal(sid)) {
        restore_pending();
        SendMsg(player, "Ha um envio anterior da vitrine em recuperacao. Aguarde e tente /confirmar de novo.");
        return;
    }

    // Revalida o inventario: usa min(preview, disponivel).
    Journal j;
    j.kind = "upload";
    j.upload_id = NewUploadId();
    j.steam_id = sid;
    j.state = "planned";
    j.created_at = NowUnix();
    j.path = UploadJournalPath(j.upload_id);
    for (const Line& line : pending.lines) {
        const int take = std::min(line.quantity, CountPlain(player, line.key));
        if (take <= 0) continue;
        JLine jl;
        jl.resource_id = line.resource_id;
        jl.key = line.key;
        jl.blueprint = line.blueprint;
        jl.bp_class = line.bp_class;
        jl.name = line.name_ascii;
        jl.stack_size = line.stack_size;
        jl.quantity = take;
        j.lines.push_back(std::move(jl));
    }
    if (j.lines.empty()) {
        SendMsg(player, "Seu inventario mudou: nenhum recurso do preview esta mais disponivel. Use /vitrine de novo.");
        return;
    }

    // 1) Journal ANTES de tirar qualquer item (se nao gravar, nada e removido).
    if (!SaveJournal(j)) {
        restore_pending();
        Log::GetLog()->error("ShopVitrine: nao foi possivel gravar journal {}", j.path);
        SendMsg(player, "Falha ao registrar o envio (disco). Nada foi removido. Avise um admin.");
        return;
    }

    // 2) Remove itens e MEDE o que de fato saiu.
    bool short_removal = false;
    for (JLine& l : j.lines) {
        const int before = CountPlain(player, l.key);
        RemovePlain(player, l.key, l.quantity);
        const int after = CountPlain(player, l.key);
        l.removed = std::max(0, before - after);
        if (l.removed < l.quantity) short_removal = true;
    }

    // 3) Journal "removed" (so depois disso o POST e permitido).
    j.state = "removed";
    const bool journal_ok = SaveJournal(j);

    if (short_removal || !journal_ok) {
        Log::GetLog()->error(
            "ShopVitrine: abortando envio steam={} upload={} short_removal={} journal_ok={}",
            sid, j.upload_id, short_removal, journal_ok);
        const bool back = ReturnItems(j, player);
        if (back) {
            SendMsg(player, "Nao foi possivel remover todos os itens com seguranca. "
                            "Os itens foram devolvidos. Tente /vitrine de novo.");
        } else {
            SendMsg(player, "FALHA: itens retirados nao puderam ser devolvidos agora. "
                            "Libere espaco no inventario; a devolucao sera retomada automaticamente no login.");
        }
        return;
    }

    bool any_removed = false;
    for (const JLine& l : j.lines)
        if (l.removed > 0) any_removed = true;
    if (!any_removed) {
        DeleteJournal(j);
        SendMsg(player, "Nenhum item foi removido. Use /vitrine de novo.");
        return;
    }

    // 4) POST idempotente.
    const UploadReply reply = PostUpload(j);
    if (reply.kind == PostKind::Applied) {
        DeleteJournal(j);
        SendMsg(player, "Vitrine de Recursos: itens enviados com sucesso!");
        for (const JLine& l : j.lines) {
            if (l.removed > 0)
                SendMsg(player, "- " + l.name + ": " + FormatQty(l.removed));
        }
        SendMsg(player, "Defina o tamanho do lote e o preco em Ambar na loja web (Comercio > Vitrine de Recursos).");
        Log::GetLog()->info("ShopVitrine: upload OK steam={} upload={} linhas={}",
                            sid, j.upload_id, j.lines.size());
        return;
    }

    Log::GetLog()->warn(
        "ShopVitrine: upload falhou steam={} upload={} kind={} code={} err={}",
        sid, j.upload_id, reply.kind == PostKind::Definitive ? "definitivo" : "transitorio",
        reply.code, reply.error);

    // 5) Falhou: arbitra com cancel (tombstone atomico no backend).
    const std::string arbiter = CancelUpload(j);
    if (arbiter == "APPLIED") {
        DeleteJournal(j);
        SendMsg(player, "Vitrine de Recursos: itens enviados com sucesso!");
        return;
    }
    if (arbiter == "CANCELLED") {
        const bool back = ReturnItems(j, player);
        if (back) {
            std::string why = reply.error.empty() ? std::string("falha no servidor") : reply.error;
            SendMsg(player, "Envio recusado - itens devolvidos ao inventario. Motivo: " + why);
        } else {
            SendMsg(player, "Envio recusado, mas nem todos os itens couberam de volta. "
                            "Libere espaco; a devolucao continua no login.");
        }
        return;
    }

    // Sem resposta: journal fica (state=removed) para recuperacao automatica.
    SendMsg(player, "Vitrine indisponivel agora (web fora). Seus itens estao protegidos e o envio sera "
                    "retomado automaticamente (ou devolvido) no proximo login/reinicio do mapa.");
    Log::GetLog()->error(
        "ShopVitrine: web indisponivel apos remocao steam={} upload={} — journal mantido",
        sid, j.upload_id);
}

void RecoverForPlayer(AShooterPlayerController* player) {
    if (!player) return;
    const std::string sid = Bridge::GetSteamId(player);
    if (sid.empty()) return;
    std::lock_guard<std::recursive_mutex> op_lock(g_op_mutex);
    try {
        for (Journal& j : LoadJournals()) {
            if (j.steam_id != sid) continue;
            ProcessJournal(j, player);
        }
    } catch (const std::exception& e) {
        Log::GetLog()->error("ShopVitrine: RecoverForPlayer erro: {}", e.what());
    } catch (...) {
        Log::GetLog()->error("ShopVitrine: RecoverForPlayer erro desconhecido");
    }
}

void RecoverForSteamId(const std::string& steam_id) {
    if (steam_id.empty()) return;
    if (ArkApi::GetApiUtils().GetStatus() != ArkApi::ServerStatus::Ready) return;
    AShooterPlayerController* player = Bridge::FindPlayer(steam_id);
    if (!player) return;
    RecoverForPlayer(player);
}

void RecoverAll() {
    std::lock_guard<std::recursive_mutex> op_lock(g_op_mutex);
    try {
        const bool ready = ArkApi::GetApiUtils().GetStatus() == ArkApi::ServerStatus::Ready;
        for (Journal& j : LoadJournals()) {
            AShooterPlayerController* player = ready ? Bridge::FindPlayer(j.steam_id) : nullptr;
            ProcessJournal(j, player);
        }
    } catch (const std::exception& e) {
        Log::GetLog()->error("ShopVitrine: RecoverAll erro: {}", e.what());
    } catch (...) {
        Log::GetLog()->error("ShopVitrine: RecoverAll erro desconhecido");
    }
}

// ── /mercado: entrega de claims de recursos ───────────────────────

namespace {

bool FetchMarketClaims(const std::string& steam_id, nlohmann::json& claims) {
    claims = nlohmann::json::array();
    nlohmann::json json;
    if (!ParseObject(HttpClient::Get(std::string(kApi) + "/pending/" + steam_id), json))
        return false;
    if (!JsonGet<bool>(json, "ok", false)) return false;
    if (json.contains("claims") && json["claims"].is_array())
        claims = json["claims"];
    return true;
}

} // anonymous namespace

bool HasMarketClaims(const std::string& steam_id) {
    if (steam_id.empty()) return false;
    nlohmann::json claims;
    return FetchMarketClaims(steam_id, claims) && !claims.empty();
}

bool DeliverMarketClaims(AShooterPlayerController* player) {
    if (!player) return false;
    const std::string sid = Bridge::GetSteamId(player);
    if (sid.empty()) return false;

    std::lock_guard<std::recursive_mutex> op_lock(g_op_mutex);

    nlohmann::json claims;
    if (!FetchMarketClaims(sid, claims) || claims.empty()) return false;

    // Lista as pendencias junto das de dinos.
    SendMsg(player, "Vitrine de Recursos: " + std::to_string(claims.size())
                        + " pendencia(s) de recurso para resgatar:");
    int listed = 0;
    for (const auto& c : claims) {
        if (listed++ >= kMaxChatLines) break;
        const std::string kind = JsonGet<std::string>(c, "kind", "BUY");
        const double hrs = JsonGet<double>(c, "hours_remaining", 24.0);
        std::string name = JsonGet<std::string>(c, "name_ascii", "");
        if (name.empty()) name = JsonGet<std::string>(c, "name", "Recurso");
        SendMsg(player, "- " + FormatQty(JsonGet<long long>(c, "quantity", 0)) + " " + name
                            + (kind == "WITHDRAW" ? " (retirada)" : " (compra)") + " - "
                            + std::to_string(std::max(1, static_cast<int>(std::ceil(hrs))))
                            + "h restantes");
    }

    if (!PlayerReady(player)) {
        SendMsg(player, "Voce precisa estar vivo para resgatar. Tente /mercado novamente.");
        return true;
    }

    int delivered_total = 0;
    for (const auto& c : claims) {
        const int claim_id = JsonGet<int>(c, "claim_id", 0);
        if (claim_id <= 0) continue;

        // 1) claim (PENDENTE -> CLAIMED)
        const nlohmann::json claim_body = {
            {"steam_id", sid}, {"claim_ids", nlohmann::json::array({claim_id})}};
        nlohmann::json claim_json;
        if (!ParseObject(HttpClient::PostJson(std::string(kApi) + "/claims/claim", claim_body.dump()),
                         claim_json)) {
            SendMsg(player, "Vitrine indisponivel agora. Tente /mercado novamente.");
            break;
        }
        if (!JsonGet<bool>(claim_json, "ok", false)) {
            SendMsg(player, "Resgate indisponivel: "
                                + JsonGet<std::string>(claim_json, "error", "tente novamente"));
            break;
        }
        nlohmann::json claimed_one;
        if (claim_json.contains("claimed") && claim_json["claimed"].is_array()) {
            for (const auto& cc : claim_json["claimed"]) {
                if (JsonGet<int>(cc, "claim_id", 0) == claim_id) { claimed_one = cc; break; }
            }
        }
        if (claimed_one.is_null()) continue;  // ja reivindicado por outra sessao

        const int quantity = JsonGet<int>(claimed_one, "quantity", JsonGet<int>(c, "quantity", 0));
        const int stack_size = JsonGet<int>(claimed_one, "stack_size", JsonGet<int>(c, "stack_size", 0));
        std::string bp_raw = JsonGet<std::string>(claimed_one, "blueprint", JsonGet<std::string>(c, "blueprint", ""));
        std::string name = JsonGet<std::string>(claimed_one, "name_ascii", JsonGet<std::string>(c, "name_ascii", ""));
        if (name.empty()) name = "Recurso";

        std::string canonical, key;
        if (quantity <= 0 || !NormalizeBlueprint(bp_raw, &canonical, &key)) {
            Log::GetLog()->error("ShopVitrine: claim {} invalido (qty={} bp={}) — liberado",
                                 claim_id, quantity, bp_raw);
            PostRelease(sid, claim_id);
            SendMsg(player, "Resgate invalido no servidor - liberado. Contate um admin.");
            break;
        }

        // 2) espaco
        if (!HasRoomFor(player, key, canonical, quantity, stack_size)) {
            PostRelease(sid, claim_id);
            SendMsg(player, "Sem espaco no inventario para receber " + FormatQty(quantity) + " " + name
                                + " (ou recurso indisponivel neste mapa). Libere espaco e digite /mercado "
                                  "novamente (nada foi perdido).");
            break;
        }

        // 3) entrega + conferencia do delta
        const int before = CountPlain(player, key);
        Store::GiveResourceStacks(player, canonical, quantity, stack_size);
        const int after = CountPlain(player, key);
        const int got = std::max(0, after - before);

        if (got < quantity) {
            Log::GetLog()->error(
                "ShopVitrine: entrega incompleta steam={} claim={} esperado={} recebido={}",
                sid, claim_id, quantity, got);
            bool undone = true;
            if (got > 0) {
                const int b2 = CountPlain(player, key);
                RemovePlain(player, key, got);
                const int a2 = CountPlain(player, key);
                undone = (b2 - a2) >= got;
            }
            if (undone) {
                PostRelease(sid, claim_id);
                SendMsg(player, "Nao foi possivel entregar " + FormatQty(quantity) + " " + name
                                    + " (inventario cheio?). Resgate liberado: libere espaco e use /mercado.");
            } else {
                // Nao foi possivel desfazer: NAO liberar (evita entrega dupla); expira pelo grace.
                Log::GetLog()->error(
                    "ShopVitrine: desfazer entrega parcial falhou claim={} — claim mantido CLAIMED", claim_id);
                SendMsg(player, "Falha na entrega de " + name + ". Contate um admin (claim " +
                                    std::to_string(claim_id) + ").");
            }
            break;
        }

        // 4) delivered (com retry + ack persistente se a web nao responder)
        AckResult ack = AckResult::Retry;
        for (int attempt = 0; attempt < 3 && ack == AckResult::Retry; ++attempt)
            ack = PostDelivered(sid, claim_id);
        if (ack == AckResult::Retry) {
            Journal a;
            a.kind = "ack";
            a.steam_id = sid;
            a.claim_id = claim_id;
            a.created_at = NowUnix();
            a.path = JournalDir() + "/ack_" + sid + "_" + std::to_string(claim_id) + ".json";
            if (!SaveJournal(a))
                Log::GetLog()->error(
                    "ShopVitrine: ack delivered nao gravado claim={} steam={} (risco de reembolso indevido)",
                    claim_id, sid);
        } else if (ack == AckResult::Final) {
            Log::GetLog()->error(
                "ShopVitrine: delivered rejeitado claim={} steam={} — conferir suporte", claim_id, sid);
        }
        ++delivered_total;
        SendMsg(player, "Recebido: " + FormatQty(quantity) + " " + name + ".");
    }

    if (delivered_total > 0)
        SendMsg(player, std::to_string(delivered_total) + " resgate(s) de recurso entregue(s).");
    return true;
}

// ── Registro ─────────────────────────────────────────────────────

void RegisterCommands() {
    ArkApi::GetCommands().AddChatCommand("/vitrine", &CmdVitrine);
    Log::GetLog()->info(
        "ShopVitrine: /vitrine registado (enabled={}, ttl={}s, journal={})",
        ShopConfig::Get().VitrineCommandEnabled() ? "yes" : "no",
        ShopConfig::Get().VitrinePreviewTtlSeconds(), JournalDir());
}

void UnregisterCommands() {
    ArkApi::GetCommands().RemoveChatCommand("/vitrine");
}

} // namespace Vitrine
} // namespace CustomShop
