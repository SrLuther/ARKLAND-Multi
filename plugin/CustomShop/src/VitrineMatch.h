#pragma once

#include <cctype>
#include <string>

// Comparacao pura de blueprint da Vitrine (sem ArkApi).
// Casa se o path canonico for igual OU se o nome curto da classe (sem _C) for igual.
// Stack, quantidade, peso e preco nao entram aqui.
// A mesma regra esta em plugin/arkshop_web/vitrine_match.py.

namespace CustomShop {
namespace VitrineMatch {

struct Identity {
    std::string path;
    std::string key;
    std::string short_key;
};

inline std::string ToLower(std::string s) {
    for (char& ch : s)
        ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
    return s;
}

inline void StripClassSuffix(std::string& name) {
    if (name.size() > 2 && name[name.size() - 2] == '_'
        && (name.back() == 'C' || name.back() == 'c'))
        name.resize(name.size() - 2);
}

inline std::string ShortToken(std::string s) {
    if (s.empty() || s.size() > 400) return {};
    const auto sp = s.find_last_of(" \t");
    if (sp != std::string::npos) s = s.substr(sp + 1);
    while (!s.empty() && (s.back() == '\'' || s.back() == '"')) s.pop_back();
    while (!s.empty() && (s.front() == '\'' || s.front() == '"')) s.erase(s.begin());
    const auto slash = s.rfind('/');
    if (slash != std::string::npos) s = s.substr(slash + 1);
    const auto dot = s.rfind('.');
    if (dot != std::string::npos && dot + 1 < s.size()) s = s.substr(dot + 1);
    if (s.size() > 9 && s.compare(0, 9, "Default__") == 0) s = s.substr(9);
    StripClassSuffix(s);
    for (char& ch : s)
        ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
    if (s.size() < 8 || s.size() > 80 || s.find('_') == std::string::npos) return {};
    for (unsigned char ch : s) {
        if (!(std::isalnum(ch) || ch == '_')) return {};
    }
    return s;
}

inline Identity Identify(const std::string& raw) {
    Identity id;
    if (raw.empty() || raw.size() > 400) return id;

    size_t pos = std::string::npos;
    for (const char* root : {"/Game/", "/Script/", "/Engine/"}) {
        const size_t p = raw.find(root);
        if (p != std::string::npos && (pos == std::string::npos || p < pos))
            pos = p;
    }
    if (pos != std::string::npos) {
        size_t end = pos;
        while (end < raw.size()) {
            const unsigned char ch = static_cast<unsigned char>(raw[end]);
            if (std::isalnum(ch) || ch == '_' || ch == '.' || ch == '/' || ch == '-')
                ++end;
            else
                break;
        }
        std::string path = raw.substr(pos, end - pos);
        while (!path.empty() && (path.back() == '/' || path.back() == '.'))
            path.pop_back();

        const size_t slash = path.rfind('/');
        const size_t dot = path.rfind('.');
        bool ok = true;
        if (dot != std::string::npos && (slash == std::string::npos || dot > slash)) {
            std::string obj = path.substr(dot + 1);
            if (obj.size() > 9 && obj.compare(0, 9, "Default__") == 0)
                obj = obj.substr(9);
            StripClassSuffix(obj);
            if (obj.empty()) ok = false;
            else path = path.substr(0, dot + 1) + obj;
        } else if (ok) {
            StripClassSuffix(path);
            const size_t slash2 = path.rfind('/');
            const std::string last = (slash2 == std::string::npos) ? path : path.substr(slash2 + 1);
            if (last.empty()) ok = false;
            else if (last.find('.') == std::string::npos)
                path += "." + last;
        }
        if (ok && path.size() <= 255 && path.find("..") == std::string::npos) {
            id.path = path;
            id.key = ToLower(path);
        }
    }

    id.short_key = ShortToken(raw);
    if (id.short_key.empty() && !id.path.empty())
        id.short_key = ShortToken(id.path);
    return id;
}

inline bool Same(const Identity& a, const Identity& b) {
    if (!a.key.empty() && a.key == b.key) return true;
    if (!a.short_key.empty() && a.short_key == b.short_key) return true;
    return false;
}

inline bool SameRaw(const std::string& a, const std::string& b) {
    return Same(Identify(a), Identify(b));
}

} // namespace VitrineMatch
} // namespace CustomShop
