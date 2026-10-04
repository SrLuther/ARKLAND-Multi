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

#include <cctype>
#include <cstdint>
#include <fstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include <json.hpp>

inline int JsonInt(const nlohmann::json& j, const char* key, int fallback = 0) {
    if (!j.contains(key)) return fallback;
    const auto& v = j.at(key);
    if (v.is_number_integer()) return v.get<int>();
    if (v.is_number()) return static_cast<int>(v.get<double>());
    return fallback;
}

inline bool JsonBool(const nlohmann::json& j, const char* key, bool fallback = false) {
    if (!j.contains(key)) return fallback;
    const auto& v = j.at(key);
    if (v.is_boolean()) return v.get<bool>();
    return fallback;
}
