#pragma once

#include "pch.h"

namespace ArkEventHunt {
namespace HttpClient {

struct Response {
    int status = 0;
    std::string body;
    bool ok() const { return status >= 200 && status < 300 && !body.empty(); }
};

void Configure(const std::string& web_url, const std::string& api_key);
void Shutdown();

Response Get(const std::string& path);
Response PostJson(const std::string& path, const std::string& json_body);

// Retry em falhas de rede / 5xx (padrão CustomShop Delivered ACK).
Response PostJsonRetry(const std::string& path, const std::string& json_body,
                       int attempts = 3);

// Fire-and-forget em thread (não bloqueia game thread). Best-effort.
void PostJsonDetached(const std::string& path, const std::string& json_body,
                      int attempts = 3);

extern std::string g_web_url;
extern std::string g_api_key;

} // namespace HttpClient
} // namespace ArkEventHunt
