#pragma once

// ArkApi ASE v3 headers must come BEFORE Windows.h
#include <API/ARK/Ark.h>

// nlohmann/json bundled with ArkApi SDK (no subdirectory)
#include <json.hpp>

#define WIN32_LEAN_AND_MEAN
#include <Windows.h>

#include <string>
#include <sstream>
#include <fstream>
#include <iomanip>
#include <algorithm>
