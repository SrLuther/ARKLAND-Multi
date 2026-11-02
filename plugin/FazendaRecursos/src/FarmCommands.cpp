#include "FarmCommands.h"
#include "FarmConfig.h"
#include "FarmState.h"
#include "FarmPerms.h"

namespace {
std::string Lower(std::string value) {
    std::transform(value.begin(), value.end(), value.begin(),
        [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });
    return value;
}
bool IsSoulCandidate(const std::string& class_name, const std::string& display_name,
                     const std::string& custom_name, const std::string& description) {
    const std::string searchable = Lower(class_name + " " + display_name + " " + custom_name + " " + description);
    return searchable.find("soul") != std::string::npos ||
           searchable.find("paragon") != std::string::npos ||
           searchable.find("alma") != std::string::npos;
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
std::wstring Wide(const std::string& s) {
    if (s.empty()) return {};
    int n = MultiByteToWideChar(CP_UTF8, 0, s.c_str(), -1, nullptr, 0);
    if (n <= 1) return std::wstring(s.begin(), s.end());
    std::wstring out(static_cast<size_t>(n - 1), L'\0');
    MultiByteToWideChar(CP_UTF8, 0, s.c_str(), -1, out.data(), n);
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

void CmdFarm(APlayerController* pc, FString*, bool) {
    auto* c = static_cast<AShooterPlayerController*>(pc);
    auto& cfg = FazendaRecursos::FarmConfig::Get();
    if (!cfg.Enabled()) { Say(c, cfg.Message("Disabled", "Fazenda desativada.")); return; }
    if (!Ready()) { Say(c, cfg.Message("NotReady", "Servidor nÃ£o estÃ¡ pronto.")); return; }
    if (!HasLicense(c)) { Say(c, cfg.Message("NoLicense", "LicenÃ§a keyfarm inativa."), FColorList::Red); return; }
    const size_t active = static_cast<size_t>(std::count_if(cfg.Resources().begin(), cfg.Resources().end(), [](const auto& r){ return r.enabled;}));
    if (!active) { Say(c, cfg.Message("StatusEmpty", "Nenhum recurso estÃ¡ configurado para depÃ³sito ainda.")); return; }
    Say(c, "ConfiguraÃ§Ã£o carregada. Recursos habilitados: " + std::to_string(active) +
        ". O depÃ³sito e a confirmaÃ§Ã£o serÃ£o liberados quando os identificadores reais forem mapeados.", FColorList::Yellow);
}
void CmdConfirm(APlayerController* pc, FString*, bool) {
    Say(static_cast<AShooterPlayerController*>(pc), "NÃ£o hÃ¡ uma prÃ©via vÃ¡lida pendente. Execute /fazenda apÃ³s configurar os recursos.", FColorList::Yellow);
}
void CmdStatus(APlayerController* pc, FString*, bool) {
    auto* c = static_cast<AShooterPlayerController*>(pc);
    auto& cfg = FazendaRecursos::FarmConfig::Get();
    if (!cfg.Enabled()) { Say(c, cfg.Message("Disabled", "Fazenda desativada.")); return; }
    if (!HasLicense(c)) { Say(c, cfg.Message("NoLicense", "LicenÃ§a keyfarm inativa."), FColorList::Red); return; }
    const size_t defs = static_cast<size_t>(std::count_if(cfg.Resources().begin(), cfg.Resources().end(), [](const auto& r){ return r.enabled;}));
    const auto state = FazendaRecursos::FarmState::Get().GetPlayer(Steam(c));
    const size_t producing = static_cast<size_t>(std::count_if(state.resources.begin(), state.resources.end(), [](const auto& row){ return row.second.active; }));
    std::string text = "Sua fazenda: " + std::to_string(producing) + " produÃ§Ã£o(Ãµes) ativa(s), " +
        std::to_string(state.resources.size()) + " recurso(s) no estoque. Recursos configurados: " + std::to_string(defs) + ".";
    Say(c, text);
}
void CmdRedeem(APlayerController* pc, FString*, bool) {
    auto* c = static_cast<AShooterPlayerController*>(pc);
    if (!HasLicense(c)) { Say(c, FazendaRecursos::FarmConfig::Get().Message("NoLicense", "LicenÃ§a keyfarm inativa."), FColorList::Red); return; }
    Say(c, "NÃ£o hÃ¡ pedidos de resgate sincronizados para este servidor ainda. Nenhum item foi entregue.", FColorList::Yellow);
}
void CmdCollect(APlayerController* pc, FString*, bool) {
    auto* c = static_cast<AShooterPlayerController*>(pc);
    if (!IsAdmin(c)) { Say(c, FazendaRecursos::FarmConfig::Get().Message("NoPermission", "Comando restrito a administradores."), FColorList::Red); return; }
    if (!Ready() || !c->GetPlayerCharacter() || !c->GetPlayerCharacter()->MyInventoryComponentField()) {
        Say(c, FazendaRecursos::FarmConfig::Get().Message("NotReady", "InventÃ¡rio indisponÃ­vel."), FColorList::Red); return;
    }
    const std::string base = ArkApi::Tools::GetCurrentDir() + "/ArkApi/Plugins/FazendaRecursos/diagnostics";
    std::error_code ec; std::filesystem::create_directories(base, ec);
    if (ec) { Say(c, FazendaRecursos::FarmConfig::Get().Message("DiagnosticFailed", "Falha ao criar diretÃ³rio."), FColorList::Red); return; }
    const auto stamp = std::chrono::duration_cast<std::chrono::seconds>(std::chrono::system_clock::now().time_since_epoch()).count();
    const std::string export_dir = base + "/items-" + std::to_string(stamp);
    std::filesystem::create_directories(export_dir, ec);
    if (ec) { Say(c, FazendaRecursos::FarmConfig::Get().Message("DiagnosticFailed", "Falha ao criar diretório."), FColorList::Red); return; }
    const std::string path = export_dir + "/report.json";
    nlohmann::json report = nlohmann::json::object();
    report["generated_utc_epoch"] = stamp;
    report["plugin_version"] = "0.1.2-test";
    report["serialization_note"] = "Blobs are opaque UPrimalItem::GetItemBytes output; metadata is read from live ArkServerAPI objects. No byte offsets are inferred.";
    report["map"] = "";
    if (auto* gm = ArkApi::GetApiUtils().GetShooterGameMode()) { FString map; gm->GetMapName(&map); report["map"] = map.ToString(); }
    report["items"] = nlohmann::json::array();
    report["engram_catalog"] = nlohmann::json::array();
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
    if (!out) { Say(c, FazendaRecursos::FarmConfig::Get().Message("DiagnosticFailed", "Falha ao gravar diagnÃ³stico."), FColorList::Red); return; }
    out << report.dump(2); out.flush();
    if (!out) { Say(c, FazendaRecursos::FarmConfig::Get().Message("DiagnosticFailed", "Falha ao gravar diagnÃ³stico."), FColorList::Red); return; }
    Say(c, "DiagnÃ³stico salvo em ArkApi/Plugins/FazendaRecursos/diagnostics/items-" + std::to_string(stamp) + " (inclui blobs opacos das Souls detectadas).");
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
