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

inline std::string JsonStr(const nlohmann::json& j,
                           const char* key,
                           const std::string& fallback = "") {
    if (!j.contains(key)) return fallback;
    const auto& v = j.at(key);
    if (v.is_null()) return fallback;
    if (v.is_string()) return v.get<std::string>();
    return fallback;
}
