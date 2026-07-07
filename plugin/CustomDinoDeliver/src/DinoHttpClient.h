#pragma once

#include "pch.h"

namespace CustomDinoDeliver {
namespace HttpClient {

extern std::string g_web_url;
extern std::string g_api_key;

struct DeliverResult {
    int claimed = 0;
    int delivered = 0;
    int failed = 0;
    bool api_ok = true;
    bool already_in_progress = false;
};

void Configure(const std::string& web_url, const std::string& api_key);
void Shutdown();
DeliverResult DeliverPending(AShooterPlayerController* controller);

} // namespace HttpClient
} // namespace CustomDinoDeliver
