#pragma once

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
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <algorithm>
#include <cstdint>

#include <json.hpp>
#include <winhttp.h>
