#include "pch.h"
#include "DinoHttpClient.h"
#include "DinoBridge.h"
#include "DinoConfig.h"
#include "DinoDeliver.h"

namespace {

HINTERNET g_session = nullptr;

bool EnsureSession() {
    if (!g_session) {
        g_session = WinHttpOpen(
            L"CustomDinoDeliver/1.0",
            WINHTTP_ACCESS_TYPE_DEFAULT_PROXY,
            nullptr, nullptr, 0);
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

} // anonymous namespace

namespace CustomDinoDeliver {
namespace HttpClient {

std::string g_web_url = "http://127.0.0.1:5177";
std::string g_api_key = "";

void Configure(const std::string& web_url, const std::string& api_key) {
    g_web_url = web_url;
    g_api_key = api_key;
    Log::GetLog()->info("DinoHttpClient: configured url='{}' api_key_set={}",
                        web_url, !api_key.empty());
}

void Shutdown() {
    if (g_session) {
        WinHttpCloseHandle(g_session);
        g_session = nullptr;
    }
}

bool DeliverPending(AShooterPlayerController* controller) {
    if (!controller) return false;

    const std::string steam_id = Bridge::GetSteamId(controller);
    if (steam_id.empty()) return false;

    Log::GetLog()->info("DinoHttpClient: claim custom-dino for '{}' at {}", steam_id, g_web_url);

    const std::string claim_url = g_web_url + "/api/pending/custom-dino/claim";
    const std::string claim_body = nlohmann::json{{"steam_id", steam_id}}.dump();
    const std::string claim_resp = HttpRequest(L"POST", claim_url, claim_body);

    nlohmann::json json;
    if (!TryParseApiJson(claim_resp, json, "claim")) {
        return claim_resp.empty();
    }

    if (!json.value("ok", false)) {
        Log::GetLog()->warn("DinoHttpClient: claim not ok: {}", claim_resp);
        return false;
    }

    nlohmann::json items = json.contains("items")
        ? json["items"]
        : json.value("orders", nlohmann::json::array());

    if (!items.is_array() || items.empty()) {
        return true;
    }

    Log::GetLog()->info("DinoHttpClient: claimed {} custom dino order(s) for '{}'",
                        items.size(), steam_id);

    std::vector<std::string> delivered_ids;
    std::vector<std::string> failed_ids;
    nlohmann::json failures = nlohmann::json::array();
    int success_count = 0;
    int fail_count = 0;

    for (const auto& item : items) {
        const std::string order_id = item.value("order_id", "");
        nlohmann::json payload = item.contains("payload") && item["payload"].is_object()
            ? item["payload"]
            : nlohmann::json::object();

        if (order_id.empty() || payload.empty()) {
            if (!order_id.empty())
                failed_ids.push_back(order_id);
            continue;
        }

        const bool ok = DeliverCustomDino(controller, payload);
        if (ok) {
            delivered_ids.push_back(order_id);
            success_count++;
            Log::GetLog()->info("DinoHttpClient: delivered order {}", order_id);
        } else {
            failed_ids.push_back(order_id);
            failures.push_back({
                {"order_id", order_id},
                {"error", "dino_delivery_failed"},
            });
            fail_count++;
            Log::GetLog()->error("DinoHttpClient: failed order {}", order_id);
        }
    }

    if (!failed_ids.empty()) {
        nlohmann::json release_body = {
            {"steam_id", steam_id},
            {"order_ids", failed_ids},
        };
        const std::string release_url = g_web_url + "/api/pending/custom-dino/release";
        const std::string release_resp =
            HttpRequest(L"POST", release_url, release_body.dump());
        Log::GetLog()->warn("DinoHttpClient: released {} failed order(s): {}",
                            failed_ids.size(), release_resp);
    }

    if (success_count > 0 || fail_count > 0) {
        nlohmann::json body = {
            {"steam_id", steam_id},
            {"order_ids", delivered_ids},
            {"failures", failures},
        };
        const std::string deliver_url = g_web_url + "/api/pending/custom-dino/delivered";
        const std::string deliver_resp = HttpRequest(L"POST", deliver_url, body.dump());
        Log::GetLog()->info("DinoHttpClient: delivered callback: {}", deliver_resp);
    }

    if (success_count > 0) {
        std::wstring msg = L"[Dino Lab] " + std::to_wstring(success_count)
            + L" dino(s) customizado(s) entregue(s)!";
        ArkApi::GetApiUtils().SendNotification(
            controller, FLinearColor(0, 1, 0, 1), 1.2f, 8.f, nullptr, msg.c_str());
    } else if (fail_count > 0) {
        ArkApi::GetApiUtils().SendNotification(
            controller, FLinearColor(1, 0.6f, 0, 1), 1.2f, 10.f, nullptr,
            L"[Dino Lab] Falha ao entregar dino customizado. Contate um admin.");
    }

    return success_count > 0;
}

} // namespace HttpClient
} // namespace CustomDinoDeliver
