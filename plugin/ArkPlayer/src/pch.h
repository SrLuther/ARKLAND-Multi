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
#include <map>
#include <unordered_map>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <algorithm>
#include <cstdint>
#include <chrono>
#include <cctype>
#include <tlhelp32.h>

#include <json.hpp>

inline std::string JsonStr(const nlohmann::json& j,
                           const char* key,
                           const std::string& fallback = "") {
    if (!j.contains(key)) return fallback;
    const auto& v = j.at(key);
    if (v.is_null()) return fallback;
    if (v.is_string()) return v.get<std::string>();
    return fallback;
}

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
