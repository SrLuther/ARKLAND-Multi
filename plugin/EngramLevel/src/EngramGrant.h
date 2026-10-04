#pragma once

#include "pch.h"

namespace EngramLevel {

// Um único OverridePlayerLevelEngramPoints neste valor (ou acima) compra o
// catálogo inteiro dentro de ServerApplyLevelUp e derruba o ASE 361.7.
// O 999 final do nivel200.txt cai aqui e não é concedido: a linha fica em 0
// enquanto o plugin estiver ligado e só volta no unload ou com Enabled false.
constexpr int kDefaultCatalogBuyoutPoints = 999;

inline bool IsCatalogBuyout(int points, int buyout) {
    return buyout > 0 && points >= buyout;
}

// Níveis gastos neste ServerApplyLevelUp, em ordem. Não é a faixa 1..atual
// nem níveis já gastos antes de /autoengram.
//
// Level up em que o nível sobe → esse nível.
// Mindwipe: o nível exibido fica e os pontos voltam. Cada ponto gasto é
// `before_char - available_before + 1` e os seguintes. Um ponto → um nível.
// Vários pontos no mesmo apply → essa faixa, um número de cada vez.
inline std::vector<int> AppliedLevelSpan(int before_base, int after_base,
                                         int before_char, int after_char,
                                         int available_before,
                                         int available_after) {
    if (after_base > before_base && after_base > 0)
        return {after_base};
    if (after_char > before_char && after_char > 0)
        return {after_char};
    if (available_before > available_after && before_char > 1) {
        const int points = available_before - available_after;
        int first = before_char - available_before + 1;
        if (first < 1) first = 1;
        std::vector<int> out;
        out.reserve(static_cast<size_t>(points));
        for (int i = 0; i < points; ++i) {
            const int level = first + i;
            if (level > before_char) break;
            out.push_back(level);
        }
        return out;
    }
    if (after_char > 0) return {after_char};
    if (before_char > 0) return {before_char};
    return {};
}

// O primeiro nível do apply. Quem gasta vários pontos usa AppliedLevelSpan.
inline int AppliedLevel(int before_base, int after_base,
                        int before_char, int after_char,
                        int available_before, int available_after) {
    const std::vector<int> span = AppliedLevelSpan(
        before_base, after_base, before_char, after_char,
        available_before, available_after);
    return span.empty() ? 0 : span.front();
}

// O que este clique pode liberar. Nunca tek e não-tek no mesmo passo.
enum class GrantTier { None, NonTek, Tek };

inline GrantTier ChooseGrantTier(bool unlock_non_tek, bool unlock_total,
                                 bool any_locked_non_tek) {
    if (unlock_total)
        return any_locked_non_tek ? GrantTier::NonTek : GrantTier::Tek;
    if (unlock_non_tek)
        return GrantTier::NonTek;
    return GrantTier::None;
}

// Vários pontos num apply: por nível, o lote não tek e só depois o lote tek
// se UnlockTotal. Um ponto devolve vazio — esse caso é ChooseGrantTier
// (um lote; tek espera outro ServerApplyLevelUp).
// O bool é tek. Tek nunca fica no mesmo par que o não tek daquele nível.
inline std::vector<std::pair<int, bool>> GrantBatchesForSpentLevels(
    const std::vector<int>& levels,
    bool unlock_non_tek,
    bool unlock_total) {
    std::vector<std::pair<int, bool>> out;
    if (levels.size() <= 1) return out;
    for (int level : levels) {
        if (level <= 0) continue;
        const bool non_tek_step = unlock_total || unlock_non_tek;
        if (!non_tek_step) continue;
        out.emplace_back(level, false);
        if (unlock_total)
            out.emplace_back(level, true);
    }
    return out;
}

inline std::string NormalizeEngramId(std::string id) {
    while (!id.empty() &&
           std::isspace(static_cast<unsigned char>(id.front())))
        id.erase(id.begin());
    while (!id.empty() &&
           std::isspace(static_cast<unsigned char>(id.back())))
        id.pop_back();
    for (char& ch : id)
        ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
    return id;
}

// Nome interno ou nome mostrado, inteiros e sem diferenciar maiúsculas.
// "rifle" não acerta "Tek Rifle" nem "EngramEntry_TekRifle_C".
inline bool EngramFilterHits(const std::string& internal_name,
                             const std::string& shown_name,
                             const std::string& filter) {
    const std::string id = NormalizeEngramId(filter);
    if (id.empty()) return false;
    return NormalizeEngramId(internal_name) == id ||
           NormalizeEngramId(shown_name) == id;
}

inline bool EngramListHits(const std::string& internal_name,
                           const std::string& shown_name,
                           const std::vector<std::string>& ids) {
    for (const auto& id : ids) {
        if (EngramFilterHits(internal_name, shown_name, id)) return true;
    }
    return false;
}

// Engrams vazio não apaga a base. ExtraEngrams soma. RemovedEngrams tira
// o item que o admin apagou. Extra nunca substitui a base inteira.
inline std::vector<std::string> MergeEngramIds(
    const std::vector<std::string>& embedded,
    const std::vector<std::string>& configured,
    bool use_configured,
    const std::vector<std::string>& extra,
    const std::vector<std::string>& removed) {
    std::vector<std::string> out;
    const std::vector<std::string>& base = use_configured ? configured : embedded;
    auto push_unique = [&](const std::string& raw) {
        const std::string id = NormalizeEngramId(raw);
        if (id.empty()) return;
        for (const auto& have : out) {
            if (have == id) return;
        }
        out.push_back(id);
    };
    for (const auto& id : base) push_unique(id);
    for (const auto& id : extra) push_unique(id);

    if (removed.empty()) return out;
    std::vector<std::string> kept;
    kept.reserve(out.size());
    for (const auto& id : out) {
        bool drop = false;
        for (const auto& raw : removed) {
            if (NormalizeEngramId(raw) == id) {
                drop = true;
                break;
            }
        }
        if (!drop) kept.push_back(id);
    }
    return kept;
}

// Libera só engramas com RequiredLevel == level, e só um tipo (tek ou
// não-tek) neste clique. Devolve quantos foram novos.
int UnlockExactLevel(AShooterPlayerController* controller, int level,
                     int character_level);

// Vários pontos num único ServerApplyLevelUp: um nível de cada vez, e tek
// só no lote seguinte ao não tek daquele mesmo nível quando UnlockTotal.
int UnlockSpentLevels(AShooterPlayerController* controller,
                      const std::vector<int>& levels);

} // namespace EngramLevel
