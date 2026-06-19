#pragma once

// ArkApi ASE v3 headers must come BEFORE Windows.h to avoid TCHAR redefinition
#include <API/ARK/Ark.h>

#define WIN32_LEAN_AND_MEAN
#include <Windows.h>

#ifdef min
#undef min
#endif
#ifdef max
#undef max
#endif

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

// MariaDB Connector/C (linkado via libmariadb.lib em mariadb/lib/)
#include "../mariadb/include/mysql.h"

// WinHTTP for HTTP communication with arkshop_web
#include <winhttp.h>
