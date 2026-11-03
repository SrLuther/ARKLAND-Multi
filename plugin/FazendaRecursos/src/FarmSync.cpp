#include "FarmSync.h"
#include "FarmConfig.h"
#include "FarmState.h"
#include "../../CustomShop/src/mysql.h"
#include <cstdlib>

namespace {
struct DbSettings {
    std::string host;
    unsigned int port = 3306;
    std::string user;
    std::string password;
    std::string database;
};

class MysqlConnection {
public:
    ~MysqlConnection() { if (db_) mysql_close(db_); }

    bool Open() {
        const std::string path = ArkApi::Tools::GetCurrentDir() +
            "/ArkApi/Plugins/CustomShop/config.json";
        std::ifstream in(path);
        if (!in) return Fail("CustomShop/config.json não encontrado");
        nlohmann::json root;
        try { in >> root; } catch (...) { return Fail("CustomShop/config.json inválido"); }
        const auto cfg = root.value("Database", nlohmann::json::object());
        DbSettings s;
        s.host = FRJsonString(cfg, "Host", "127.0.0.1");
        s.port = static_cast<unsigned int>(std::clamp(FRJsonInt(cfg, "Port", 3306), 1, 65535));
        s.user = FRJsonString(cfg, "User", "arkland");
        s.password = FRJsonString(cfg, "Password");
        s.database = FRJsonString(cfg, "Database", "arkland_shop");
        if (s.host.empty() || s.user.empty() || s.database.empty())
            return Fail("configuração Database incompleta no CustomShop");
        db_ = mysql_init(nullptr);
        if (!db_) return Fail("mysql_init falhou");
        my_bool reconnect = 1;
        mysql_options(db_, MYSQL_OPT_RECONNECT, &reconnect);
        // The local MariaDB instance used by ARKLAND does not offer TLS.
        // Match CustomShop's client options so the farm can use the same DB.
        my_bool ssl_enforce = 0;
        mysql_options(db_, static_cast<enum_mysql_set_option>(38), &ssl_enforce);
        my_bool ssl_verify = 0;
        mysql_options(db_, static_cast<enum_mysql_set_option>(21), &ssl_verify);
        if (!mysql_real_connect(db_, s.host.c_str(), s.user.c_str(), s.password.c_str(),
                s.database.c_str(), s.port, nullptr, 0)) {
            const std::string err = mysql_error(db_) ? mysql_error(db_) : "falha de conexão";
            mysql_close(db_); db_ = nullptr;
            return Fail("conexão MySQL falhou: " + err);
        }
        mysql_set_character_set(db_, "utf8mb4");
        if (!Query("SET SESSION sql_mode='NO_ENGINE_SUBSTITUTION'")) return false;
        return true;
    }

    MYSQL* Get() const { return db_; }
    bool Query(const std::string& sql) {
        if (!db_ || mysql_real_query(db_, sql.data(), static_cast<unsigned long>(sql.size())) != 0) {
            const std::string err = db_ && mysql_error(db_) ? mysql_error(db_) : "sem conexão";
            Log::GetLog()->warn("Fazenda MySQL: query falhou ({})", err);
            return false;
        }
        MYSQL_RES* result = mysql_store_result(db_);
        if (result) mysql_free_result(result);
        return true;
    }
    MYSQL_RES* Select(const std::string& sql) {
        if (!db_ || mysql_real_query(db_, sql.data(), static_cast<unsigned long>(sql.size())) != 0) {
            const std::string err = db_ && mysql_error(db_) ? mysql_error(db_) : "sem conexão";
            Log::GetLog()->warn("Fazenda MySQL: SELECT falhou ({})", err);
            return nullptr;
        }
        return mysql_store_result(db_);
    }
    std::string Escape(const std::string& value) const {
        if (!db_) return {};
        std::string out(value.size() * 2 + 1, '\0');
        const auto n = mysql_real_escape_string(db_, out.data(), value.data(),
            static_cast<unsigned long>(value.size()));
        out.resize(n);
        return out;
    }

private:
    bool Fail(const std::string& message) {
        Log::GetLog()->warn("Fazenda MySQL: {}", message);
        return false;
    }
    MYSQL* db_ = nullptr;
};

std::string BlobHex(const std::vector<unsigned char>& bytes) {
    static constexpr char digits[] = "0123456789ABCDEF";
    std::string out;
    out.resize(bytes.size() * 2);
    for (size_t i = 0; i < bytes.size(); ++i) {
        out[i * 2] = digits[bytes[i] >> 4];
        out[i * 2 + 1] = digits[bytes[i] & 0x0f];
    }
    return out;
}

class SyncWorker {
public:
    static SyncWorker& Get() { static SyncWorker worker; return worker; }

    void Start() {
        std::lock_guard<std::mutex> lock(mutex_);
        if (thread_.joinable()) return;
        stop_ = false;
        thread_ = std::thread([this] { Run(); });
    }
    void Stop() {
        { std::lock_guard<std::mutex> lock(mutex_); stop_ = true; }
        wake_.notify_all();
        if (thread_.joinable()) thread_.join();
    }
    void Queue(std::string steam_id) {
        if (steam_id.empty()) return;
        { std::lock_guard<std::mutex> lock(mutex_); queued_.insert(std::move(steam_id)); }
        wake_.notify_one();
    }
    void QueueCatalog() {
        { std::lock_guard<std::mutex> lock(mutex_); catalog_queued_ = true; }
        wake_.notify_one();
    }
    bool SyncUploadNow(const std::string& steam_id, const std::string& upload_id) {
        try {
            const auto player = FazendaRecursos::FarmState::Get().GetPlayer(steam_id);
            const auto found = player.uploaded_resources.find(upload_id);
            if (found == player.uploaded_resources.end()) return false;
            MysqlConnection db;
            if (!db.Open()) return false;
            return SyncOneUploadedResource(db, steam_id,
                FazendaRecursos::FarmConfig::Get().ServerId(), found->second);
        } catch (const std::exception& e) {
            Log::GetLog()->warn("Fazenda MySQL: falha ao persistir upload {} ({})", upload_id, e.what());
            return false;
        }
    }
    bool ClaimRedemptionStacks(const std::string& steam_id, const std::string& server_id,
                               std::vector<FazendaRecursos::FarmSync::RedemptionStack>& stacks) {
        stacks.clear();
        MysqlConnection db;
        if (!db.Open() || !db.Query("START TRANSACTION")) return false;
        const auto sid = db.Escape(steam_id), server = db.Escape(server_id);
        const auto share = db.Escape(FazendaRecursos::FarmConfig::Get().ShareKey());
        const std::string claim_sql = "SELECT id FROM farm_redemptions WHERE steam_id='" + sid +
            "' AND share_key='" + share + "' AND (status='PENDENTE' OR (status='PROCESSANDO' AND "
            "(claimed_at IS NULL OR claimed_at < DATE_SUB(UTC_TIMESTAMP(), INTERVAL 2 MINUTE)))) "
            "ORDER BY created_at ASC LIMIT 1 FOR UPDATE";
        MYSQL_RES* claim_result = db.Select(claim_sql);
        if (!claim_result) { db.Query("ROLLBACK"); return false; }
        MYSQL_ROW claim_row = mysql_fetch_row(claim_result);
        if (!claim_row || !claim_row[0]) {
            mysql_free_result(claim_result);
            return db.Query("COMMIT");
        }
        const std::string redemption_id = claim_row[0];
        mysql_free_result(claim_result);
        const std::string update_sql = "UPDATE farm_redemptions SET status='PROCESSANDO',claimed_by='" + server +
            "',claimed_at=UTC_TIMESTAMP() WHERE id='" + db.Escape(redemption_id) + "'";
        if (!db.Query(update_sql) || !db.Query("COMMIT")) { db.Query("ROLLBACK"); return false; }

        MYSQL_RES* result = db.Select(
            "SELECT d.redemption_id,r.resource_id,d.stack_index,d.quantity "
            "FROM farm_redemption_deliveries d JOIN farm_redemptions r ON r.id=d.redemption_id "
            "WHERE d.redemption_id='" + db.Escape(redemption_id) + "' AND d.status='PENDENTE' "
            "AND r.steam_id='" + sid + "' AND r.share_key='" + share + "' "
            "AND r.status='PROCESSANDO' AND r.claimed_by='" + server + "' ORDER BY d.stack_index");
        if (!result) return false;
        while (MYSQL_ROW row = mysql_fetch_row(result)) {
            if (!row[0] || !row[1] || !row[2] || !row[3]) continue;
            FazendaRecursos::FarmSync::RedemptionStack stack;
            stack.redemption_id = row[0];
            stack.resource_id = row[1];
            stack.stack_index = std::atoi(row[2]);
            stack.quantity = std::atoi(row[3]);
            if (stack.quantity > 0) stacks.emplace_back(std::move(stack));
        }
        mysql_free_result(result);
        return true;
    }

    bool CompleteRedemptionStack(const FazendaRecursos::FarmSync::RedemptionStack& stack,
                                 const std::string& steam_id, const std::string& server_id,
                                 bool delivered) {
        MysqlConnection db;
        if (!db.Open() || !db.Query("START TRANSACTION")) return false;
        const auto redemption = db.Escape(stack.redemption_id);
        const auto sid = db.Escape(steam_id), server = db.Escape(server_id);
        const auto share = db.Escape(FazendaRecursos::FarmConfig::Get().ShareKey());
        if (!delivered) {
            const bool ok = db.Query("UPDATE farm_redemptions SET status='PENDENTE',claimed_by=NULL,claimed_at=NULL "
                "WHERE id='" + redemption + "' AND steam_id='" + sid + "' AND share_key='" + share +
                "' AND claimed_by='" + server + "'");
            if (!db.Query(ok ? "COMMIT" : "ROLLBACK")) return false;
            return ok;
        }

        const std::string check_sql = "SELECT d.quantity,r.resource_id FROM farm_redemption_deliveries d "
            "JOIN farm_redemptions r ON r.id=d.redemption_id WHERE d.redemption_id='" + redemption +
            "' AND d.stack_index=" + std::to_string(stack.stack_index) + " AND d.status='PENDENTE' "
            "AND r.steam_id='" + sid + "' AND r.share_key='" + share + "' "
            "AND r.status='PROCESSANDO' AND r.claimed_by='" + server + "' FOR UPDATE";
        MYSQL_RES* check = db.Select(check_sql);
        if (!check) { db.Query("ROLLBACK"); return false; }
        MYSQL_ROW row = mysql_fetch_row(check);
        if (!row || !row[0] || !row[1] || std::atoi(row[0]) != stack.quantity || stack.resource_id != row[1]) {
            mysql_free_result(check); db.Query("ROLLBACK"); return false;
        }
        const std::string resource = row[1];
        mysql_free_result(check);
        MYSQL_RES* stock_result = db.Select("SELECT stock FROM farm_player_resources WHERE share_key='" + share +
            "' AND steam_id='" + sid + "' AND resource_id='" + db.Escape(resource) + "' FOR UPDATE");
        if (!stock_result) { db.Query("ROLLBACK"); return false; }
        MYSQL_ROW stock_row = mysql_fetch_row(stock_result);
        if (!stock_row || !stock_row[0] || std::atoi(stock_row[0]) < stack.quantity) {
            mysql_free_result(stock_result); db.Query("ROLLBACK"); return false;
        }
        mysql_free_result(stock_result);
        bool ok = db.Query("UPDATE farm_player_resources SET stock=stock-" + std::to_string(stack.quantity) +
            ",updated_at=UTC_TIMESTAMP() WHERE share_key='" + share + "' AND steam_id='" + sid +
            "' AND resource_id='" + db.Escape(resource) + "' AND stock >= " + std::to_string(stack.quantity));
        if (ok) ok = db.Query("UPDATE farm_redemption_deliveries d JOIN farm_redemptions r ON r.id=d.redemption_id "
            "SET d.status='ENTREGUE',d.delivered_at=UTC_TIMESTAMP() WHERE d.redemption_id='" + redemption +
            "' AND d.stack_index=" + std::to_string(stack.stack_index) + " AND d.status='PENDENTE' "
            "AND r.steam_id='" + sid + "' AND r.share_key='" + share + "' AND r.claimed_by='" + server + "'");
        if (ok) ok = db.Query("UPDATE farm_redemptions r SET "
            "r.delivered_amount=(SELECT COALESCE(SUM(d.quantity),0) FROM farm_redemption_deliveries d "
            "WHERE d.redemption_id=r.id AND d.status='ENTREGUE'),"
            "r.status=IF((SELECT COALESCE(SUM(d.quantity),0) FROM farm_redemption_deliveries d "
            "WHERE d.redemption_id=r.id AND d.status='ENTREGUE')>=r.amount,'ENTREGUE','PROCESSANDO'),"
            "r.completed_at=IF((SELECT COALESCE(SUM(d.quantity),0) FROM farm_redemption_deliveries d "
            "WHERE d.redemption_id=r.id AND d.status='ENTREGUE')>=r.amount,UTC_TIMESTAMP(),NULL),"
            "r.claimed_at=UTC_TIMESTAMP() WHERE r.id='" + redemption + "' AND r.steam_id='" + sid +
            "' AND r.share_key='" + share + "' AND r.claimed_by='" + server + "'");
        if (!db.Query(ok ? "COMMIT" : "ROLLBACK")) return false;
        return ok;
    }

private:
    std::mutex mutex_;
    std::condition_variable wake_;
    std::set<std::string> queued_;
    std::thread thread_;
    bool stop_ = false;
    bool catalog_queued_ = false;
    std::string applied_revision_;

    void FetchAuthoritativeConfig() {
        const auto share_key = FazendaRecursos::FarmConfig::Get().ShareKey();
        MysqlConnection db;
        if (!db.Open()) return;
        MYSQL_RES* result = db.Select("SELECT config_json,revision FROM farm_share_configs WHERE share_key='" +
            db.Escape(share_key) + "' LIMIT 1");
        if (!result) return;
        MYSQL_ROW row = mysql_fetch_row(result);
        if (!row || !row[0] || !row[1]) { mysql_free_result(result); return; }
        const std::string serialized = row[0];
        const std::string revision = row[1];
        mysql_free_result(result);
        {
            std::lock_guard<std::mutex> lock(mutex_);
            if (revision.empty() || revision == applied_revision_) return;
        }
        try {
            const auto config = nlohmann::json::parse(serialized);
            if (!config.is_object() || !config.contains("FazendaRecursos") ||
                !config["FazendaRecursos"].is_object() ||
                FRJsonString(config["FazendaRecursos"], "FarmShareKey", "default") != share_key) {
                Log::GetLog()->warn("Fazenda: configuração mestre inválida para share_key={}", share_key);
                return;
            }
            if (FazendaRecursos::FarmConfig::Get().ApplyRemoteConfig(config)) {
                std::lock_guard<std::mutex> lock(mutex_);
                applied_revision_ = revision;
                catalog_queued_ = true;
                wake_.notify_one();
            }
        } catch (const std::exception& e) {
            Log::GetLog()->warn("Fazenda: JSON mestre inválido para share_key={} ({})", share_key, e.what());
        }
    }

    static bool SyncCatalog(MysqlConnection& db, const std::vector<FazendaRecursos::ResourceDefinition>& defs,
                            const std::string& server_id) {
        const auto server = db.Escape(server_id);
        const auto share = db.Escape(FazendaRecursos::FarmConfig::Get().ShareKey());
        nlohmann::json signature = nlohmann::json::array();
        for (const auto& d : defs) signature.push_back({
            {"id", d.id}, {"name", d.name}, {"category", d.category},
            {"class", d.item_class}, {"enabled", d.enabled}, {"output", d.output_quantity},
            {"interval", d.interval_seconds}, {"stack", d.stack_size}, {"capacity", d.capacity}
        });
        uint64_t hash = 1469598103934665603ULL;
        for (const unsigned char byte : signature.dump()) { hash ^= byte; hash *= 1099511628211ULL; }
        const auto revision = std::to_string(hash);
        for (const auto& def : defs) {
            const std::string sql =
                "INSERT INTO farm_resource_catalog (server_id,resource_id,share_key,category,resource_name,item_class,enabled,"
                "output_quantity,interval_seconds,stack_size,capacity,config_revision,updated_at) VALUES ('" +
                server + "','" + db.Escape(def.id) + "','" + share + "','" + db.Escape(def.category) + "','" +
                db.Escape(def.name) + "','" + db.Escape(def.item_class) + "'," +
                (def.enabled ? "1" : "0") + "," + std::to_string(def.output_quantity) + "," +
                std::to_string(def.interval_seconds) + "," + std::to_string(def.stack_size) + "," +
                std::to_string(def.capacity) + ",'" + revision + "',UTC_TIMESTAMP()) "
                "ON DUPLICATE KEY UPDATE share_key=VALUES(share_key),category=VALUES(category),resource_name=VALUES(resource_name),"
                "item_class=VALUES(item_class),enabled=VALUES(enabled),output_quantity=VALUES(output_quantity),"
                "interval_seconds=VALUES(interval_seconds),stack_size=VALUES(stack_size),capacity=VALUES(capacity),"
                "config_revision=VALUES(config_revision),updated_at=VALUES(updated_at)";
            if (!db.Query(sql)) return false;
        }
        // The catalog is a snapshot of the loaded config. If a resource is
        // removed from config.json, do not leave its previous DB row enabled.
        // Keep the row for existing uploads/history, but prevent new uploads
        // and redemptions through the website.
        std::string deactivate_sql = "UPDATE farm_resource_catalog SET enabled=0,updated_at=UTC_TIMESTAMP() "
            "WHERE server_id='" + server + "' AND share_key='" + share + "'";
        if (!defs.empty()) {
            deactivate_sql += " AND resource_id NOT IN (";
            bool first = true;
            for (const auto& def : defs) {
                if (!first) deactivate_sql += ",";
                first = false;
                deactivate_sql += "'" + db.Escape(def.id) + "'";
            }
            deactivate_sql += ")";
        }
        if (!db.Query(deactivate_sql)) return false;
        return true;
    }

    static bool SyncOneUploadedResource(MysqlConnection& db, const std::string& steam_id,
                                        const std::string& server_id,
                                        const FazendaRecursos::PlayerFarm::UploadedResource& upload) {
        if (upload.status != "active" && upload.status != "recovered" && upload.status != "rolled_back")
            return false;
        const std::filesystem::path filename(upload.blob_file);
        if (filename.empty() || filename.filename().string() != upload.blob_file) return false;
        auto& farm = FazendaRecursos::FarmState::Get();
        std::ifstream input(std::filesystem::path(farm.ResourceDirectory(steam_id)) / filename, std::ios::binary);
        if (!input) return false;
        std::vector<unsigned char> blob((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
        if (blob.empty() || blob.size() > 8 * 1024 * 1024) return false;
        const auto hex = BlobHex(blob);
        std::string resource_name = upload.resource_name.empty() ? upload.resource_id : upload.resource_name;
        for (const auto& definition : FazendaRecursos::FarmConfig::Get().ResourcesSnapshot())
            if (definition.id == upload.resource_id) { resource_name = definition.name; break; }
        const auto sid = db.Escape(steam_id), upload_id = db.Escape(upload.id);
        const auto share = db.Escape(FazendaRecursos::FarmConfig::Get().ShareKey());
        const std::string sql =
            "INSERT INTO farm_uploaded_resources (share_key,steam_id,upload_id,resource_id,resource_name,item_class,display_name,"
            "item_quantity,blob_size,status,server_id,uploaded_at,item_blob) VALUES ('" + share + "','" + sid + "','" + upload_id + "','" +
            db.Escape(upload.resource_id) + "','" + db.Escape(resource_name) + "','" + db.Escape(upload.item_class) +
            "','" + db.Escape(upload.display_name) + "'," + std::to_string(upload.item_quantity) + "," +
            std::to_string(blob.size()) + ",'" + db.Escape(upload.status) + "','" + db.Escape(server_id) +
            "',FROM_UNIXTIME(" + std::to_string(upload.uploaded_utc) + "),UNHEX('" + hex + "')) "
            "ON DUPLICATE KEY UPDATE status=VALUES(status),server_id=VALUES(server_id)";
        return db.Query(sql);
    }

    static bool AccrueAllActiveResources() {
        auto& config = FazendaRecursos::FarmConfig::Get();
        const auto definitions = config.ResourcesSnapshot();
        const std::string share_key = config.ShareKey();
        const int64_t now = static_cast<int64_t>(std::chrono::duration_cast<std::chrono::seconds>(
            std::chrono::system_clock::now().time_since_epoch()).count());
        MysqlConnection db;
        if (!db.Open() || !db.Query("START TRANSACTION")) return false;
        const auto share = db.Escape(share_key);
        for (const auto& def : definitions) {
            if (!def.enabled || def.interval_seconds < 1 || def.output_quantity < 1) continue;
            MYSQL_RES* result = db.Select("SELECT steam_id,stock,last_accrual_utc FROM farm_player_resources WHERE share_key='" +
                share + "' AND resource_id='" + db.Escape(def.id) + "' AND active=1 FOR UPDATE");
            if (!result) { db.Query("ROLLBACK"); return false; }
            std::vector<std::tuple<std::string, int64_t, int64_t>> rows;
            while (MYSQL_ROW row = mysql_fetch_row(result)) {
                if (row[0] && row[1] && row[2])
                    rows.emplace_back(row[0], std::max<int64_t>(0, std::atoll(row[1])),
                                      std::max<int64_t>(0, std::atoll(row[2])));
            }
            mysql_free_result(result);
            for (const auto& [steam_id, stock, last] : rows) {
                if (last <= 0 || now <= last) continue;
                const int64_t elapsed_cycles = (now - last) / def.interval_seconds;
                const int64_t capacity_cycles = std::max<int64_t>(0, def.capacity - stock) / def.output_quantity;
                const int64_t cycles = std::min(elapsed_cycles, capacity_cycles);
                if (cycles <= 0) continue;
                const auto next_stock = stock + cycles * def.output_quantity;
                const auto next_tick = last + cycles * def.interval_seconds;
                if (!db.Query("UPDATE farm_player_resources SET stock=" + std::to_string(next_stock) +
                    ",last_accrual_utc=" + std::to_string(next_tick) + ",updated_at=UTC_TIMESTAMP() "
                    "WHERE share_key='" + share + "' AND steam_id='" + db.Escape(steam_id) +
                    "' AND resource_id='" + db.Escape(def.id) + "' AND active=1")) {
                    db.Query("ROLLBACK"); return false;
                }
            }
        }
        return db.Query("COMMIT");
    }

    static bool SyncPlayer(const std::string& steam_id) {
        try {
            auto& config = FazendaRecursos::FarmConfig::Get();
            const auto definitions = config.ResourcesSnapshot();
            const auto now = static_cast<int64_t>(std::chrono::duration_cast<std::chrono::seconds>(
                std::chrono::system_clock::now().time_since_epoch()).count());
            auto& state = FazendaRecursos::FarmState::Get();
            const auto player = state.GetPlayer(steam_id);
            MysqlConnection db;
            if (!db.Open() || !db.Query("START TRANSACTION")) return false;
            bool ok = SyncCatalog(db, definitions, config.ServerId());
            const auto server = db.Escape(config.ServerId());
            const auto sid = db.Escape(steam_id);
            const auto version = "0.1.13-test";
            if (ok) {
                for (const auto& def : definitions) {
                    if (!def.enabled) continue;
                    const auto found = player.resources.find(def.id);
                    const int64_t stock = 0;
                    const bool active = found != player.resources.end() && found->second.active;
                    const int64_t last = found == player.resources.end() ? now : found->second.last_accrual_utc;
                    const auto share = db.Escape(config.ShareKey());
                    const std::string sql = "INSERT INTO farm_player_resources "
                        "(share_key,steam_id,resource_id,stock,active,last_accrual_utc,server_id,plugin_version,updated_at) VALUES ('" +
                        share + "','" + sid + "','" + db.Escape(def.id) + "'," + std::to_string(stock) + "," +
                        (active ? "1" : "0") + "," + std::to_string(last) + ",'" + server + "','" + version +
                        "',UTC_TIMESTAMP()) ON DUPLICATE KEY UPDATE "
                        "last_accrual_utc=IF(active=0 AND VALUES(active)=1,VALUES(last_accrual_utc),last_accrual_utc),"
                        "server_id=IF(VALUES(active)=1,VALUES(server_id),server_id),"
                        "plugin_version=VALUES(plugin_version),active=IF(VALUES(active)=1,1,active),updated_at=VALUES(updated_at)";
                    if (!db.Query(sql)) { ok = false; break; }
                }
            }
            if (ok) {
                for (const auto& [id, upload] : player.uploaded_resources) {
                    if (upload.status == "active" || upload.status == "recovered" || upload.status == "rolled_back") {
                        if (!SyncOneUploadedResource(db, steam_id, config.ServerId(), upload)) { ok = false; break; }
                    }
                }
            }
            if (!db.Query(ok ? "COMMIT" : "ROLLBACK")) return false;
            if (!ok) return false;
            Log::GetLog()->info("Fazenda MySQL: tabelas compartilhadas atualizadas (steam={}, catalogo={}, versao={})",
                steam_id, definitions.size(), version);
            return true;
        } catch (const std::exception& e) {
            Log::GetLog()->warn("Fazenda MySQL: sincronização falhou para {} ({})", steam_id, e.what());
            return false;
        }
    }

    void Run() {
        bool first_sync = true;
        for (;;) {
            std::set<std::string> queued;
            bool full_sync = false;
            bool catalog_sync = false;
            {
                std::unique_lock<std::mutex> lock(mutex_);
                bool notified = false;
                if (!first_sync) {
                    const auto interval = std::chrono::seconds(FazendaRecursos::FarmConfig::Get().SyncIntervalSeconds());
                    notified = wake_.wait_for(lock, interval,
                        [this] { return stop_ || catalog_queued_ || !queued_.empty(); });
                }
                if (stop_) return;
                queued.swap(queued_);
                full_sync = first_sync || !notified;
                first_sync = false;
                catalog_sync = catalog_queued_;
                catalog_queued_ = false;
            }
            FetchAuthoritativeConfig();
            if (catalog_sync && !full_sync) {
                MysqlConnection db;
                if (db.Open() && !SyncCatalog(db, FazendaRecursos::FarmConfig::Get().ResourcesSnapshot(),
                                              FazendaRecursos::FarmConfig::Get().ServerId()))
                    Log::GetLog()->warn("Fazenda MySQL: falha ao publicar catálogo atualizado");
            }
            if (full_sync) {
                if (!AccrueAllActiveResources())
                    Log::GetLog()->warn("Fazenda MySQL: falha ao processar ciclos do grupo {}", FazendaRecursos::FarmConfig::Get().ShareKey());
                MysqlConnection db;
                if (db.Open()) SyncCatalog(db, FazendaRecursos::FarmConfig::Get().ResourcesSnapshot(),
                                           FazendaRecursos::FarmConfig::Get().ServerId());
                for (const auto& id : FazendaRecursos::FarmState::Get().PlayerIds()) {
                    { std::lock_guard<std::mutex> lock(mutex_); if (stop_) return; }
                    SyncPlayer(id);
                }
            }
            for (const auto& id : queued) SyncPlayer(id);
        }
    }
};
}

namespace FazendaRecursos::FarmSync {
void Start() { SyncWorker::Get().Start(); }
void Stop() { SyncWorker::Get().Stop(); }
void QueuePlayer(const std::string& steam_id) { SyncWorker::Get().Queue(steam_id); }
void QueueCatalog() { SyncWorker::Get().QueueCatalog(); }
bool SyncUploadedResourceNow(const std::string& steam_id, const std::string& upload_id) {
    return SyncWorker::Get().SyncUploadNow(steam_id, upload_id);
}
bool ClaimRedemptionStacks(const std::string& steam_id, const std::string& server_id,
                          std::vector<RedemptionStack>& stacks) {
    return SyncWorker::Get().ClaimRedemptionStacks(steam_id, server_id, stacks);
}
bool CompleteRedemptionStack(const RedemptionStack& stack, const std::string& steam_id,
                             const std::string& server_id, bool delivered) {
    return SyncWorker::Get().CompleteRedemptionStack(stack, steam_id, server_id, delivered);
}
}

