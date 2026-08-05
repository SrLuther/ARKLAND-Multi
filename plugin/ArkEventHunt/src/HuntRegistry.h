#pragma once

#include "pch.h"

namespace ArkEventHunt {
namespace Registry {

enum class Mode : uint8_t {
    Spike = 0,
    // Mode A — /eve <code>: só owner_steam_id; spawn no jogador.
    ModeA = 1,
    // Mode B — /eveadm <code>: evento público; tag mode=PUBLIC.
    ModeB = 2,
};

struct Entry {
    Mode mode = Mode::Spike;
    std::string code;
    int64_t claim_id = 0;      // Mode A
    int64_t instance_id = 0;   // Mode B
    int64_t challenge_id = 0;  // Mode A
    int64_t public_dino_id = 0;
    int64_t session_id = 0;
    uint64_t team_id = 0; // Mode A claim team (owner)
    std::string owner_steam_id;
    std::string display_name;
    std::string server_id;
    std::vector<std::string> allowed_weapons;
    float min_allowed_weapon_damage_ratio = 0.80f;
    bool forbid_torpor = true;
    bool official_weapons_only = true;
    // Mode B: se false, kill/assist de tame pessoal → sem score.
    bool allow_personal_tames = true;

    uint32_t dino_id1 = 0;
    uint32_t dino_id2 = 0;
    std::string last_weapon_hint;
    uint64_t last_attacker_steam = 0;
    bool outcome_sent = false;

    float allowed_hp_damage = 0.f;
    float other_hp_damage = 0.f;
    float torpor_hits = 0.f;
    float personal_tame_hp_damage = 0.f;
    int damage_events = 0;

    // TTL Mode B (unix seconds). 0 = sem expire (fica até morte).
    int64_t expires_at_unix = 0;
    bool ttl_warned = false;
};

std::string MakeKey(uint32_t id1, uint32_t id2);

void Clear();
bool Bind(const Entry& entry);
bool Find(uint32_t id1, uint32_t id2, Entry& out);
bool UpdateHints(uint32_t id1, uint32_t id2,
                 uint64_t steam_id, const std::string& weapon_hint);
bool RecordDamage(uint32_t id1, uint32_t id2, float hp_amount, bool allowed,
                  bool is_torpor, bool is_personal_tame,
                  const std::string& weapon_hint, uint64_t steam_id);
bool MarkOutcomeSent(uint32_t id1, uint32_t id2);
bool MarkTtlWarned(uint32_t id1, uint32_t id2);
bool Unbind(uint32_t id1, uint32_t id2);
bool HasActiveClaimForOwner(const std::string& owner_steam_id);
size_t Count();
size_t CountMode(Mode mode);

// Snapshot cópia (para timers / status sem segurar lock longo).
std::vector<Entry> Snapshot(Mode mode_filter = Mode::Spike,
                            bool filter_by_mode = false);

} // namespace Registry
} // namespace ArkEventHunt
