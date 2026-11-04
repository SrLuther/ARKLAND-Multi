#include "FarmCommands.h"
#include "FarmConfig.h"
#include "FarmState.h"
#include "FarmPerms.h"
#include "FarmSync.h"
#include "plugin_version.h"

namespace {
struct FarmPreviewEntry {
    std::string item_id;
    std::string class_name;
    std::string species_blueprint;
    std::string display_name;
    std::string resource_id;
    int item_quantity = 1;
    bool is_soul = false;
    std::string resource_name;
};
struct FarmPreview {
    int64_t expires_utc = 0;
    std::vector<FarmPreviewEntry> items;
};
std::mutex g_preview_mutex;
std::mutex g_redemption_mutex;
std::unordered_map<std::string, FarmPreview> g_previews;

std::string Lower(std::string value) {
    std::transform(value.begin(), value.end(), value.begin(),
        [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });
    return value;
}
bool IsSoulCandidate(const std::string& class_name, const std::string& display_name,
                     const std::string& custom_name, const std::string& description) {
    (void)display_name; (void)custom_name; (void)description;
    const std::string lower = Lower(class_name);
    return lower.find("/game/mods/arkomega/items/souls/godsouls/primalitem_speciessoul.") != std::string::npos &&
           lower.ends_with("primalitem_speciessoul_c");
}
bool MatchesConfiguredClass(const std::string& actual, const std::string& configured) {
    if (actual.empty() || configured.empty()) return false;
    return Lower(actual).find(Lower(configured)) != std::string::npos;
}
bool GiveFarmStack(AShooterPlayerController* controller, const std::string& configured_class,
                   int quantity, std::string& failure_reason) {
    if (!controller || configured_class.empty() || quantity < 1) {
        failure_reason = "invalid arguments";
        return false;
    }
    std::string blueprint = configured_class;
    const auto game_path = blueprint.find("/Game/");
    if (game_path != std::string::npos) blueprint = blueprint.substr(game_path);
    if (blueprint.rfind("Blueprint'", 0) == 0 && blueprint.size() > 11 && blueprint.back() == '\'')
        blueprint = blueprint.substr(10, blueprint.size() - 11);
    FString fblueprint(blueprint.c_str());
    UClass* item_class = UVictoryCore::BPLoadClass(&fblueprint);
    auto* inventory = controller->GetPlayerInventoryComponent();
    if (!item_class) {
        failure_reason = "Blueprint class could not be loaded";
        return false;
    }
    if (!inventory) {
        failure_reason = "player inventory is unavailable";
        return false;
    }
    auto* cdo = static_cast<UPrimalItem*>(item_class->GetDefaultObject(true));
    int max_stack = quantity;
    if (cdo) {
        const int game_max = cdo->GetMaxItemQuantity(ArkApi::GetApiUtils().GetWorld());
        if (game_max > 0) max_stack = game_max;
    }
    // Redemption quantity can exceed an item's real ARK stack limit even when
    // the farm's configured stock stack is larger. Deliver legal inventory stacks.
    int remaining = quantity;
    while (remaining > 0) {
        const int chunk = std::min(max_stack, remaining);
        UPrimalItem* created = UPrimalItem::AddNewItem(
            TSubclassOf<UPrimalItem>(item_class), inventory,
            false, false, 0.0f, true, chunk, false, 0.0f, false,
            TSubclassOf<UPrimalItem>(), 0.0f, false, false);
        if (!created) {
            failure_reason = "AddNewItem returned null (qty=" + std::to_string(chunk) +
                ", max_stack=" + std::to_string(max_stack) + ")";
            return false;
        }
        remaining -= chunk;
    }
    return true;
}
std::string ItemIdText(const FItemNetID& id) {
    return std::to_string(id.ItemID1) + ":" + std::to_string(id.ItemID2);
}
UPrimalGameData* GetPrimalGameData() {
    UEngine* engine = Globals::GEngine().Get();
    if (!engine) return nullptr;
    auto* globals = static_cast<UPrimalGlobals*>(engine->GameSingletonField());
    if (!globals) return nullptr;
    return globals->PrimalGameDataOverrideField()
        ? globals->PrimalGameDataOverrideField() : globals->PrimalGameDataField();
}
FAssetRegistry* GetLoadedAssetRegistry() {
    auto* manager = FModuleManager::Get();
    if (!manager) return nullptr;
    const FName module_name("AssetRegistry", EFindName::FNAME_Find);
    if (!manager->IsModuleLoaded(module_name)) return nullptr;
    TSharedPtr<IModuleInterface> module;
    manager->GetModule(&module, module_name);
    auto* asset_registry_module = static_cast<FAssetRegistryModule*>(module.Get());
    return asset_registry_module ? asset_registry_module->Get() : nullptr;
}
std::wstring Wide(const std::string& s) {
    if (s.empty()) return {};
    int n = MultiByteToWideChar(CP_UTF8, 0, s.c_str(), -1, nullptr, 0);
    if (n <= 1) return std::wstring(s.begin(), s.end());
    std::wstring out(static_cast<size_t>(n), L'\0');
    if (!MultiByteToWideChar(CP_UTF8, 0, s.c_str(), -1, out.data(), n)) return {};
    out.resize(static_cast<size_t>(n - 1));
    return out;
}
void Say(AShooterPlayerController* c, const std::string& message, FLinearColor color = FColorList::White) {
    if (!c || message.empty()) return;
    FString text(Wide(message));
    c->ClientServerChatDirectMessage(&text, color, false);
}
std::string Steam(AShooterPlayerController* c) {
    if (!c) return {};
    const uint64_t id = ArkApi::GetApiUtils().GetSteamIdFromController(c);
    return id ? std::to_string(id) : std::string{};
}
bool HasLicense(AShooterPlayerController* c) {
    const auto id = ArkApi::GetApiUtils().GetSteamIdFromController(c);
    return id && FazendaRecursos::Perms::IsInGroup(id, FazendaRecursos::FarmConfig::Get().LicenseGroup());
}
bool IsAdmin(AShooterPlayerController* c) {
    if (!c) return false;
    if (c->bIsAdmin()()) return true;
    const auto id = ArkApi::GetApiUtils().GetSteamIdFromController(c);
    for (const auto& group : FazendaRecursos::FarmConfig::Get().AdminGroups())
        if (FazendaRecursos::Perms::IsInGroup(id, group)) return true;
    return false;
}
bool Ready() { return ArkApi::GetApiUtils().GetStatus() == ArkApi::ServerStatus::Ready; }

bool GetSpeciesBlueprint(UPrimalItem* item, std::string& species) {
    if (!item) return false;
    const auto& all = item->CustomItemDatasField();
    for (int data_index = 0; data_index < all.Num(); ++data_index) {
        const auto& data = all[data_index];
        if (Lower(data.CustomDataName.ToString().ToString()) != "speciessoul") continue;
        if (data.CustomDataStrings.Num() != 1) return false;
        species = data.CustomDataStrings[0].ToString();
        const auto lower = Lower(species);
        return lower.starts_with("/game/mods/arkomega/classes/") && lower.find("_character_bp") != std::string::npos;
    }
    return false;
}

std::string SafeFilename(std::string value) {
    for (auto& ch : value) if (!std::isalnum(static_cast<unsigned char>(ch)) && ch != '-' && ch != '_') ch = '_';
    return value;
}

UPrimalItem* FindInventoryItem(UPrimalInventoryComponent* inv, const std::string& net_id) {
    if (!inv) return nullptr;
    for (UPrimalItem* item : inv->InventoryItemsField())
        if (item && ItemIdText(item->ItemIDField()) == net_id) return item;
    return nullptr;
}

bool WriteSoulBlob(const std::string& path, const TArray<unsigned char>& bytes) {
    if (bytes.Num() <= 0) return false;
    std::error_code ec;
    std::filesystem::create_directories(std::filesystem::path(path).parent_path(), ec);
    if (ec) return false;
    const std::wstring temp = std::filesystem::path(path).wstring() + L".tmp";
    {
        std::ofstream out(temp, std::ios::binary | std::ios::trunc);
        if (!out) return false;
        out.write(reinterpret_cast<const char*>(bytes.GetData()), bytes.Num());
        out.flush();
        if (!out) { std::filesystem::remove(temp, ec); return false; }
    }
    if (!MoveFileExW(temp.c_str(), std::filesystem::path(path).wstring().c_str(),
                     MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        std::filesystem::remove(temp, ec);
        return false;
    }
    return true;
}

void CmdFarm(APlayerController* pc, FString*, bool) {
    auto* c = static_cast<AShooterPlayerController*>(pc);
    auto& cfg = FazendaRecursos::FarmConfig::Get();
    if (!cfg.Enabled()) { Say(c, cfg.Message("Disabled", "Fazenda desativada.")); return; }
    if (!Ready()) { Say(c, cfg.Message("NotReady", "Servidor não está pronto.")); return; }
    if (!HasLicense(c)) { Say(c, cfg.Message("NoLicense", "Licença keyfarm inativa."), FColorList::Red); return; }
    auto* character = c ? c->GetPlayerCharacter() : nullptr;
    auto* inv = character ? character->MyInventoryComponentField() : nullptr;
    if (!inv) { Say(c, "Não consegui ler seu inventário agora.", FColorList::Red); return; }
    const std::string steam = Steam(c);
    std::vector<FarmPreviewEntry> found;
    std::set<std::string> previewed_species;
    std::set<std::string> previewed_resources;
    const auto definitions = cfg.ResourcesSnapshot();
    const auto state = FazendaRecursos::FarmState::Get().GetPlayer(steam);
    for (UPrimalItem* item : inv->InventoryItemsField()) {
        if (!item) continue;
        FString class_name, item_name;
        if (auto* cls = item->ClassField()) cls->GetFullName(&class_name, nullptr);
        item->GetItemName(&item_name, false, true, nullptr);
        const std::string class_text = class_name.ToString();
        const int quantity = std::max(1, item->GetItemQuantity());
        if (IsSoulCandidate(class_text, {}, {}, {})) {
            if (quantity != 1) continue;
            std::string species;
            if (!GetSpeciesBlueprint(item, species)) continue;
            const bool already_owned = std::any_of(state.souls.begin(), state.souls.end(), [&](const auto& row) {
                return row.second.species_blueprint == species && row.second.status != "rolled_back";
            });
            if (already_owned || !previewed_species.insert(species).second) continue;
            found.push_back({ItemIdText(item->ItemIDField()), class_text, species,
                item_name.ToString(), {}, quantity, true});
            continue;
        }
        for (const auto& def : definitions) {
            if (!def.enabled || !MatchesConfiguredClass(class_text, def.input_class)) continue;
            if (quantity != 1 || def.input_quantity != 1 || state.resources.count(def.id) && state.resources.at(def.id).active ||
                !previewed_resources.insert(def.id).second) break;
            found.push_back({ItemIdText(item->ItemIDField()), class_text, {},
                item_name.ToString(), def.id, quantity, false});
            found.back().resource_name = def.name;
            break;
        }
    }
    if (found.empty()) {
        Say(c, "Não encontrei recursos elegíveis para envio. O item precisa estar configurado e habilitado na Fazenda; Paragon Souls também precisam estar sem empilhar e cada espécie só pode ser enviada uma vez.", FColorList::Yellow);
        return;
    }
    const int64_t now = static_cast<int64_t>(std::chrono::duration_cast<std::chrono::seconds>(
        std::chrono::system_clock::now().time_since_epoch()).count());
    {
        std::lock_guard<std::mutex> lock(g_preview_mutex);
        g_previews[steam] = {now + cfg.PreviewLifetimeSeconds(), found};
    }
    std::string text = "Prévia de envio: " + std::to_string(found.size()) + " item(ns). O envio consome os itens listados e ativa a produção dos recursos:";
    const size_t shown = std::min<size_t>(found.size(), 8);
    for (size_t i = 0; i < shown; ++i) text += "\n- " + found[i].display_name;
    if (found.size() > shown) text += "\n- e mais " + std::to_string(found.size() - shown);
    text += "\nDigite /fazconfirmar em até " + std::to_string(cfg.PreviewLifetimeSeconds()) + " segundos para enviar todas.";
    Say(c, text, FColorList::Yellow);
}
void CmdConfirm(APlayerController* pc, FString*, bool) {
    auto* c = static_cast<AShooterPlayerController*>(pc);
    auto& cfg = FazendaRecursos::FarmConfig::Get();
    if (!cfg.Enabled() || !Ready()) { Say(c, "A Fazenda não está disponível neste momento.", FColorList::Red); return; }
    if (!HasLicense(c)) { Say(c, cfg.Message("NoLicense", "Licença keyfarm inativa."), FColorList::Red); return; }
    const std::string steam = Steam(c);
    FarmPreview preview;
    {
        std::lock_guard<std::mutex> lock(g_preview_mutex);
        auto it = g_previews.find(steam);
        if (it == g_previews.end()) { Say(c, "Não há prévia pendente. Use /fazenda para listar os itens elegíveis.", FColorList::Yellow); return; }
        preview = std::move(it->second);
        g_previews.erase(it);
    }
    const int64_t now = static_cast<int64_t>(std::chrono::duration_cast<std::chrono::seconds>(
        std::chrono::system_clock::now().time_since_epoch()).count());
    if (now > preview.expires_utc) { Say(c, "A prévia expirou. Use /fazenda novamente.", FColorList::Yellow); return; }
    auto* character = c ? c->GetPlayerCharacter() : nullptr;
    auto* inv = character ? character->MyInventoryComponentField() : nullptr;
    if (!inv) { Say(c, "Não consegui ler seu inventário agora.", FColorList::Red); return; }
    int uploaded = 0, skipped = 0, failed = 0;
    auto& farm = FazendaRecursos::FarmState::Get();
    for (const auto& entry : preview.items) {
        UPrimalItem* item = FindInventoryItem(inv, entry.item_id);
        std::string species;
        if (!item || item->GetItemQuantity() != 1 || entry.item_quantity != 1) { ++skipped; continue; }
        if (entry.is_soul && (!GetSpeciesBlueprint(item, species) || species != entry.species_blueprint ||
            farm.HasSoul(steam, species))) { ++skipped; continue; }
        if (!entry.is_soul && farm.HasActiveResource(steam, entry.resource_id)) { ++skipped; continue; }
        TArray<unsigned char> bytes;
        item->GetItemBytes(&bytes);
        if (bytes.Num() <= 0) { ++failed; continue; }
        const int64_t uploaded_at = static_cast<int64_t>(std::chrono::duration_cast<std::chrono::seconds>(
            std::chrono::system_clock::now().time_since_epoch()).count());
        const std::string id = std::to_string(uploaded_at) + "-" + SafeFilename(entry.item_id);
        const std::string filename = (entry.is_soul ? "soul-" : "resource-") + id + ".bin";
        const std::string blob_directory = entry.is_soul ? farm.SoulDirectory(steam) : farm.ResourceDirectory(steam);
        const std::string full_path = blob_directory + "/" + filename;
        if (!WriteSoulBlob(full_path, bytes)) { ++failed; continue; }
        if (!entry.is_soul) {
            FazendaRecursos::PlayerFarm::UploadedResource record;
            record.id = id; record.resource_id = entry.resource_id;
            record.resource_name = entry.resource_name;
            record.item_class = entry.class_name; record.display_name = entry.display_name;
            record.blob_file = filename; record.uploaded_utc = uploaded_at;
            record.blob_size = static_cast<uint64_t>(bytes.Num()); record.item_quantity = entry.item_quantity;
            if (!farm.AddPendingResource(steam, record)) {
                std::error_code ec; std::filesystem::remove(full_path, ec); ++skipped; continue;
            }
            FItemNetID item_id = item->ItemIDField();
            if (!inv->RemoveItem(&item_id, false, false, true, true)) {
                farm.RemoveResource(steam, id);
                std::error_code ec; std::filesystem::remove(full_path, ec); ++failed; continue;
            }
            const int64_t started_at = static_cast<int64_t>(std::chrono::duration_cast<std::chrono::seconds>(
                std::chrono::system_clock::now().time_since_epoch()).count());
            if (!farm.CommitResource(steam, entry.resource_id, id, started_at)) {
                ++failed;
                Log::GetLog()->error("FazendaRecursos: recurso consumido mas commit pendente; steam={} recurso={} upload={}",
                    steam, entry.resource_id, id);
                continue;
            }
            if (!FazendaRecursos::FarmSync::SyncUploadedResourceNow(steam, id)) {
                UPrimalItem* restored = UPrimalItem::CreateFromBytes(&bytes);
                if (restored && inv->AddItemObject(restored)) {
                    if (farm.RollbackResourceUpload(steam, id))
                        FazendaRecursos::FarmSync::SyncUploadedResourceNow(steam, id);
                    else
                        Log::GetLog()->error("FazendaRecursos: item devolvido mas estado não foi revertido; steam={} upload={}", steam, id);
                } else {
                    Log::GetLog()->error("FazendaRecursos: MySQL indisponível e item não pôde ser devolvido; conferir inventário e farms.json; steam={} upload={}", steam, id);
                }
                ++failed;
                FazendaRecursos::FarmSync::QueuePlayer(steam);
                continue;
            }
            ++uploaded;
            continue;
        }
        FazendaRecursos::PlayerFarm::UploadedSoul record;
        record.id = id; record.item_class = entry.class_name;
        record.species_blueprint = species; record.display_name = entry.display_name;
        record.blob_file = filename; record.status = "pending_consumption";
        record.uploaded_utc = uploaded_at; record.blob_size = static_cast<uint64_t>(bytes.Num());
        if (!farm.AddPendingSoul(steam, record)) {
            std::error_code ec; std::filesystem::remove(full_path, ec); ++failed; continue;
        }
        FItemNetID item_id = item->ItemIDField();
        if (!inv->RemoveItem(&item_id, false, false, true, true)) {
            farm.RemoveSoul(steam, id);
            std::error_code ec; std::filesystem::remove(full_path, ec); ++failed; continue;
        }
        if (!farm.CommitSoul(steam, id)) {
            ++failed;
            Log::GetLog()->error("FazendaRecursos: Soul consumida mas commit pendente; steam={} record={}", steam, id);
            continue;
        }
        ++uploaded;
    }
    Say(c, "Envio concluído: " + std::to_string(uploaded) + " item(ns) armazenado(s); " +
        std::to_string(skipped) + " ignorado(s); " + std::to_string(failed) + " falha(s). Recursos configurados iniciam producao passiva; agende a retirada na Minha Area e use /fazresgatar no jogo.",
        failed ? FColorList::Yellow : FColorList::Green);
    if (uploaded > 0) FazendaRecursos::FarmSync::QueuePlayer(steam);
}
void CmdStatus(APlayerController* pc, FString*, bool) {
    auto* c = static_cast<AShooterPlayerController*>(pc);
    auto& cfg = FazendaRecursos::FarmConfig::Get();
    if (!cfg.Enabled()) { Say(c, cfg.Message("Disabled", "Fazenda desativada.")); return; }
    if (!HasLicense(c)) { Say(c, cfg.Message("NoLicense", "Licença keyfarm inativa."), FColorList::Red); return; }
    const auto resource_defs = cfg.ResourcesSnapshot();
    const size_t defs = static_cast<size_t>(std::count_if(resource_defs.begin(), resource_defs.end(), [](const auto& r){ return r.enabled;}));
    const auto state = FazendaRecursos::FarmState::Get().GetPlayer(Steam(c));
    const size_t producing = static_cast<size_t>(std::count_if(state.resources.begin(), state.resources.end(), [](const auto& row){ return row.second.active; }));
    const size_t souls = static_cast<size_t>(std::count_if(state.souls.begin(), state.souls.end(), [](const auto& row){ return row.second.status == "active"; }));
    const size_t pending = static_cast<size_t>(std::count_if(state.souls.begin(), state.souls.end(), [](const auto& row){ return row.second.status == "pending_consumption"; }));
    FazendaRecursos::FarmSync::QueuePlayer(Steam(c));
    std::string text = "Sua fazenda: " + std::to_string(souls) + " Paragon Soul(s) enviada(s), " +
        std::to_string(producing) + " produção(ões) ativa(s), " + std::to_string(state.resources.size()) +
        " recurso(s) no estoque. Recursos configurados: " + std::to_string(defs) + ".";
    if (pending) text += " Registro(s) pendente(s) para revisão administrativa: " + std::to_string(pending) + ".";
    Say(c, text);
}
void CmdRedeem(APlayerController* pc, FString*, bool) {
    auto* c = static_cast<AShooterPlayerController*>(pc);
    if (!c || !Ready()) { Say(c, "A Fazenda não está disponível neste momento.", FColorList::Yellow); return; }
    auto* character = c->GetPlayerCharacter();
    auto* inv = character ? character->MyInventoryComponentField() : nullptr;
    const std::string steam = Steam(c);
    if (!inv || steam.empty()) { Say(c, "Não consegui acessar seu inventário.", FColorList::Red); return; }
    std::unique_lock<std::mutex> operation(g_redemption_mutex, std::try_to_lock);
    if (!operation.owns_lock()) { Say(c, "Um resgate da Fazenda já está sendo processado. Tente novamente em instantes.", FColorList::Yellow); return; }

    std::vector<FazendaRecursos::FarmSync::RedemptionStack> stacks;
    if (!FazendaRecursos::FarmSync::ClaimRedemptionStacks(steam,
            FazendaRecursos::FarmConfig::Get().ServerId(), stacks)) {
        Say(c, "Não consegui consultar os pedidos da Fazenda no MySQL. Nenhum item foi entregue.", FColorList::Red);
        return;
    }
    if (stacks.empty()) { Say(c, "Você não tem stacks pendentes para resgatar.", FColorList::Yellow); return; }

    const auto definitions = FazendaRecursos::FarmConfig::Get().ResourcesSnapshot();
    int delivered_stacks = 0, delivered_items = 0;
    bool failed = false;
    for (const auto& stack : stacks) {
        const auto definition = std::find_if(definitions.begin(), definitions.end(), [&](const auto& row) {
            return row.id == stack.resource_id;
        });
        if (definition == definitions.end() || stack.quantity < 1 ||
            stack.quantity > definition->stack_size || !definition->enabled) {
            Log::GetLog()->error("Farm: delivery stack invalid; steam={} order={} resource={} qty={}",
                steam, stack.redemption_id, stack.resource_id, stack.quantity);
            FazendaRecursos::FarmSync::CompleteRedemptionStack(stack, steam,
                FazendaRecursos::FarmConfig::Get().ServerId(), false);
            failed = true;
            break;
        }
        std::string delivery_failure;
        if (!GiveFarmStack(c, definition->item_class, stack.quantity, delivery_failure)) {
            Log::GetLog()->warn("Farm: Blueprint delivery failed; steam={} order={} stack={} qty={} class={} reason={}",
                steam, stack.redemption_id, stack.stack_index, stack.quantity, definition->item_class,
                delivery_failure);
            FazendaRecursos::FarmSync::CompleteRedemptionStack(stack, steam,
                FazendaRecursos::FarmConfig::Get().ServerId(), false);
            failed = true;
            break;
        }
        if (!FazendaRecursos::FarmSync::CompleteRedemptionStack(stack, steam,
                FazendaRecursos::FarmConfig::Get().ServerId(), true)) {
            Log::GetLog()->error("Farm: item entregue mas MySQL nao confirmou; verifique o inventario antes de repetir; steam={} order={} stack={}",
                steam, stack.redemption_id, stack.stack_index);
            failed = true;
            break;
        }
        ++delivered_stacks;
        delivered_items += stack.quantity;
    }
    const std::string result = "Resgate da Fazenda: " + std::to_string(delivered_items) +
        " unidade(s) em " + std::to_string(delivered_stacks) + " stack(s) entregue(s).";
    Say(c, failed ? result + " Há itens pendentes; confira o histórico na Minha Área antes de repetir." : result,
        failed ? FColorList::Yellow : FColorList::Yellow);
}
void CmdRecover(APlayerController* pc, FString*, bool) {
    auto* c = static_cast<AShooterPlayerController*>(pc);
    auto* character = c ? c->GetPlayerCharacter() : nullptr;
    auto* inv = character ? character->MyInventoryComponentField() : nullptr;
    const std::string steam = Steam(c);
    if (!inv || steam.empty()) { Say(c, "Não consegui acessar seu inventário.", FColorList::Red); return; }

    auto& farm = FazendaRecursos::FarmState::Get();
    const auto player = farm.GetPlayer(steam);
    int restored = 0, failed = 0, needs_review = 0;
    for (const auto& [id, record] : player.uploaded_resources) {
        if (record.status == "recovered" || record.status == "rolled_back") continue;
        if (record.status != "active") { ++needs_review; continue; }
        if (!farm.BeginResourceRestore(steam, id)) { ++needs_review; continue; }

        const auto safe_name = std::filesystem::path(record.blob_file).filename().string();
        if (safe_name.empty() || safe_name != record.blob_file) {
            farm.FinishResourceRestore(steam, id, false); ++failed; continue;
        }
        const auto path = std::filesystem::path(farm.ResourceDirectory(steam)) / safe_name;
        std::ifstream in(path, std::ios::binary);
        std::vector<unsigned char> raw((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
        if (raw.empty() || in.bad()) {
            farm.FinishResourceRestore(steam, id, false); ++failed; continue;
        }
        TArray<unsigned char> bytes;
        bytes.Reserve(static_cast<int>(raw.size()));
        for (const auto byte : raw) bytes.Add(byte);
        UPrimalItem* item = UPrimalItem::CreateFromBytes(&bytes);
        if (!item || !inv->AddItemObject(item)) {
            farm.FinishResourceRestore(steam, id, false); ++failed; continue;
        }
        if (!farm.FinishResourceRestore(steam, id, true)) {
            ++needs_review;
            Log::GetLog()->error("FazendaRecursos: item restaurado mas estado não salvo; conferir inventário antes de repetir /fazrecuperar; steam={} upload={}", steam, id);
            continue;
        }
        ++restored;
    }
    for (const auto& [id, record] : player.souls) {
        if (record.status == "recovered" || record.status == "rolled_back") continue;
        if (record.status != "active") { ++needs_review; continue; }
        if (!farm.BeginSoulRestore(steam, id)) { ++needs_review; continue; }

        const auto safe_name = std::filesystem::path(record.blob_file).filename().string();
        if (safe_name.empty() || safe_name != record.blob_file) {
            farm.FinishSoulRestore(steam, id, false); ++failed; continue;
        }
        const auto path = std::filesystem::path(farm.SoulDirectory(steam)) / safe_name;
        std::ifstream in(path, std::ios::binary);
        std::vector<unsigned char> raw((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
        if (raw.empty() || in.bad()) {
            farm.FinishSoulRestore(steam, id, false); ++failed; continue;
        }
        TArray<unsigned char> bytes;
        bytes.Reserve(static_cast<int>(raw.size()));
        for (const auto byte : raw) bytes.Add(byte);
        UPrimalItem* item = UPrimalItem::CreateFromBytes(&bytes);
        if (!item || !inv->AddItemObject(item)) {
            farm.FinishSoulRestore(steam, id, false); ++failed; continue;
        }
        if (!farm.FinishSoulRestore(steam, id, true)) {
            ++needs_review;
            Log::GetLog()->error("FazendaRecursos: Paragon Soul restaurada mas estado não salvo; conferir inventário antes de repetir /fazrecuperar; steam={} soul={}", steam, id);
            continue;
        }
        ++restored;
    }
    if (restored > 0) FazendaRecursos::FarmSync::QueuePlayer(steam);
    std::string message = "Recuperação: " + std::to_string(restored) + " item(ns) restaurado(s); " +
        std::to_string(failed) + " falha(s). Os arquivos-fonte foram mantidos.";
    if (needs_review) message += " " + std::to_string(needs_review) + " registro(s) exigem conferência; não repita sem verificar o inventário.";
    Say(c, message, failed || needs_review ? FColorList::Yellow : FColorList::Green);
}
void CmdCollect(APlayerController* pc, FString*, bool) {
    auto* c = static_cast<AShooterPlayerController*>(pc);
    if (!IsAdmin(c)) { Say(c, FazendaRecursos::FarmConfig::Get().Message("NoPermission", "Comando restrito a administradores."), FColorList::Red); return; }
    if (!Ready() || !c->GetPlayerCharacter() || !c->GetPlayerCharacter()->MyInventoryComponentField()) {
        Say(c, FazendaRecursos::FarmConfig::Get().Message("NotReady", "Inventário indisponível."), FColorList::Red); return;
    }
    const std::string base = ArkApi::Tools::GetCurrentDir() + "/ArkApi/Plugins/FazendaRecursos/diagnostics";
    std::error_code ec; std::filesystem::create_directories(base, ec);
    if (ec) { Say(c, FazendaRecursos::FarmConfig::Get().Message("DiagnosticFailed", "Falha ao criar diretório."), FColorList::Red); return; }
    const auto stamp = std::chrono::duration_cast<std::chrono::seconds>(std::chrono::system_clock::now().time_since_epoch()).count();
    const std::string export_dir = base + "/items-" + std::to_string(stamp);
    std::filesystem::create_directories(export_dir, ec);
    if (ec) { Say(c, FazendaRecursos::FarmConfig::Get().Message("DiagnosticFailed", "Falha ao criar diretório."), FColorList::Red); return; }
    const std::string path = export_dir + "/report.json";
    nlohmann::json report = nlohmann::json::object();
    report["generated_utc_epoch"] = stamp;
    report["plugin_version"] = std::string(ARKLAND_PLUGIN_VERSION) + "-test";
    report["serialization_note"] = "Blobs are opaque UPrimalItem::GetItemBytes output; metadata is read from live ArkServerAPI objects. No byte offsets are inferred.";
    report["map"] = "";
    if (auto* gm = ArkApi::GetApiUtils().GetShooterGameMode()) { FString map; gm->GetMapName(&map); report["map"] = map.ToString(); }
    report["items"] = nlohmann::json::array();
    report["engram_catalog"] = nlohmann::json::array();
    report["asset_registry"] = {
        {"status", "not_attempted"},
        {"source", "FAssetRegistry::GetAllAssets from the already-loaded index; no forced synchronous scan"}
    };
    const std::string asset_path = export_dir + "/assets.json";
    if (auto* registry = GetLoadedAssetRegistry()) {
        if (registry->IsLoadingAssets()) {
            report["asset_registry"]["status"] = "index_loading";
        } else {
            TArray<FAssetData> assets;
            if (registry->GetAllAssets(&assets)) {
                nlohmann::json asset_rows = nlohmann::json::array();
                std::ostringstream asset_text;
                asset_text << "AssetName\tAssetClass\tObjectPath\n";
                for (const FAssetData& asset : assets) {
                    const std::string object_path = asset.ObjectPath.ToString().ToString();
                    const std::string asset_name = asset.AssetName.ToString().ToString();
                    const std::string asset_class = asset.AssetClass.ToString().ToString();
                    asset_rows.push_back({
                        {"object_path", object_path},
                        {"package_name", asset.PackageName.ToString().ToString()},
                        {"package_path", asset.PackagePath.ToString().ToString()},
                        {"asset_name", asset_name},
                        {"asset_class", asset_class}
                    });
                    asset_text << asset_name << '\t' << asset_class << '\t' << object_path << '\n';
                }
                std::ofstream asset_file(asset_path, std::ios::binary | std::ios::trunc);
                if (asset_file) {
                    asset_file << asset_rows.dump(2);
                    asset_file.flush();
                    if (asset_file) {
                        report["asset_registry"]["status"] = "exported";
                        report["asset_registry"]["count"] = assets.Num();
                        report["asset_registry"]["file"] = "assets.json";
                        std::ofstream readable_assets(export_dir + "/assets.txt", std::ios::binary | std::ios::trunc);
                        if (readable_assets) {
                            readable_assets << asset_text.str();
                            readable_assets.flush();
                            if (readable_assets) report["asset_registry"]["readable_file"] = "assets.txt";
                        }
                    } else {
                        report["asset_registry"]["status"] = "write_failed";
                    }
                } else {
                    report["asset_registry"]["status"] = "write_failed";
                }
            } else {
                report["asset_registry"]["status"] = "query_failed";
            }
        }
    } else {
        report["asset_registry"]["status"] = "module_unavailable";
    }
    auto* player_state = c->GetShooterPlayerState();
    auto* game_data = GetPrimalGameData();
    if (player_state && game_data) {
        const TArray<UPrimalEngramEntry*>& entries = game_data->EngramBlueprintEntriesField();
        report["engram_catalog_count"] = entries.Num();
        int available_count = 0;
        int unlocked_count = 0;
        for (UPrimalEngramEntry* entry : entries) {
            if (!entry) continue;
            const auto item_class = entry->BluePrintEntryField();
            if (!item_class.uClass) continue;
            FString class_name, entry_name, display_name;
            item_class.uClass->GetFullName(&class_name, nullptr);
            entry->NameField().ToString(&entry_name);
            entry->GetEngramName(&display_name);
            const bool hidden = entry->IsEngramClassHidden(item_class);
            const bool requirements_met = entry->MeetsEngramRequirements(player_state, false, false);
            const bool unlocked = player_state->HasEngram(item_class);
            const bool available = !hidden && requirements_met;
            if (available) ++available_count;
            if (unlocked) ++unlocked_count;
            report["engram_catalog"].push_back({
                {"entry_name", entry_name.ToString()},
                {"display_name", display_name.ToString()},
                {"item_class_full_name", class_name.ToString()},
                {"required_character_level", entry->RequiredCharacterLevelField()},
                {"required_engram_points", entry->RequiredEngramPointsField()},
                {"hidden", hidden},
                {"requirements_met", requirements_met},
                {"unlocked", unlocked},
                {"available_to_player", available}
            });
        }
        report["engram_available_to_player_count"] = available_count;
        report["engram_unlocked_count"] = unlocked_count;
    } else {
        report["engram_catalog_error"] = !player_state ? "player_state_unavailable" : "primal_game_data_unavailable";
    }
    {
        std::ostringstream readable_catalog;
        readable_catalog << "DisplayName\tEntryName\tRequiredLevel\tRequiredEngramPoints\tHidden\tUnlocked\tRequirementsMet\tBlueprintClass\n";
        for (const auto& entry : report["engram_catalog"]) {
            readable_catalog << entry.value("display_name", std::string{}) << '\t'
                << entry.value("entry_name", std::string{}) << '\t'
                << entry.value("required_character_level", 0) << '\t'
                << entry.value("required_engram_points", 0) << '\t'
                << (entry.value("hidden", false) ? "yes" : "no") << '\t'
                << (entry.value("unlocked", false) ? "yes" : "no") << '\t'
                << (entry.value("requirements_met", false) ? "yes" : "no") << '\t'
                << entry.value("item_class_full_name", std::string{}) << '\n';
        }
        std::ofstream readable_catalog_file(export_dir + "/engram_catalog.txt", std::ios::binary | std::ios::trunc);
        if (readable_catalog_file) {
            readable_catalog_file << readable_catalog.str();
            readable_catalog_file.flush();
            report["engram_catalog_text"] = readable_catalog_file ? "engram_catalog.txt" : "write_failed";
        } else {
            report["engram_catalog_text"] = "write_failed";
        }
    }
    auto* inv = c->GetPlayerCharacter()->MyInventoryComponentField();
    int candidate_index = 0;
    for (UPrimalItem* item : inv->InventoryItemsField()) {
        if (!item) continue;
        UClass* cls = item->ClassField();
        FString class_name, item_name;
        if (cls) cls->GetFullName(&class_name, nullptr);
        item->GetItemName(&item_name, false, true, nullptr);
        const std::string class_text = class_name.ToString();
        const std::string display_text = item_name.ToString();
        const std::string custom_name = item->CustomItemNameField().ToString();
        const std::string description = item->ItemDescriptionField().ToString();
        const bool candidate = IsSoulCandidate(class_text, display_text, custom_name, description);
        nlohmann::json row = {
            {"class_full_name", class_text},
            {"display_name", display_text},
            {"custom_item_name", custom_name},
            {"custom_item_id", item->CustomItemIDField()},
            {"descriptive_name_base", item->DescriptiveNameBaseField().ToString()},
            {"description", description},
            {"quantity", item->GetItemQuantity()},
            {"item_net_id", ItemIdText(item->ItemIDField())},
            {"soul_candidate", candidate}
        };

        nlohmann::json custom_data = nlohmann::json::array();
        const TArray<FCustomItemData>& all_custom_data = item->CustomItemDatasField();
        for (int data_index = 0; data_index < all_custom_data.Num(); ++data_index) {
            const FCustomItemData& data = all_custom_data[data_index];
            nlohmann::json entry = nlohmann::json::object();
            entry["name"] = data.CustomDataName.ToString().ToString();
            entry["strings"] = nlohmann::json::array();
            for (int i = 0; i < data.CustomDataStrings.Num(); ++i)
                entry["strings"].push_back(data.CustomDataStrings[i].ToString());
            entry["floats"] = nlohmann::json::array();
            for (int i = 0; i < data.CustomDataFloats.Num(); ++i)
                entry["floats"].push_back(data.CustomDataFloats[i]);
            entry["doubles"] = nlohmann::json::array();
            for (int i = 0; i < data.CustomDataDoubles.Doubles.Num(); ++i)
                entry["doubles"].push_back(data.CustomDataDoubles.Doubles[i]);
            entry["names"] = nlohmann::json::array();
            for (int i = 0; i < data.CustomDataNames.Num(); ++i)
                entry["names"].push_back(data.CustomDataNames[i].ToString().ToString());
            entry["classes"] = nlohmann::json::array();
            for (int i = 0; i < data.CustomDataClasses.Num(); ++i) {
                FString full_name;
                if (data.CustomDataClasses[i]) data.CustomDataClasses[i]->GetFullName(&full_name, nullptr);
                entry["classes"].push_back(full_name.ToString());
            }
            entry["byte_array_sizes"] = nlohmann::json::array();
            for (int i = 0; i < data.CustomDataBytes.ByteArrays.Num(); ++i)
                entry["byte_array_sizes"].push_back(data.CustomDataBytes.ByteArrays[i].Bytes.Num());
            entry["object_count"] = data.CustomDataObjects.Num();
            custom_data.push_back(std::move(entry));
        }
        row["custom_item_data"] = std::move(custom_data);

        if (candidate) {
            TArray<unsigned char> serialized;
            item->GetItemBytes(&serialized);
            row["serialized_blob_size"] = serialized.Num();
            if (serialized.Num() > 0) {
                std::ostringstream filename;
                filename << "item-" << std::setw(3) << std::setfill('0') << candidate_index++ << ".bin";
                const std::string blob_path = export_dir + "/" + filename.str();
                std::ofstream blob(blob_path, std::ios::binary | std::ios::trunc);
                blob.write(reinterpret_cast<const char*>(serialized.GetData()), serialized.Num());
                blob.flush();
                if (blob) row["serialized_blob_file"] = filename.str();
                else row["serialized_blob_error"] = "write_failed";
            } else {
                row["serialized_blob_error"] = "empty_serialization";
            }
        }
        report["items"].push_back(std::move(row));
    }
    std::ofstream out(path, std::ios::binary | std::ios::trunc);
    if (!out) { Say(c, FazendaRecursos::FarmConfig::Get().Message("DiagnosticFailed", "Falha ao gravar diagnóstico."), FColorList::Red); return; }
    out << report.dump(2); out.flush();
    if (!out) { Say(c, FazendaRecursos::FarmConfig::Get().Message("DiagnosticFailed", "Falha ao gravar diagnóstico."), FColorList::Red); return; }
    Say(c, "Diagnóstico salvo em ArkApi/Plugins/FazendaRecursos/diagnostics/items-" + std::to_string(stamp) + " (inclui blobs opacos das Souls detectadas).");
    Log::GetLog()->info("FazendaRecursos: inventory diagnostic generated by steam={} file={}", Steam(c), path);
}

void CmdReload(APlayerController*, FString*, bool) {
    try {
        FazendaRecursos::FarmConfig::Get().Reload();
        FazendaRecursos::FarmSync::QueueCatalog();
        Log::GetLog()->info("FazendaRecursos: configuração recarregada pelo console");
    } catch (const std::exception& e) {
        Log::GetLog()->error("FazendaRecursos: recarga rejeitada; configuração anterior mantida: {}", e.what());
    }
}
}

namespace FazendaRecursos::Commands {
void Register() {
    ArkApi::GetCommands().AddConsoleCommand("Fazenda.Reload", &CmdReload);
    ArkApi::GetCommands().AddChatCommand("/fazenda", &CmdFarm);
    ArkApi::GetCommands().AddChatCommand("/fazconfirmar", &CmdConfirm);
    ArkApi::GetCommands().AddChatCommand("/fazstatus", &CmdStatus);
    ArkApi::GetCommands().AddChatCommand("/fazresgatar", &CmdRedeem);
    ArkApi::GetCommands().AddChatCommand("/fazrecuperar", &CmdRecover);
    ArkApi::GetCommands().AddChatCommand("/fazcoletar", &CmdCollect);
}
void Unregister() {
    ArkApi::GetCommands().RemoveConsoleCommand("Fazenda.Reload");
    ArkApi::GetCommands().RemoveChatCommand("/fazenda");
    ArkApi::GetCommands().RemoveChatCommand("/fazconfirmar");
    ArkApi::GetCommands().RemoveChatCommand("/fazstatus");
    ArkApi::GetCommands().RemoveChatCommand("/fazresgatar");
    ArkApi::GetCommands().RemoveChatCommand("/fazrecuperar");
    ArkApi::GetCommands().RemoveChatCommand("/fazcoletar");
}
}
