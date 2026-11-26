#pragma once
#define WIN32_LEAN_AND_MEAN
#include <Windows.h>
#ifdef min
#undef min
#endif
#ifdef max
#undef max
#endif
#include <json.hpp>
#include <array>
#include <string>
#include <vector>
#include <unordered_map>
#include <memory>

namespace ChatArkland {
using Json = nlohmann::json;
std::wstring Wide(const std::string& text);
std::string Utf8(const std::wstring& text);
std::string NewId();
std::string CompactId();
std::string Escape(const std::string& text);
std::string Name(const std::string& text);
std::array<float,4> Color(const std::string& color);
void ValidateShared(const Json& config);
std::string Message(const Json& config, const std::string& key);

class WordFilter {
    struct Node { std::unordered_map<wchar_t, size_t> next; bool terminal = false; };
    std::vector<Node> nodes_{{}};
    std::wstring ignored_;
    bool enabled_ = false;
public:
    explicit WordFilter(const Json& config);
    std::string Apply(const std::string& text) const;
};

struct SharedState {
    Json config;
    Json players = Json::object();
    uint64_t revision = 0;
    bool observer = true;
    std::shared_ptr<const WordFilter> filter;
};
std::string LocalFormat(const SharedState& state, const Json& actor, const std::string& server_key, bool verified_network);
}
