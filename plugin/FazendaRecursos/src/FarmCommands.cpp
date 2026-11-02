#include "FarmCommands.h"
#include "FarmConfig.h"
#include "FarmState.h"
#include "FarmPerms.h"
#include "FarmSync.h"

namespace {
struct SoulPreviewEntry {
    std::string item_id;
    std::string class_name;
    std::string species_blueprint;
    std::string display_name;
};
struct SoulPreview {
    int64_t expires_utc = 0;
    std::vector<SoulPreviewEntry> items;
};
std::mutex g_preview_mutex;
std::unordered_map<std::string, SoulPreview> g_previews;

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
    std::vector<SoulPreviewEntry> found;
    std::set<std::string> previewed_species;
    const auto state = FazendaRecursos::FarmState::Get().GetPlayer(steam);
    for (UPrimalItem* item : inv->InventoryItemsField()) {
        if (!item || item->GetItemQuantity() != 1) continue;
        FString class_name, item_name;
        if (auto* cls = item->ClassField()) cls->GetFullName(&class_name, nullptr);
        item->GetItemName(&item_name, false, true, nullptr);
        const std::string class_text = class_name.ToString();
        if (!IsSoulCandidate(class_text, {}, {}, {})) continue;
        std::string species;
        if (!GetSpeciesBlueprint(item, species)) continue;
        const bool already_owned = std::any_of(state.souls.begin(), state.souls.end(), [&](const auto& row) {
            return row.second.species_blueprint == species && row.second.status != "rolled_back";
        });
        if (already_owned || !previewed_species.insert(species).second) continue;
        found.push_back({ItemIdText(item->ItemIDField()), class_text, species, item_name.ToString()});
    }
    if (found.empty()) {
        Say(c, "Não encontrei Paragon Souls Omega elegíveis. Elas precisam estar no inventário, sem estar empilhadas, e cada espécie só pode ser enviada uma vez.", FColorList::Yellow);
        return;
    }
    const int64_t now = static_cast<int64_t>(std::chrono::duration_cast<std::chrono::seconds>(
        std::chrono::system_clock::now().time_since_epoch()).count());
    {
        std::lock_guard<std::mutex> lock(g_preview_mutex);
        g_previews[steam] = {now + cfg.PreviewLifetimeSeconds(), found};
    }
    std::string text = "Prévia de envio: " + std::to_string(found.size()) + " Paragon Soul(s). O envio consome uma unidade por espécie:";
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
    SoulPreview preview;
    {
        std::lock_guard<std::mutex> lock(g_preview_mutex);
        auto it = g_previews.find(steam);
        if (it == g_previews.end()) { Say(c, "Não há prévia pendente. Use /fazenda para listar suas Paragons.", FColorList::Yellow); return; }
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
        if (!item || item->GetItemQuantity() != 1 || !GetSpeciesBlueprint(item, species) ||
            species != entry.species_blueprint || farm.HasSoul(steam, species)) { ++skipped; continue; }
        TArray<unsigned char> bytes;
        item->GetItemBytes(&bytes);
        if (bytes.Num() <= 0) { ++failed; continue; }
        const int64_t uploaded_at = static_cast<int64_t>(std::chrono::duration_cast<std::chrono::seconds>(
            std::chrono::system_clock::now().time_since_epoch()).count());
        const std::string id = std::to_string(uploaded_at) + "-" + SafeFilename(entry.item_id);
        const std::string filename = "soul-" + id + ".bin";
        const std::string full_path = farm.SoulDirectory(steam) + "/" + filename;
        if (!WriteSoulBlob(full_path, bytes)) { ++failed; continue; }
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
    Say(c, "Envio concluído: " + std::to_string(uploaded) + " Paragon Soul(s) armazenada(s); " +
        std::to_string(skipped) + " ignorada(s); " + std::to_string(failed) + " falha(s). Os arquivos originais foram preservados como blobs; esta versão ainda não gera nem entrega cópias.",
        failed ? FColorList::Yellow : FColorList::Green);
    if (uploaded > 0) FazendaRecursos::FarmSync::QueuePlayer(steam);
}
void CmdStatus(APlayerController* pc, FString*, bool) {
    auto* c = static_cast<AShooterPlayerController*>(pc);
    auto& cfg = FazendaRecursos::FarmConfig::Get();
    if (!cfg.Enabled()) { Say(c, cfg.Message("Disabled", "Fazenda desativada.")); return; }
    if (!HasLicense(c)) { Say(c, cfg.Message("NoLicense", "Licença keyfarm inativa."), FColorList::Red); return; }
    const size_t defs = static_cast<size_t>(std::count_if(cfg.Resources().begin(), cfg.Resources().end(), [](const auto& r){ return r.enabled;}));
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
    if (!HasLicense(c)) { Say(c, FazendaRecursos::FarmConfig::Get().Message("NoLicense", "Licença keyfarm inativa."), FColorList::Red); return; }
    Say(c, "Não há pedidos de resgate sincronizados para este servidor ainda. Nenhum item foi entregue.", FColorList::Yellow);
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
    report["plugin_version"] = "0.1.5-test";
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
    ArkApi::GetCommands().AddChatCommand("/fazcoletar", &CmdCollect);
}
void Unregister() {
    ArkApi::GetCommands().RemoveConsoleCommand("Fazenda.Reload");
    ArkApi::GetCommands().RemoveChatCommand("/fazenda");
    ArkApi::GetCommands().RemoveChatCommand("/fazconfirmar");
    ArkApi::GetCommands().RemoveChatCommand("/fazstatus");
    ArkApi::GetCommands().RemoveChatCommand("/fazresgatar");
    ArkApi::GetCommands().RemoveChatCommand("/fazcoletar");
}
}
