#pragma once

// ArkApi ASE v3 headers must come BEFORE Windows.h to avoid TCHAR redefinition
#include <API/ARK/Ark.h>

#define WIN32_LEAN_AND_MEAN
#include <Windows.h>

#include <string>
#include <vector>
#include <memory>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <algorithm>
#include <cctype>
#include <cstdint>

// nlohmann/json bundled with ArkApi SDK (no subdirectory)
#include <json.hpp>

// MySQL C Connector (via vcpkg libmysql)
#include <mysql.h>
