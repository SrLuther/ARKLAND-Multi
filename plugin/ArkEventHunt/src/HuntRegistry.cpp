#include "pch.h"
#include "HuntRegistry.h"

namespace ArkEventHunt {
namespace Registry {

namespace {

std::mutex g_mu;
std::unordered_map<std::string, Entry> g_entries;

} // anonymous

std::string MakeKey(uint32_t id1, uint32_t id2) {
    return std::to_string(id1) + ":" + std::to_string(id2);
}

void Clear() {
    std::lock_guard<std::mutex> lock(g_mu);
    g_entries.clear();
}

bool Bind(const Entry& entry) {
    if (entry.dino_id1 == 0 && entry.dino_id2 == 0)
        return false;
    std::lock_guard<std::mutex> lock(g_mu);
    g_entries[MakeKey(entry.dino_id1, entry.dino_id2)] = entry;
    return true;
}

bool Find(uint32_t id1, uint32_t id2, Entry& out) {
    std::lock_guard<std::mutex> lock(g_mu);
    const auto it = g_entries.find(MakeKey(id1, id2));
    if (it == g_entries.end()) return false;
    out = it->second;
    return true;
}

bool UpdateHints(uint32_t id1, uint32_t id2,
                 uint64_t steam_id, const std::string& weapon_hint) {
    std::lock_guard<std::mutex> lock(g_mu);
    const auto it = g_entries.find(MakeKey(id1, id2));
    if (it == g_entries.end()) return false;
    if (steam_id != 0)
        it->second.last_attacker_steam = steam_id;
    if (!weapon_hint.empty())
        it->second.last_weapon_hint = weapon_hint;
    return true;
}

bool RecordDamage(uint32_t id1, uint32_t id2, float hp_amount, bool allowed,
                  bool is_torpor, bool is_personal_tame,
                  const std::string& weapon_hint, uint64_t steam_id) {
    std::lock_guard<std::mutex> lock(g_mu);
    const auto it = g_entries.find(MakeKey(id1, id2));
    if (it == g_entries.end()) return false;
    Entry& e = it->second;
    if (is_torpor) {
        e.torpor_hits += (hp_amount > 0.f ? hp_amount : 1.f);
    }
    if (is_personal_tame && hp_amount > 0.f)
        e.personal_tame_hp_damage += hp_amount;
    if (hp_amount > 0.f) {
        if (allowed)
            e.allowed_hp_damage += hp_amount;
        else
            e.other_hp_damage += hp_amount;
        e.damage_events += 1;
    } else if (is_torpor) {
        e.damage_events += 1;
    }
    if (steam_id != 0)
        e.last_attacker_steam = steam_id;
    if (!weapon_hint.empty())
        e.last_weapon_hint = weapon_hint;
    return true;
}

bool MarkOutcomeSent(uint32_t id1, uint32_t id2) {
    std::lock_guard<std::mutex> lock(g_mu);
    const auto it = g_entries.find(MakeKey(id1, id2));
    if (it == g_entries.end()) return false;
    if (it->second.outcome_sent) return false;
    it->second.outcome_sent = true;
    return true;
}

bool MarkTtlWarned(uint32_t id1, uint32_t id2) {
    std::lock_guard<std::mutex> lock(g_mu);
    const auto it = g_entries.find(MakeKey(id1, id2));
    if (it == g_entries.end()) return false;
    if (it->second.ttl_warned) return false;
    it->second.ttl_warned = true;
    return true;
}

bool Unbind(uint32_t id1, uint32_t id2) {
    std::lock_guard<std::mutex> lock(g_mu);
    return g_entries.erase(MakeKey(id1, id2)) > 0;
}

bool HasActiveClaimForOwner(const std::string& owner_steam_id) {
    if (owner_steam_id.empty()) return false;
    std::lock_guard<std::mutex> lock(g_mu);
    for (const auto& kv : g_entries) {
        if (kv.second.mode == Mode::ModeA &&
            kv.second.owner_steam_id == owner_steam_id &&
            !kv.second.outcome_sent)
            return true;
    }
    return false;
}

size_t Count() {
    std::lock_guard<std::mutex> lock(g_mu);
    return g_entries.size();
}

size_t CountMode(Mode mode) {
    std::lock_guard<std::mutex> lock(g_mu);
    size_t n = 0;
    for (const auto& kv : g_entries) {
        if (kv.second.mode == mode) ++n;
    }
    return n;
}

std::vector<Entry> Snapshot(Mode mode_filter, bool filter_by_mode) {
    std::lock_guard<std::mutex> lock(g_mu);
    std::vector<Entry> out;
    out.reserve(g_entries.size());
    for (const auto& kv : g_entries) {
        if (filter_by_mode && kv.second.mode != mode_filter)
            continue;
        out.push_back(kv.second);
    }
    return out;
}

} // namespace Registry
} // namespace ArkEventHunt
