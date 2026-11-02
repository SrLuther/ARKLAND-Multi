#pragma once

#include <API/ARK/Ark.h>
#define WIN32_LEAN_AND_MEAN
#include <Windows.h>
#include <winhttp.h>
#ifdef min
#undef min
#endif
#ifdef max
#undef max
#endif
#include <json.hpp>
#include <algorithm>
#include <array>
#include <cctype>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <map>
#include <mutex>
#include <set>
#include <sstream>
#include <string>
#include <tuple>
#include <thread>
#include <unordered_map>
#include <vector>

inline std::string FRJsonString(const nlohmann::json& j, const char* key,
                                const std::string& fallback = {}) {
    return j.contains(key) && j[key].is_string()
        ? j[key].get<std::string>() : fallback;
}
inline int FRJsonInt(const nlohmann::json& j, const char* key, int fallback) {
    return j.contains(key) && j[key].is_number_integer()
        ? j[key].get<int>() : fallback;
}
inline bool FRJsonBool(const nlohmann::json& j, const char* key, bool fallback) {
    return j.contains(key) && j[key].is_boolean()
        ? j[key].get<bool>() : fallback;
}
