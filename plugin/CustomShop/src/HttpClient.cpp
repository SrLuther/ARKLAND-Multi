#include "pch.h"
#include "HttpClient.h"
#include "ShopBridge.h"
#include "ShopConfig.h"
#include "ShopStore.h"
#include "ShopPoints.h"
#include "ShopDebug.h"

#include <chrono>

namespace {

// ── WinHTTP helpers ──────────────────────────────────────────────

HINTERNET g_session = nullptr;

// Capas o bloqueio no game thread: WinHTTP default (resolve infinito / connect 60s)
// pode ultrapassar o HangWatcher do ASE se a API estiver lenta ou inacessível.
constexpr int kHttpResolveMs = 5000;
constexpr int kHttpConnectMs = 5000;
constexpr int kHttpSendMs = 8000;
constexpr int kHttpReceiveMs = 8000;
constexpr size_t kHttpBodySnippetMax = 240;

bool EnsureSession() {
    if (!g_session) {
        g_session = WinHttpOpen(
            L"CustomShop/1.0",
            WINHTTP_ACCESS_TYPE_DEFAULT_PROXY,
            nullptr, nullptr, 0);
        if (g_session) {
            WinHttpSetTimeouts(
                g_session,
                kHttpResolveMs, kHttpConnectMs, kHttpSendMs, kHttpReceiveMs);
        }
    }
    return g_session != nullptr;
}

/** Path sem query string — evita logar tokens/?api_key= em URLs. */
std::string SanitizePathForLog(const std::string& path) {
    const auto q = path.find('?');
    return (q == std::string::npos) ? path : path.substr(0, q);
}

std::string TruncateForLog(const std::string& text, size_t max_n = kHttpBodySnippetMax) {
    if (text.size() <= max_n) return text;
    return text.substr(0, max_n) + "…";
}

int ElapsedMs(const std::chrono::steady_clock::time_point& started) {
    return static_cast<int>(
        std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now() - started)
            .count());
}

nlohmann::json BuildHttpFields(const char* method,
                               const std::string& host,
                               const std::string& path,
                               int duration_ms,
                               int http_status = 0,
                               DWORD winhttp_error = 0,
                               const char* error = nullptr,
                               const std::string* response_snippet = nullptr) {
    nlohmann::json fields = {
        {"method", method ? method : ""},
        {"host", host},
        {"path", SanitizePathForLog(path)},
        {"duration_ms", duration_ms},
        {"timeout_ms_resolve", kHttpResolveMs},
        {"timeout_ms_connect", kHttpConnectMs},
        {"timeout_ms_send", kHttpSendMs},
        {"timeout_ms_receive", kHttpReceiveMs},
    };
    if (http_status > 0) fields["http_status"] = http_status;
    if (winhttp_error != 0) fields["winhttp_error"] = static_cast<int>(winhttp_error);
    if (error && error[0]) fields["error"] = error;
    if (response_snippet && !response_snippet->empty())
        fields["response_snippet"] = TruncateForLog(*response_snippet);
    return fields;
}

std::string ReadHttpBody(HINTERNET hRequest, size_t hard_cap = 256 * 1024) {
    std::string result;
    DWORD bytes_avail = 0, bytes_read = 0;
    char buf[4096];
    while (WinHttpQueryDataAvailable(hRequest, &bytes_avail) && bytes_avail > 0) {
        while (bytes_avail > 0) {
            if (result.size() >= hard_cap) return result;
            DWORD to_read = (bytes_avail > sizeof(buf)) ? (DWORD)sizeof(buf) : bytes_avail;
            if (result.size() + to_read > hard_cap)
                to_read = static_cast<DWORD>(hard_cap - result.size());
            if (WinHttpReadData(hRequest, buf, to_read, &bytes_read) && bytes_read > 0) {
                result.append(buf, bytes_read);
                bytes_avail -= bytes_read;
            } else {
                break;
            }
        }
    }
    return result;
}

void WarnHttpStatus(const char* method,
                    const std::string& host,
                    const std::string& path,
                    int status_code,
                    int duration_ms,
                    const std::string& body) {
    const std::string safe_path = SanitizePathForLog(path);
    Log::GetLog()->warn(
        "HttpClient: {} HTTP {} host={} path={}", method, status_code, host, safe_path);
    CustomShop::Debug::Fields hf;
    hf.extra = BuildHttpFields(
        method, host, path, duration_ms, status_code, 0, "http_error", &body);
    CustomShop::Debug::Warn(
        "Http", hf,
        std::string(method) + " HTTP " + std::to_string(status_code) + " " + safe_path);
}

void WarnHttpTransport(const char* method,
                       const std::string& host,
                       const std::string& path,
                       int duration_ms,
                       DWORD winhttp_error,
                       const char* error_tag) {
    const std::string safe_path = SanitizePathForLog(path);
    CustomShop::Debug::Fields hf;
    hf.extra = BuildHttpFields(
        method, host, path, duration_ms, 0, winhttp_error, error_tag, nullptr);
    CustomShop::Debug::Warn(
        "Http", hf,
        std::string(method) + " " + error_tag + " err=" + std::to_string(winhttp_error) +
            " " + safe_path);
}

bool ParseUrlParts(const std::string& url,
                   std::string& host,
                   std::string& path,
                   int& port,
                   bool& secure) {
    std::string remaining = url;
    port = 80;
    secure = false;

    if (remaining.find("http://") == 0) {
        remaining = remaining.substr(7);
        secure = false;
    } else if (remaining.find("https://") == 0) {
        remaining = remaining.substr(8);
        secure = true;
        port = 443;
    }

    const auto slash_pos = remaining.find('/');
    const auto colon_pos = remaining.find(':');

    if (colon_pos != std::string::npos &&
        (slash_pos == std::string::npos || colon_pos < slash_pos)) {
        host = remaining.substr(0, colon_pos);
        const auto port_end =
            slash_pos != std::string::npos ? slash_pos : remaining.size();
        try {
            port = std::stoi(remaining.substr(colon_pos + 1, port_end - colon_pos - 1));
        } catch (...) {
            port = secure ? 443 : 80;
        }
    } else {
        const auto end = slash_pos != std::string::npos ? slash_pos : remaining.size();
        host = remaining.substr(0, end);
    }
    path = (slash_pos != std::string::npos) ? remaining.substr(slash_pos) : "/";
    return !host.empty();
}

// Simple blocking HTTP GET, returns response body or empty string on failure.
std::string HttpGet(const std::string& url) {
    if (!EnsureSession()) return "";

    std::string host, path;
    int port = 80;
    bool secure = false;
    if (!ParseUrlParts(url, host, path, port, secure)) return "";

    const auto started = std::chrono::steady_clock::now();
    std::wstring whost(host.begin(), host.end());
    std::wstring wpath(path.begin(), path.end());

    HINTERNET hConnect = WinHttpConnect(g_session, whost.c_str(), (INTERNET_PORT)port, 0);
    if (!hConnect) {
        WarnHttpTransport(
            "GET", host, path, ElapsedMs(started), GetLastError(), "WinHttpConnect failed");
        return "";
    }

    DWORD request_flags = secure ? WINHTTP_FLAG_SECURE : 0;
    HINTERNET hRequest = WinHttpOpenRequest(hConnect, L"GET", wpath.c_str(),
                                             nullptr, nullptr, nullptr, request_flags);
    if (!hRequest) {
        WarnHttpTransport(
            "GET", host, path, ElapsedMs(started), GetLastError(), "WinHttpOpenRequest failed");
        WinHttpCloseHandle(hConnect);
        return "";
    }

    if (!CustomShop::HttpClient::g_api_key.empty()) {
        const auto& key = CustomShop::HttpClient::g_api_key;
        std::wstring api_key_hdr = L"X-API-Key: " + std::wstring(key.begin(), key.end());
        WinHttpAddRequestHeaders(hRequest, api_key_hdr.c_str(), (DWORD)wcslen(api_key_hdr.c_str()),
                                 WINHTTP_ADDREQ_FLAG_ADD);
    }

    std::string result;
    if (WinHttpSendRequest(hRequest, nullptr, 0, nullptr, 0, 0, 0)) {
        if (!WinHttpReceiveResponse(hRequest, nullptr)) {
            WarnHttpTransport(
                "GET", host, path, ElapsedMs(started), GetLastError(),
                "WinHttpReceiveResponse failed / timeout");
            WinHttpCloseHandle(hRequest);
            WinHttpCloseHandle(hConnect);
            return "";
        }
        DWORD status_code = 0;
        DWORD status_size = sizeof(status_code);
        if (WinHttpQueryHeaders(
                hRequest,
                WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER,
                WINHTTP_HEADER_NAME_BY_INDEX,
                &status_code,
                &status_size,
                WINHTTP_NO_HEADER_INDEX)) {
            if (status_code >= 400) {
                result = ReadHttpBody(hRequest);
                WarnHttpStatus(
                    "GET", host, path, static_cast<int>(status_code), ElapsedMs(started),
                    result);
                WinHttpCloseHandle(hRequest);
                WinHttpCloseHandle(hConnect);
                return "";
            }
        }
        result = ReadHttpBody(hRequest);
    } else {
        WarnHttpTransport(
            "GET", host, path, ElapsedMs(started), GetLastError(),
            "WinHttpSendRequest failed / timeout");
    }

    WinHttpCloseHandle(hRequest);
    WinHttpCloseHandle(hConnect);
    return result;
}

// Simple blocking HTTP POST JSON, returns response body.
std::string HttpPostJson(const std::string& url, const std::string& json_body) {
    if (!EnsureSession()) return "";

    std::string host, path;
    int port = 80;
    bool secure = false;
    if (!ParseUrlParts(url, host, path, port, secure)) return "";

    const auto started = std::chrono::steady_clock::now();
    std::wstring whost(host.begin(), host.end());
    std::wstring wpath(path.begin(), path.end());

    HINTERNET hConnect = WinHttpConnect(g_session, whost.c_str(), (INTERNET_PORT)port, 0);
    if (!hConnect) {
        WarnHttpTransport(
            "POST", host, path, ElapsedMs(started), GetLastError(), "WinHttpConnect failed");
        return "";
    }

    DWORD request_flags = secure ? WINHTTP_FLAG_SECURE : 0;
    HINTERNET hRequest = WinHttpOpenRequest(hConnect, L"POST", wpath.c_str(),
                                             nullptr, nullptr, nullptr, request_flags);
    if (!hRequest) {
        WarnHttpTransport(
            "POST", host, path, ElapsedMs(started), GetLastError(), "WinHttpOpenRequest failed");
        WinHttpCloseHandle(hConnect);
        return "";
    }

    // Content-Type header
    LPCWSTR content_type = L"Content-Type: application/json";
    WinHttpAddRequestHeaders(hRequest, content_type, (DWORD)wcslen(content_type),
                             WINHTTP_ADDREQ_FLAG_ADD);

    if (!CustomShop::HttpClient::g_api_key.empty()) {
        const auto& key = CustomShop::HttpClient::g_api_key;
        std::wstring api_key_hdr = L"X-API-Key: " + std::wstring(key.begin(), key.end());
        WinHttpAddRequestHeaders(hRequest, api_key_hdr.c_str(), (DWORD)wcslen(api_key_hdr.c_str()),
                                 WINHTTP_ADDREQ_FLAG_ADD);
    }

    std::string result;
    if (WinHttpSendRequest(hRequest, nullptr, 0, (LPVOID)json_body.c_str(),
                           (DWORD)json_body.size(), (DWORD)json_body.size(), 0)) {
        if (!WinHttpReceiveResponse(hRequest, nullptr)) {
            WarnHttpTransport(
                "POST", host, path, ElapsedMs(started), GetLastError(),
                "WinHttpReceiveResponse failed / timeout");
            WinHttpCloseHandle(hRequest);
            WinHttpCloseHandle(hConnect);
            return "";
        }
        DWORD status_code = 0;
        DWORD status_size = sizeof(status_code);
        if (WinHttpQueryHeaders(
                hRequest,
                WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER,
                WINHTTP_HEADER_NAME_BY_INDEX,
                &status_code,
                &status_size,
                WINHTTP_NO_HEADER_INDEX)) {
            result = ReadHttpBody(hRequest);
            if (status_code >= 400) {
                WarnHttpStatus(
                    "POST", host, path, static_cast<int>(status_code), ElapsedMs(started),
                    result);
            }
        } else {
            result = ReadHttpBody(hRequest);
        }
    } else {
        WarnHttpTransport(
            "POST", host, path, ElapsedMs(started), GetLastError(),
            "WinHttpSendRequest failed / timeout");
    }

    WinHttpCloseHandle(hRequest);
    WinHttpCloseHandle(hConnect);
    return result;
}

} // anonymous namespace

namespace {

std::wstring Utf8ToWide(const std::string& text) {
    if (text.empty()) return L"";
    const int len = MultiByteToWideChar(CP_UTF8, 0, text.c_str(), -1, nullptr, 0);
    if (len <= 0) return std::wstring(text.begin(), text.end());
    std::wstring out(static_cast<size_t>(len - 1), L'\0');
    MultiByteToWideChar(CP_UTF8, 0, text.c_str(), -1, &out[0], len);
    return out;
}

bool IsUnknownCatalogFailure(const std::string& fail_reason) {
    return fail_reason == "kit_desconhecido" || fail_reason == "item_desconhecido";
}

// Parses plugin API JSON; empty body is a soft failure (caller may retry on next poll).
bool TryParseApiJson(const std::string& body, nlohmann::json& out, const char* context) {
    if (body.empty()) {
        Log::GetLog()->debug("HttpClient: {} empty response", context);
        return false;
    }
    try {
        out = nlohmann::json::parse(body);
        return true;
    } catch (const std::exception& e) {
        Log::GetLog()->error("HttpClient: {} JSON parse error: {}", context, e.what());
        return false;
    }
}

bool TryReloadConfigForDelivery() {
    try {
        CustomShop::ShopConfig::Get().Load();
        // Paridade Shop.Reload: URL/chave da web também mudam no config.json.
        CustomShop::HttpClient::Configure(
            CustomShop::ShopConfig::Get().WebApiUrl(),
            CustomShop::ShopConfig::Get().WebApiKey());
        Log::GetLog()->info("HttpClient: config reloaded before retrying delivery");
        return true;
    } catch (const std::exception& e) {
        Log::GetLog()->error("HttpClient: config reload failed: {}", e.what());
        return false;
    }
}

std::wstring DeliveryFailureUserMessage(const std::string& item_id,
                                        const std::string& fail_reason) {
    if (fail_reason == "kit_desconhecido" || fail_reason == "item_desconhecido") {
        return L"[Shop] '" + Utf8ToWide(item_id)
            + L"' nao esta no catalogo deste mapa. Sincronize plugins no TEK.";
    }
    if (fail_reason.rfind("sem_permissao:", 0) == 0) {
        const std::string groups = fail_reason.substr(14);
        return L"[Shop] Falta permissao/licenca: " + Utf8ToWide(groups);
    }
    if (fail_reason == "sem_licenca") {
        return L"[Shop] Falta licenca ativa para resgatar '" + Utf8ToWide(item_id) + L"'";
    }
    if (fail_reason == "licenca_falhou" || fail_reason == "licenca_mal_configurada") {
        return L"[Shop] Falha ao conceder licenca de '" + Utf8ToWide(item_id)
            + L"'. Contate um admin.";
    }
    if (fail_reason == "dino_spawn_falhou") {
        return L"[Shop] Falha ao spawnar dino de '" + Utf8ToWide(item_id)
            + L"'. Tente novamente ou contate um admin.";
    }
    if (fail_reason == "sem_conteudo") {
        return L"[Shop] Kit '" + Utf8ToWide(item_id)
            + L"' sem conteudo entregavel no catalogo.";
    }
    if (fail_reason == "sem_usos_kit") {
        return L"[Shop] Voce esgotou os resgates do kit '" + Utf8ToWide(item_id)
            + L"'. Contate um admin se precisar.";
    }
    return L"[Shop] Falha ao entregar '" + Utf8ToWide(item_id)
        + L"'. Contate um admin.";
}

} // anonymous namespace

namespace CustomShop {
namespace HttpClient {

// ── Configuration ─────────────────────────────────────────────────

std::string g_web_url = "http://127.0.0.1:5177";
std::string g_auth_token = "";  // Flask session cookie value (legacy)
std::string g_api_key   = "";   // X-API-Key for arkshop_web authentication

void Configure(const std::string& web_url, const std::string& api_key) {
    g_web_url = web_url;
    g_api_key  = api_key;
    Log::GetLog()->info("HttpClient: configured url='{}' api_key_set={}",
                        web_url, !api_key.empty());
}

void Shutdown() {
    if (g_session) {
        WinHttpCloseHandle(g_session);
        g_session = nullptr;
    }
}

std::string PostJson(const std::string& path, const std::string& json_body) {
    const std::string url = g_web_url + path;
    return HttpPostJson(url, json_body);
}

std::string Get(const std::string& path) {
    return HttpGet(g_web_url + path);
}

// ── Pending delivery API ──────────────────────────────────────────

bool DeliverPending(AShooterPlayerController* controller) {
    if (!controller) return false;

    const std::string steam_id = Bridge::GetSteamId(controller);
    if (steam_id.empty()) return false;

    Log::GetLog()->info("HttpClient: checking pending deliveries for '{}' at {}",
                        steam_id, g_web_url);

    // Atomically claim PENDENTE orders (prevents duplicate AddTimed on race).
    const std::string claim_url = g_web_url + "/api/pending/claim";
    const std::string claim_body = nlohmann::json{{"steam_id", steam_id}}.dump();
    std::string claim_resp = HttpPostJson(claim_url, claim_body);

    nlohmann::json json;
    if (!TryParseApiJson(claim_resp, json, "claim")) {
        // Empty body usually means a transient network/HTTP failure — skip error spam.
        return claim_resp.empty();
    }

    if (!json.value("ok", false)) {
        Log::GetLog()->warn("HttpClient: claim API returned not ok: {}", claim_resp);
        return false;
    }

    nlohmann::json items = json.contains("items")
        ? json["items"]
        : json.value("orders", nlohmann::json::array());

    if (!items.is_array() || items.empty()) {
        Log::GetLog()->info("HttpClient: no pending deliveries for '{}'", steam_id);
        return true;  // nothing to deliver, but not an error
    }

    Log::GetLog()->info("HttpClient: claimed {} pending item(s) for '{}'",
                        items.size(), steam_id);

    std::vector<std::string> delivered_ids;
    std::vector<std::string> failed_ids;
    nlohmann::json deliveries = nlohmann::json::array();
    nlohmann::json dino_records = nlohmann::json::array();
    int success_count = 0;
    int fail_count = 0;
    const int total = static_cast<int>(items.size());
    std::wstring first_fail_msg;

    for (const auto& item : items) {
        const std::string order_id = item.value("order_id", "");
        const std::string item_type = item.value("item_type", "shop");
        const std::string item_id = item.value("item_id", "");
        const int amount = item.value("amount", 1);
        const bool skip_kit_limit = item.value("skip_kit_limit", false);

        if (order_id.empty() || item_id.empty()) continue;

        bool ok = false;
        std::string detail;
        std::string fail_reason;
        nlohmann::json order_dinos = nlohmann::json::array();

        if (item_type == "kit") {
            ok = Store::GiveKit(controller, item_id, true, skip_kit_limit, &fail_reason,
                                &order_dinos);
            if (!ok && IsUnknownCatalogFailure(fail_reason) && TryReloadConfigForDelivery()) {
                fail_reason.clear();
                order_dinos = nlohmann::json::array();
                ok = Store::GiveKit(controller, item_id, true, skip_kit_limit, &fail_reason,
                                    &order_dinos);
                if (ok) detail = "GiveKit ok (after config reload)";
            }
            if (detail.empty())
                detail = ok ? "GiveKit ok" : ("GiveKit failed: " + fail_reason);
            Log::GetLog()->info("HttpClient: GiveKit '{}' for order {}: {} ({})",
                                item_id, order_id, ok ? "OK" : "FAIL", detail);
        } else {
            ok = Store::GiveItem(controller, item_id, amount, true, &fail_reason,
                                 &order_dinos);
            if (!ok && IsUnknownCatalogFailure(fail_reason) && TryReloadConfigForDelivery()) {
                fail_reason.clear();
                order_dinos = nlohmann::json::array();
                ok = Store::GiveItem(controller, item_id, amount, true, &fail_reason,
                                     &order_dinos);
                if (ok) detail = "GiveItem ok (after config reload)";
            }
            if (detail.empty())
                detail = ok ? "GiveItem ok" : ("GiveItem failed: " + fail_reason);
            Log::GetLog()->info("HttpClient: GiveItem '{}' x{} for order {}: {} ({})",
                                item_id, amount, order_id, ok ? "OK" : "FAIL", detail);
        }

        if (ok && order_dinos.is_array()) {
            for (auto& rec : order_dinos) {
                if (!rec.is_object()) continue;
                rec["order_id"] = order_id;
                rec["item_id"] = item_id;
                dino_records.push_back(rec);
            }
        }

        deliveries.push_back({
            {"order_id", order_id},
            {"item_id", item_id},
            {"item_type", item_type},
            {"amount", amount},
            {"ok", ok},
            {"trigger", "auto"},
            {"details", detail},
            {"fail_reason", ok ? "" : fail_reason},
        });

        if (ok) {
            ShopPoints::Get().LogTransaction(
                "web_deliver_pending", steam_id, "", item_id, amount, 0, 0);
            delivered_ids.push_back(order_id);
            success_count++;
            Log::GetLog()->info("HttpClient: delivered '{}' x{} for order {}",
                                item_id, amount, order_id);
        } else {
            failed_ids.push_back(order_id);
            fail_count++;
            if (first_fail_msg.empty()) {
                first_fail_msg = DeliveryFailureUserMessage(item_id, fail_reason);
            }
            Log::GetLog()->error("HttpClient: failed to deliver '{}' for order {} ({})",
                                 item_id, order_id, fail_reason);
            CustomShop::Debug::Fields df;
            df.steam_id = steam_id;
            df.order_id = order_id;
            df.extra = {{"item_id", item_id},
                        {"item_type", item_type},
                        {"fail_reason", fail_reason}};
            CustomShop::Debug::Error("Shop", df,
                                     "deliver failed: " + fail_reason);
        }
    }

    if (!failed_ids.empty()) {
        // Build errors[] from failed deliveries (fail_reason on each entry).
        nlohmann::json errors = nlohmann::json::array();
        for (const auto& d : deliveries) {
            if (!d.value("ok", true)) {
                const std::string fr = d.value("fail_reason", "");
                errors.push_back({
                    {"order_id", d.value("order_id", "")},
                    {"fail_reason", fr.empty() ? "delivery_failed" : fr},
                });
            }
        }
        nlohmann::json release_body = {
            {"steam_id", steam_id},
            {"order_ids", failed_ids},
            {"errors", errors},
        };
        const std::string release_url = g_web_url + "/api/pending/release";
        std::string release_resp = HttpPostJson(release_url, release_body.dump());
        Log::GetLog()->warn("HttpClient: released {} failed order(s): {}",
                            failed_ids.size(), release_resp);
    }

    if (success_count > 0) {
        std::wstring msg;
        if (fail_count > 0) {
            msg = L"[Shop] " + std::to_wstring(success_count) + L"/"
                + std::to_wstring(total) + L" resgate(s) entregue(s)";
        } else {
            msg = L"[Shop] " + std::to_wstring(success_count)
                + L" item(ns) da loja web entregue(s)!";
        }
        ArkApi::GetApiUtils().SendNotification(
            controller, FLinearColor(0, 1, 0, 1), 1.2f, 8.f, nullptr, msg.c_str());

        nlohmann::json body = {
            {"steam_id", steam_id},
            {"order_ids", delivered_ids},
            {"deliveries", deliveries},
        };
        if (!dino_records.empty())
            body["dino_records"] = dino_records;
        const std::string deliver_url = g_web_url + "/api/pending/delivered";
        std::string deliver_resp = HttpPostJson(deliver_url, body.dump());
        Log::GetLog()->info("HttpClient: mark delivered response: {}", deliver_resp);
    } else if (fail_count > 0) {
        std::wstring msg = first_fail_msg.empty()
            ? (L"[Shop] Falha ao entregar " + std::to_wstring(fail_count)
               + L" resgate(s). Contate um admin.")
            : first_fail_msg;
        if (fail_count > 1 && !first_fail_msg.empty()) {
            msg += L" (+" + std::to_wstring(fail_count - 1) + L" falha(s))";
        }
        ArkApi::GetApiUtils().SendNotification(
            controller, FLinearColor(1, 0.6f, 0, 1), 1.2f, 10.f, nullptr, msg.c_str());
    }

    return success_count > 0;
}

} // namespace HttpClient
} // namespace CustomShop
