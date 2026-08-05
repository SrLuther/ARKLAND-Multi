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
#include <mutex>
#include <thread>
#include <optional>

#include <json.hpp>

inline int64_t JsonInt64(const nlohmann::json& j, const char* key,
                         int64_t fallback = 0) {
    if (!j.contains(key)) return fallback;
    const auto& v = j.at(key);
    if (v.is_number_integer()) return v.get<int64_t>();
    if (v.is_number()) return static_cast<int64_t>(v.get<double>());
    if (v.is_string()) {
        try {
            return static_cast<int64_t>(std::stoll(v.get<std::string>()));
        } catch (...) {
            return fallback;
        }
    }
    return fallback;
}

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

inline float JsonFloat(const nlohmann::json& j, const char* key, float fallback = 0.f) {
    if (!j.contains(key)) return fallback;
    const auto& v = j.at(key);
    if (v.is_number()) return static_cast<float>(v.get<double>());
    if (v.is_string()) {
        try {
            return static_cast<float>(std::stof(v.get<std::string>()));
        } catch (...) {
            return fallback;
        }
    }
    return fallback;
}
