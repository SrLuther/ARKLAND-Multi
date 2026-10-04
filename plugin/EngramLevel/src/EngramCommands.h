#pragma once

#include "pch.h"

namespace EngramLevel {

// Quem não está na lista permanece com o automático DESLIGADO.
inline bool IsAutoOn(const std::vector<std::string>& opted_in,
                     const std::string& steam) {
    if (steam.empty()) return false;
    for (const auto& id : opted_in) {
        if (id == steam) return true;
    }
    return false;
}

// Primeiro uso liga. O seguinte desliga. Devolve o estado novo.
inline bool ToggleAuto(std::vector<std::string>& opted_in,
                       const std::string& steam) {
    if (steam.empty()) return false;
    for (auto it = opted_in.begin(); it != opted_in.end(); ++it) {
        if (*it == steam) {
            opted_in.erase(it);
            return false;
        }
    }
    opted_in.push_back(steam);
    return true;
}

namespace Prefs {

void Load();
bool IsAutoEnabled(const std::string& steam);
bool Toggle(const std::string& steam);

} // namespace Prefs

namespace Commands {

void Register();
void Unregister();

} // namespace Commands
} // namespace EngramLevel
