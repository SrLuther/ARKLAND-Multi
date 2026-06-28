#pragma once

#include "pch.h"

namespace CustomShop {
namespace CrossChat {

void SetDb(MYSQL* db);
void Start();
void Stop();
void OnConfigReload();

} // namespace CrossChat
} // namespace CustomShop
