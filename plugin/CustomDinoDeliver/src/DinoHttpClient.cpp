#include "pch.h"
#include "DinoHttpClient.h"
#include "DinoBridge.h"
#include "DinoConfig.h"
#include "DinoDeliver.h"
#include "DinoDebug.h"

#include <mutex>
#include <unordered_set>

namespace {

HINTERNET g_session = nullptr;
std::mutex g_deliver_mutex;
std::unordered_set<std::string> g_deliver_inflight;

// Evita hang longo no game thread (HangWatcher ASE) se a API não responder.
constexpr int kHttpResolveMs = 5000;
constexpr int kHttpConnectMs = 5000;
constexpr int kHttpSendMs = 8000;
constexpr int kHttpReceiveMs = 8000;

bool EnsureSession() {
    if (!g_session) {
        g_session = WinHttpOpen(
            L"CustomDinoDeliver/1.0",
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

bool ParseUrl(const std::string& url, std::string& host, std::string& path, int& port, bool& secure) {
    std::string remaining = url;
    port = 80;
    secure = false;

    if (remaining.find("http://") == 0) {
        remaining = remaining.substr(7);
    } else if (remaining.find("https://") == 0) {
        remaining = remaining.substr(8);
        secure = true;
        port = 443;
    } else {
        return false;
    }

    const auto slash_pos = remaining.find('/');
    const auto colon_pos = remaining.find(':');

    if (colon_pos != std::string::npos && (slash_pos == std::string::npos || colon_pos < slash_pos)) {
        host = remaining.substr(0, colon_pos);
        const auto port_end = slash_pos != std::string::npos ? slash_pos : remaining.size();
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

std::string HttpRequest(const wchar_t* method, const std::string& url, const std::string& json_body) {
    if (!EnsureSession()) return "";

    std::string host, path;
    int port = 80;
    bool secure = false;
    if (!ParseUrl(url, host, path, port, secure))
        return "";

    const std::wstring whost(host.begin(), host.end());
    const std::wstring wpath(path.begin(), path.end());

    HINTERNET hConnect = WinHttpConnect(g_session, whost.c_str(), static_cast<INTERNET_PORT>(port), 0);
    if (!hConnect) return "";

    const DWORD request_flags = secure ? WINHTTP_FLAG_SECURE : 0;
    HINTERNET hRequest = WinHttpOpenRequest(
        hConnect, method, wpath.c_str(), nullptr, nullptr, nullptr, request_flags);
    if (!hRequest) {
        WinHttpCloseHandle(hConnect);
        return "";
    }

    if (!json_body.empty()) {
        LPCWSTR content_type = L"Content-Type: application/json";
        WinHttpAddRequestHeaders(
            hRequest, content_type, static_cast<DWORD>(wcslen(content_type)),
            WINHTTP_ADDREQ_FLAG_ADD);
    }

  if (!CustomDinoDeliver::HttpClient::g_api_key.empty()) {
        const auto& key = CustomDinoDeliver::HttpClient::g_api_key;
        const std::wstring api_key_hdr = L"X-API-Key: " + std::wstring(key.begin(), key.end());
        WinHttpAddRequestHeaders(
            hRequest, api_key_hdr.c_str(), static_cast<DWORD>(wcslen(api_key_hdr.c_str())),
            WINHTTP_ADDREQ_FLAG_ADD);
    }

    std::string result;
    const BOOL sent = json_body.empty()
        ? WinHttpSendRequest(hRequest, nullptr, 0, nullptr, 0, 0, 0)
        : WinHttpSendRequest(
              hRequest, nullptr, 0,
              const_cast<LPVOID>(static_cast<LPCVOID>(json_body.data())),
              static_cast<DWORD>(json_body.size()),
              static_cast<DWORD>(json_body.size()), 0);

    if (sent && WinHttpReceiveResponse(hRequest, nullptr)) {
        DWORD status_code = 0;
        DWORD status_size = sizeof(status_code);
        if (WinHttpQueryHeaders(
                hRequest,
                WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER,
                WINHTTP_HEADER_NAME_BY_INDEX,
                &status_code,
                &status_size,
                WINHTTP_NO_HEADER_INDEX)) {
            // Evita recursão no ingest de debug.
            const bool is_debug_ingest =
                path.find("/api/plugin-debug/") != std::string::npos;
            if (status_code >= 400 && !is_debug_ingest) {
                Log::GetLog()->warn(
                    "DinoHttpClient: HTTP {} path={}", status_code, path);
                CustomDinoDeliver::Debug::Fields hf;
                hf.extra = {{"http_status", static_cast<int>(status_code)},
                            {"path", path}};
                CustomDinoDeliver::Debug::Warn(
                    "Http", hf, "HTTP " + std::to_string(status_code));
            }
        }
        DWORD bytes_avail = 0;
        DWORD bytes_read = 0;
        char buf[4096];
        while (WinHttpQueryDataAvailable(hRequest, &bytes_avail) && bytes_avail > 0) {
            while (bytes_avail > 0) {
                const DWORD to_read = (bytes_avail > sizeof(buf)) ? static_cast<DWORD>(sizeof(buf)) : bytes_avail;
                if (WinHttpReadData(hRequest, buf, to_read, &bytes_read) && bytes_read > 0) {
                    result.append(buf, bytes_read);
                    bytes_avail -= bytes_read;
                } else {
                    break;
                }
            }
        }
    } else {
        const bool is_debug_ingest =
            path.find("/api/plugin-debug/") != std::string::npos;
        if (!is_debug_ingest) {
            CustomDinoDeliver::Debug::Fields hf;
            hf.extra = {{"path", path}, {"timeout_ms", kHttpSendMs}};
            CustomDinoDeliver::Debug::Warn("Http", hf, "WinHTTP send/receive failed");
        }
    }

    WinHttpCloseHandle(hRequest);
    WinHttpCloseHandle(hConnect);
    return result;
}

bool TryParseApiJson(const std::string& body, nlohmann::json& out, const char* context) {
    if (body.empty()) {
        Log::GetLog()->debug("DinoHttpClient: {} empty response", context);
        return false;
    }
    try {
        out = nlohmann::json::parse(body);
        return true;
    } catch (const std::exception& e) {
        Log::GetLog()->error("DinoHttpClient: {} JSON parse error: {}", context, e.what());
        return false;
    }
}

void PostReleaseFailed(const std::string& steam_id, const std::vector<std::string>& failed_ids) {
    if (failed_ids.empty()) return;

    nlohmann::json release_body = {
        {"steam_id", steam_id},
        {"order_ids", failed_ids},
    };
    const std::string release_url =
        CustomDinoDeliver::HttpClient::g_web_url + "/api/pending/custom-dino/release";
    const std::string release_resp =
        HttpRequest(L"POST", release_url, release_body.dump());
    Log::GetLog()->warn("DinoHttpClient: released {} failed order(s): {}",
                        failed_ids.size(), release_resp);
}

void PostDeliveredCallback(const std::string& steam_id,
                           const std::vector<std::string>& delivered_ids,
                           const nlohmann::json& failures,
                           const nlohmann::json& dino_records) {
    nlohmann::json body = {
        {"steam_id", steam_id},
        {"order_ids", delivered_ids},
        {"failures", failures},
    };
    if (!dino_records.empty())
        body["dino_records"] = dino_records;
    const std::string deliver_url =
        CustomDinoDeliver::HttpClient::g_web_url + "/api/pending/custom-dino/delivered";
    const std::string deliver_resp = HttpRequest(L"POST", deliver_url, body.dump());
    Log::GetLog()->info("DinoHttpClient: delivered callback: {}", deliver_resp);
}

class DeliverInflightGuard {
public:
    explicit DeliverInflightGuard(std::string steam_id)
        : steam_id_(std::move(steam_id)), active_(!steam_id_.empty()) {}

    DeliverInflightGuard(const DeliverInflightGuard&) = delete;
    DeliverInflightGuard& operator=(const DeliverInflightGuard&) = delete;

    bool Acquire() {
        if (!active_) return false;
        std::lock_guard<std::mutex> lock(g_deliver_mutex);
        if (!g_deliver_inflight.insert(steam_id_).second) {
            active_ = false;
            return false;
        }
        return true;
    }

    ~DeliverInflightGuard() {
        if (!active_) return;
        std::lock_guard<std::mutex> lock(g_deliver_mutex);
        g_deliver_inflight.erase(steam_id_);
    }

private:
    std::string steam_id_;
    bool active_ = false;
};

} // anonymous namespace

namespace CustomDinoDeliver {
namespace HttpClient {

std::string g_web_url = "http://127.0.0.1:5177";
std::string g_api_key = "";

void Configure(const std::string& web_url, const std::string& api_key) {
    g_web_url = web_url;
    g_api_key = api_key;
    CustomDinoDeliver::Debug::SetIngestCallback([](const std::string& json_body) {
        if (g_web_url.empty() || json_body.empty()) return;
        // Fire-and-forget; falhas não reentram no debug logger.
        HttpRequest(L"POST", g_web_url + "/api/plugin-debug/ingest", json_body);
    });
    Log::GetLog()->info("DinoHttpClient: configured url='{}' api_key_set={}",
                        web_url, !api_key.empty());
}

void Shutdown() {
    CustomDinoDeliver::Debug::SetIngestCallback(nullptr);
    if (g_session) {
        WinHttpCloseHandle(g_session);
        g_session = nullptr;
    }
}

DeliverResult DeliverPending(AShooterPlayerController* controller) {
    DeliverResult result;

    if (!controller) return result;
    if (ArkApi::GetApiUtils().GetStatus() != ArkApi::ServerStatus::Ready) {
        Log::GetLog()->warn("DinoHttpClient: DeliverPending skipped — server not ready");
        result.api_ok = false;
        return result;
    }

    const std::string steam_id = Bridge::GetSteamId(controller);
    if (steam_id.empty()) {
        Log::GetLog()->warn("DinoHttpClient: DeliverPending skipped — empty steam_id");
        result.api_ok = false;
        return result;
    }

    DeliverInflightGuard inflight(steam_id);
    if (!inflight.Acquire()) {
        Log::GetLog()->warn("DinoHttpClient: deliver already in progress for '{}'", steam_id);
        result.already_in_progress = true;
        return result;
    }

    Log::GetLog()->info("DinoHttpClient: claim custom-dino for '{}' at {}", steam_id, g_web_url);

    const std::string claim_url = g_web_url + "/api/pending/custom-dino/claim";
    const std::string claim_body = nlohmann::json{{"steam_id", steam_id}}.dump();
    const std::string claim_resp = HttpRequest(L"POST", claim_url, claim_body);

    nlohmann::json json;
    if (!TryParseApiJson(claim_resp, json, "claim")) {
        Log::GetLog()->error("DinoHttpClient: claim failed for '{}' (empty or invalid response)",
                             steam_id);
        result.api_ok = false;
        return result;
    }

    if (!json.value("ok", false)) {
        Log::GetLog()->warn("DinoHttpClient: claim not ok: {}", claim_resp);
        result.api_ok = false;
        return result;
    }

    nlohmann::json items = json.contains("items")
        ? json["items"]
        : json.value("orders", nlohmann::json::array());

    if (!items.is_array() || items.empty()) {
        Log::GetLog()->debug("DinoHttpClient: no pending custom dino orders for '{}'", steam_id);
        return result;
    }

    result.claimed = static_cast<int>(items.size());
    Log::GetLog()->info("DinoHttpClient: claimed {} custom dino order(s) for '{}'",
                        result.claimed, steam_id);

    std::vector<std::string> delivered_ids;
    std::vector<std::string> failed_ids;
    nlohmann::json failures = nlohmann::json::array();
    nlohmann::json dino_records = nlohmann::json::array();

    for (const auto& item : items) {
        const std::string order_id = item.value("order_id", "");
        nlohmann::json payload = item.contains("payload") && item["payload"].is_object()
            ? item["payload"]
            : nlohmann::json::object();

        if (order_id.empty() || payload.empty()) {
            if (!order_id.empty()) {
                failed_ids.push_back(order_id);
                result.failed++;
                failures.push_back({
                    {"order_id", order_id},
                    {"error", payload.empty() ? "empty_payload" : "invalid_order"},
                });
                Log::GetLog()->error("DinoHttpClient: order {} skipped — invalid payload", order_id);
            }
            continue;
        }

        const std::string species = JsonStr(payload, "species_display_name",
            JsonStr(payload, "species_blueprint", "unknown"));
        Log::GetLog()->info("DinoHttpClient: delivering order {} ({})", order_id, species);

        bool ok = false;
        std::string error = "dino_delivery_failed";
        CustomDinoDeliver::DeliverCustomDinoResult deliver_result;
        try {
            deliver_result = DeliverCustomDino(controller, payload);
            ok = deliver_result.ok;
        } catch (const std::exception& e) {
            error = std::string("exception: ") + e.what();
            Log::GetLog()->error("DinoHttpClient: order {} exception — {}", order_id, e.what());
        } catch (...) {
            error = "unknown_exception";
            Log::GetLog()->error("DinoHttpClient: order {} unknown exception", order_id);
        }

        if (ok) {
            delivered_ids.push_back(order_id);
            result.delivered++;
            dino_records.push_back({
                {"order_id", order_id},
                {"dino_id1", deliver_result.identity.dino_id1},
                {"dino_id2", deliver_result.identity.dino_id2},
                {"ancestors", deliver_result.identity.ancestors},
            });
            Log::GetLog()->info(
                "[DinoLabDeliver] delivered order {} id1={} id2={} ancestors={}",
                order_id,
                deliver_result.identity.dino_id1,
                deliver_result.identity.dino_id2,
                deliver_result.identity.ancestors.size());
        } else {
            if (!deliver_result.failure_reason.empty())
                error = deliver_result.failure_reason;
            failed_ids.push_back(order_id);
            result.failed++;
            failures.push_back({
                {"order_id", order_id},
                {"error", error},
            });
            Log::GetLog()->error("DinoHttpClient: failed order {} ({})", order_id, error);
        }
    }

    if (!failed_ids.empty())
        PostReleaseFailed(steam_id, failed_ids);

    if (!delivered_ids.empty() || !failures.empty())
        PostDeliveredCallback(steam_id, delivered_ids, failures, dino_records);

    if (controller && (result.delivered > 0 || result.failed > 0)) {
        if (result.delivered > 0) {
            std::wstring msg = L"[Dino Lab] " + std::to_wstring(result.delivered)
                + L" dino(s) customizado(s) entregue(s)!";
            if (result.failed > 0) {
                msg += L" (" + std::to_wstring(result.failed) + L" falha(s))";
            }
            ArkApi::GetApiUtils().SendNotification(
                controller, FLinearColor(0, 1, 0, 1), 1.2f, 8.f, nullptr, msg.c_str());
        } else {
            ArkApi::GetApiUtils().SendNotification(
                controller, FLinearColor(1, 0.6f, 0, 1), 1.2f, 10.f, nullptr,
                L"[Dino Lab] Falha ao entregar dino customizado. Contate um admin.");
        }
    }

    return result;
}

} // namespace HttpClient
} // namespace CustomDinoDeliver
