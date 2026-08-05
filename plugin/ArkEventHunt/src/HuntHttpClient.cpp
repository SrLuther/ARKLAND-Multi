#include "pch.h"
#include "HuntHttpClient.h"

#include <winhttp.h>
#include <thread>

#pragma comment(lib, "winhttp.lib")

namespace {

HINTERNET g_session = nullptr;
std::mutex g_http_mu;

constexpr int kHttpResolveMs = 5000;
constexpr int kHttpConnectMs = 5000;
constexpr int kHttpSendMs = 8000;
constexpr int kHttpReceiveMs = 8000;

bool EnsureSession() {
    if (!g_session) {
        g_session = WinHttpOpen(
            L"ArkEventHunt/0.4",
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

void AddApiKeyHeader(HINTERNET hRequest) {
    if (ArkEventHunt::HttpClient::g_api_key.empty()) return;
    const auto& key = ArkEventHunt::HttpClient::g_api_key;
    std::wstring hdr = L"X-API-Key: " + std::wstring(key.begin(), key.end());
    WinHttpAddRequestHeaders(
        hRequest, hdr.c_str(), static_cast<DWORD>(hdr.size()),
        WINHTTP_ADDREQ_FLAG_ADD);
}

ArkEventHunt::HttpClient::Response DoRequestUnlocked(
    const wchar_t* method_w,
    const char* method_log,
    const std::string& full_url,
    const std::string* json_body) {
    ArkEventHunt::HttpClient::Response out;
    if (!EnsureSession()) return out;

    std::string host, path;
    int port = 80;
    bool secure = false;
    if (!ParseUrlParts(full_url, host, path, port, secure)) return out;

    std::wstring whost(host.begin(), host.end());
    std::wstring wpath(path.begin(), path.end());

    HINTERNET hConnect = WinHttpConnect(g_session, whost.c_str(),
                                        static_cast<INTERNET_PORT>(port), 0);
    if (!hConnect) {
        Log::GetLog()->warn("ArkEventHunt HTTP: connect failed host={}", host);
        return out;
    }

    DWORD flags = secure ? WINHTTP_FLAG_SECURE : 0;
    HINTERNET hRequest = WinHttpOpenRequest(
        hConnect, method_w, wpath.c_str(), nullptr, nullptr, nullptr, flags);
    if (!hRequest) {
        WinHttpCloseHandle(hConnect);
        return out;
    }

    if (json_body) {
        LPCWSTR content_type = L"Content-Type: application/json";
        WinHttpAddRequestHeaders(
            hRequest, content_type, static_cast<DWORD>(wcslen(content_type)),
            WINHTTP_ADDREQ_FLAG_ADD);
    }
    AddApiKeyHeader(hRequest);

    LPVOID body_ptr = json_body ? (LPVOID)json_body->c_str() : nullptr;
    DWORD body_len = json_body ? static_cast<DWORD>(json_body->size()) : 0;

    if (!WinHttpSendRequest(hRequest, nullptr, 0, body_ptr, body_len, body_len, 0) ||
        !WinHttpReceiveResponse(hRequest, nullptr)) {
        Log::GetLog()->warn(
            "ArkEventHunt HTTP: send/recv failed path={} err={}",
            path, GetLastError());
        WinHttpCloseHandle(hRequest);
        WinHttpCloseHandle(hConnect);
        return out;
    }

    DWORD status_code = 0;
    DWORD status_size = sizeof(status_code);
    WinHttpQueryHeaders(
        hRequest,
        WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER,
        WINHTTP_HEADER_NAME_BY_INDEX,
        &status_code,
        &status_size,
        WINHTTP_NO_HEADER_INDEX);
    out.status = static_cast<int>(status_code);
    out.body = ReadHttpBody(hRequest);

    if (out.status >= 400) {
        Log::GetLog()->warn(
            "ArkEventHunt HTTP: {} {} status={} body_len={}",
            method_log ? method_log : "?", path, out.status, out.body.size());
    }

    WinHttpCloseHandle(hRequest);
    WinHttpCloseHandle(hConnect);
    return out;
}

ArkEventHunt::HttpClient::Response DoRequest(
    const wchar_t* method_w,
    const char* method_log,
    const std::string& full_url,
    const std::string* json_body) {
    std::lock_guard<std::mutex> lock(g_http_mu);
    return DoRequestUnlocked(method_w, method_log, full_url, json_body);
}

bool ShouldRetryPost(const ArkEventHunt::HttpClient::Response& r) {
    if (r.status == 0) return true;
    if (r.status >= 500 && r.status <= 599) return true;
    if (r.status == 408 || r.status == 429) return true;
    return false;
}

} // anonymous

namespace ArkEventHunt {
namespace HttpClient {

std::string g_web_url = "http://127.0.0.1:5177";
std::string g_api_key;

void Configure(const std::string& web_url, const std::string& api_key) {
    g_web_url = web_url.empty() ? "http://127.0.0.1:5177" : web_url;
    while (!g_web_url.empty() && g_web_url.back() == '/')
        g_web_url.pop_back();
    g_api_key = api_key;
}

void Shutdown() {
    std::lock_guard<std::mutex> lock(g_http_mu);
    if (g_session) {
        WinHttpCloseHandle(g_session);
        g_session = nullptr;
    }
}

Response Get(const std::string& path) {
    return DoRequest(L"GET", "GET", g_web_url + path, nullptr);
}

Response PostJson(const std::string& path, const std::string& json_body) {
    return DoRequest(L"POST", "POST", g_web_url + path, &json_body);
}

Response PostJsonRetry(const std::string& path, const std::string& json_body,
                       int attempts) {
    if (attempts < 1) attempts = 1;
    Response last;
    for (int i = 0; i < attempts; ++i) {
        if (i > 0) {
            Log::GetLog()->warn(
                "ArkEventHunt HTTP: retrying POST {} (attempt {}/{})",
                path, i + 1, attempts);
            Sleep(static_cast<DWORD>(200 * i));
        }
        last = PostJson(path, json_body);
        if (!ShouldRetryPost(last))
            return last;
    }
    return last;
}

void PostJsonDetached(const std::string& path, const std::string& json_body,
                      int attempts) {
    std::thread([path, json_body, attempts]() {
        try {
            const auto resp = PostJsonRetry(path, json_body, attempts);
            Log::GetLog()->info(
                "ArkEventHunt HTTP detached POST {} status={}",
                path, resp.status);
        } catch (const std::exception& e) {
            Log::GetLog()->error(
                "ArkEventHunt HTTP detached POST {} exception: {}",
                path, e.what());
        } catch (...) {
            Log::GetLog()->error(
                "ArkEventHunt HTTP detached POST {} unknown exception", path);
        }
    }).detach();
}

} // namespace HttpClient
} // namespace ArkEventHunt
