#include "pch.h"
#include "HttpClient.h"
#include "ShopBridge.h"
#include "ShopConfig.h"
#include "ShopStore.h"
#include "ShopPoints.h"

namespace {

// ── WinHTTP helpers ──────────────────────────────────────────────

HINTERNET g_session = nullptr;

bool EnsureSession() {
    if (!g_session) {
        g_session = WinHttpOpen(
            L"CustomShop/1.0",
            WINHTTP_ACCESS_TYPE_DEFAULT_PROXY,
            nullptr, nullptr, 0);
    }
    return g_session != nullptr;
}

// Simple blocking HTTP GET, returns response body or empty string on failure.
std::string HttpGet(const std::string& url) {
    if (!EnsureSession()) return "";

    // Parse URL into components (supports http and https)
    std::string host, path;
    int port = 80;
    bool secure = false;
    std::string remaining = url;

    if (remaining.find("http://") == 0) {
        remaining = remaining.substr(7);
        secure = false;
    } else if (remaining.find("https://") == 0) {
        remaining = remaining.substr(8);
        secure = true;
        port = 443;
    }

    // Split host:port/path
    auto slash_pos = remaining.find('/');
    auto colon_pos = remaining.find(':');

    if (colon_pos != std::string::npos && colon_pos < slash_pos) {
        host = remaining.substr(0, colon_pos);
        auto port_end = slash_pos != std::string::npos ? slash_pos : remaining.size();
        try { port = std::stoi(remaining.substr(colon_pos + 1, port_end - colon_pos - 1)); }
        catch (...) { port = secure ? 443 : 80; }
    } else {
        auto end = slash_pos != std::string::npos ? slash_pos : remaining.size();
        host = remaining.substr(0, end);
    }
    path = (slash_pos != std::string::npos) ? remaining.substr(slash_pos) : "/";

    // Connect
    std::wstring whost(host.begin(), host.end());
    std::wstring wpath(path.begin(), path.end());

    HINTERNET hConnect = WinHttpConnect(g_session, whost.c_str(), (INTERNET_PORT)port, 0);
    if (!hConnect) return "";

    DWORD request_flags = secure ? WINHTTP_FLAG_SECURE : 0;
    HINTERNET hRequest = WinHttpOpenRequest(hConnect, L"GET", wpath.c_str(),
                                             nullptr, nullptr, nullptr, request_flags);
    if (!hRequest) {
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
        WinHttpReceiveResponse(hRequest, nullptr);
        DWORD bytes_avail = 0, bytes_read = 0;
        char buf[4096];
        while (WinHttpQueryDataAvailable(hRequest, &bytes_avail) && bytes_avail > 0) {
            while (bytes_avail > 0) {
                DWORD to_read = (bytes_avail > sizeof(buf)) ? (DWORD)sizeof(buf) : bytes_avail;
                if (WinHttpReadData(hRequest, buf, to_read, &bytes_read) && bytes_read > 0) {
                    result.append(buf, bytes_read);
                    bytes_avail -= bytes_read;
                } else break;
            }
        }
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
    std::string remaining = url;
    bool secure = false;

    if (remaining.find("http://") == 0) {
        remaining = remaining.substr(7);
        secure = false;
    } else if (remaining.find("https://") == 0) {
        remaining = remaining.substr(8);
        secure = true;
        port = 443;
    }

    auto slash_pos = remaining.find('/');
    auto colon_pos = remaining.find(':');

    if (colon_pos != std::string::npos && colon_pos < slash_pos) {
        host = remaining.substr(0, colon_pos);
        auto port_end = slash_pos != std::string::npos ? slash_pos : remaining.size();
        try { port = std::stoi(remaining.substr(colon_pos + 1, port_end - colon_pos - 1)); }
        catch (...) { port = secure ? 443 : 80; }
    } else {
        auto end = slash_pos != std::string::npos ? slash_pos : remaining.size();
        host = remaining.substr(0, end);
    }
    path = (slash_pos != std::string::npos) ? remaining.substr(slash_pos) : "/";

    std::wstring whost(host.begin(), host.end());
    std::wstring wpath(path.begin(), path.end());

    HINTERNET hConnect = WinHttpConnect(g_session, whost.c_str(), (INTERNET_PORT)port, 0);
    if (!hConnect) return "";

    DWORD request_flags = secure ? WINHTTP_FLAG_SECURE : 0;
    HINTERNET hRequest = WinHttpOpenRequest(hConnect, L"POST", wpath.c_str(),
                                             nullptr, nullptr, nullptr, request_flags);
    if (!hRequest) {
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
        WinHttpReceiveResponse(hRequest, nullptr);
        DWORD bytes_avail = 0, bytes_read = 0;
        char buf[4096];
        while (WinHttpQueryDataAvailable(hRequest, &bytes_avail) && bytes_avail > 0) {
            while (bytes_avail > 0) {
                DWORD to_read = (bytes_avail > sizeof(buf)) ? (DWORD)sizeof(buf) : bytes_avail;
                if (WinHttpReadData(hRequest, buf, to_read, &bytes_read) && bytes_read > 0) {
                    result.append(buf, bytes_read);
                    bytes_avail -= bytes_read;
                } else break;
            }
        }
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

bool TryReloadConfigForDelivery() {
    try {
        CustomShop::ShopConfig::Get().Load();
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
    try {
        json = nlohmann::json::parse(claim_resp);
    } catch (const std::exception& e) {
        Log::GetLog()->error("HttpClient: claim JSON parse error: {}", e.what());
        return false;
    }

    if (!json.value("ok", false)) {
        Log::GetLog()->warn("HttpClient: claim API returned not ok: {}", claim_resp);
        if (claim_resp.empty()) {
            ArkApi::GetApiUtils().SendNotification(
                controller, FLinearColor(1, 0.4f, 0, 1), 1.2f, 6.f, nullptr,
                L"[Shop] Servico de entrega indisponivel");
        }
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

        if (item_type == "kit") {
            ok = Store::GiveKit(controller, item_id, true, skip_kit_limit, &fail_reason);
            if (!ok && IsUnknownCatalogFailure(fail_reason) && TryReloadConfigForDelivery()) {
                fail_reason.clear();
                ok = Store::GiveKit(controller, item_id, true, skip_kit_limit, &fail_reason);
                if (ok) detail = "GiveKit ok (after config reload)";
            }
            if (detail.empty())
                detail = ok ? "GiveKit ok" : ("GiveKit failed: " + fail_reason);
            Log::GetLog()->info("HttpClient: GiveKit '{}' for order {}: {} ({})",
                                item_id, order_id, ok ? "OK" : "FAIL", detail);
        } else {
            ok = Store::GiveItem(controller, item_id, amount, true, &fail_reason);
            if (!ok && IsUnknownCatalogFailure(fail_reason) && TryReloadConfigForDelivery()) {
                fail_reason.clear();
                ok = Store::GiveItem(controller, item_id, amount, true, &fail_reason);
                if (ok) detail = "GiveItem ok (after config reload)";
            }
            if (detail.empty())
                detail = ok ? "GiveItem ok" : ("GiveItem failed: " + fail_reason);
            Log::GetLog()->info("HttpClient: GiveItem '{}' x{} for order {}: {} ({})",
                                item_id, amount, order_id, ok ? "OK" : "FAIL", detail);
        }

        deliveries.push_back({
            {"order_id", order_id},
            {"item_id", item_id},
            {"item_type", item_type},
            {"amount", amount},
            {"ok", ok},
            {"trigger", "auto"},
            {"details", detail},
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
        }
    }

    if (!failed_ids.empty()) {
        nlohmann::json release_body = {
            {"steam_id", steam_id},
            {"order_ids", failed_ids},
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
