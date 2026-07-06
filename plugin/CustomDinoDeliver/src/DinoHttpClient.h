#pragma once

#include "pch.h"

namespace CustomDinoDeliver {
namespace HttpClient {

extern std::string g_web_url;
extern std::string g_api_key;

void Configure(const std::string& web_url, const std::string& api_key);
void Shutdown();
bool DeliverPending(AShooterPlayerController* controller);

} // namespace HttpClient
} // namespace CustomDinoDeliver
