#pragma once

#include <string>

namespace ArkPlayer {

// Compacta o dano para o texto flutuante.
// 9000 → 9k, 27000 → 27k, 2563000 → 2.6kk, 999500 → 999.5k,
// 1000000 → 1kk, 999 → 999. Sem vírgula e sem espaço.
// Casa decimal só quando o resto não é zero.
inline std::string FormatDamageAmount(long long amount) {
    if (amount <= 0) return "0";

    int ks = 0;
    long long n = amount;
    while (n >= 1000 && ks < 8) {
        const long long next = n / 1000;
        const long long rem = n % 1000;
        if (next >= 1000) {
            n = next;
            ++ks;
            continue;
        }
        ++ks;
        int tenth = static_cast<int>((rem + 50) / 100);
        n = next;
        if (tenth >= 10) {
            ++n;
            tenth = 0;
        }
        if (n >= 1000) continue;

        std::string out = std::to_string(n);
        if (tenth != 0) {
            out.push_back('.');
            out.push_back(static_cast<char>('0' + tenth));
        }
        out.append(static_cast<size_t>(ks), 'k');
        return out;
    }
    return std::to_string(n);
}

}  // namespace ArkPlayer
