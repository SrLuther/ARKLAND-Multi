#include "StructureLimitsCore.h"

#include <algorithm>
#include <cctype>
#include <filesystem>
#include <limits>
#include <set>
#include <sstream>
#include <stdexcept>

namespace StructureLimits {
namespace {

std::size_t Utf8CharacterCount(const std::string& value) {
    std::size_t count = 0;
    for (std::size_t i = 0; i < value.size();) {
        const unsigned char c = static_cast<unsigned char>(value[i]);
        if (c == ' ') {
            ++i;
            continue;
        }
        if ((c & 0xC0) != 0x80) ++count;
        if (c < 0x80) ++i;
        else if ((c & 0xE0) == 0xC0) i += (std::min)(2u, static_cast<unsigned>(value.size() - i));
        else if ((c & 0xF0) == 0xE0) i += (std::min)(3u, static_cast<unsigned>(value.size() - i));
        else i += (std::min)(4u, static_cast<unsigned>(value.size() - i));
    }
    return count;
}

std::string FirstThreeNonSpaceCharacters(const std::string& value) {
    std::string result;
    std::size_t characters = 0;
    for (std::size_t i = 0; i < value.size() && characters < 3;) {
        const unsigned char first = static_cast<unsigned char>(value[i]);
        std::size_t width = first < 0x80 ? 1 :
            ((first & 0xE0) == 0xC0 ? 2 : ((first & 0xF0) == 0xE0 ? 3 : 4));
        width = std::min(width, value.size() - i);
        if (width == 1 && std::isspace(first)) {
            ++i;
            continue;
        }
        for (std::size_t j = 0; j < width; ++j) {
            unsigned char c = static_cast<unsigned char>(value[i + j]);
            if (width == 1) c = static_cast<unsigned char>(std::toupper(c));
            result.push_back(static_cast<char>(c));
        }
        ++characters;
        i += width;
    }
    return result;
}

std::string NormalizePath(const std::string& path) {
    std::u8string utf8Input;
    utf8Input.reserve(path.size());
    for (unsigned char c : path) utf8Input.push_back(static_cast<char8_t>(c));
    const auto utf8Path = std::filesystem::path(utf8Input)
        .lexically_normal().u8string();
    const std::string lexical(reinterpret_cast<const char*>(utf8Path.data()),
                               utf8Path.size());
    std::string normalized;
    normalized.reserve(lexical.size());
    for (unsigned char c : lexical) {
        char out = c == '/' ? '\\' : static_cast<char>(c);
        if (out >= 'A' && out <= 'Z') out = static_cast<char>(out - 'A' + 'a');
        normalized.push_back(out);
    }
    while (normalized.size() > 3 && normalized.back() == '\\')
        normalized.pop_back();
    return normalized;
}

std::string NormalizeBlueprintKeyImpl(const std::string& blueprint) {
    auto value = blueprint;
    const auto first = value.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) return {};
    const auto last = value.find_last_not_of(" \t\r\n");
    value = value.substr(first, last - first + 1);

    // Accept the wrapper used by ArkApi config examples as well as the full
    // UObject::GetFullName forms emitted by the diagnostic probe.
    if (value.rfind("Blueprint'", 0) == 0 && value.size() > 11 &&
        value.back() == '\'') {
        value = value.substr(10, value.size() - 11);
    } else {
        const auto separator = value.find(' ');
        if (separator != std::string::npos && separator + 1 < value.size() &&
            value[separator + 1] == '/')
            value.erase(0, separator + 1);
        for (const char* prefix : {"BlueprintGeneratedClass ", "Blueprint ", "Class "}) {
            const std::string token(prefix);
            if (value.rfind(token, 0) == 0) {
                value.erase(0, token.size());
                break;
            }
        }
    }

    if (value.size() >= 2 && value.front() == '\'' && value.back() == '\'')
        value = value.substr(1, value.size() - 2);

    const auto defaultObject = value.find("Default__");
    if (defaultObject != std::string::npos)
        value.erase(defaultObject, 9);

    // BlueprintGeneratedClass names end in _C. Config paths often include
    // the object name explicitly (Package.Object), while GetFullName may only
    // expose Package_Class_C. Canonicalize both to Package.Package.
    const auto slash = value.find_last_of("/\\");
    const auto dot = value.find_last_of('.');
    const auto objectStart = dot == std::string::npos ?
        (slash == std::string::npos ? 0 : slash + 1) : dot + 1;
    if (value.size() >= objectStart + 2 && value.compare(value.size() - 2, 2, "_C") == 0)
        value.erase(value.size() - 2);

    const auto packageSlash = value.find_last_of("/\\");
    const auto packageDot = value.find_last_of('.');
    if (packageDot == std::string::npos ||
        (packageSlash != std::string::npos && packageDot < packageSlash)) {
        const auto leaf = value.substr(packageSlash == std::string::npos ? 0 : packageSlash + 1);
        if (!leaf.empty()) value += "." + leaf;
    }

    for (auto& c : value) {
        if (c == '\\') c = '/';
        else if (static_cast<unsigned char>(c) < 0x80)
            c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    }
    return value;
}

std::string InstanceFolderNumber(const std::string& normalizedPath) {
    const auto separator = normalizedPath.find_last_of('\\');
    const auto folder = normalizedPath.substr(separator == std::string::npos
        ? 0 : separator + 1);
    if (folder.empty() || !std::all_of(folder.begin(), folder.end(),
        [](unsigned char c) { return c >= '0' && c <= '9'; }))
        throw std::invalid_argument("Instance folder must end with its numeric folder ID");
    return folder;
}

std::uint64_t CalculateExtra(std::uint64_t primary, std::uint32_t percentage) {
    const auto quotient = primary / 100;
    const auto remainder = primary % 100;
    if (percentage != 0 && quotient >
        (std::numeric_limits<std::uint64_t>::max)() / percentage)
        throw std::overflow_error("Extra capacity overflows uint64");
    const auto whole = quotient * percentage;
    const auto fractionalProduct = remainder * percentage;
    const auto fractional = fractionalProduct / 100 +
        (fractionalProduct % 100 != 0 ? 1 : 0);
    if (whole > (std::numeric_limits<std::uint64_t>::max)() - fractional)
        throw std::overflow_error("Extra capacity overflows uint64");
    return whole + fractional;
}

std::uint64_t CountFor(
    const std::unordered_map<std::string, std::uint64_t>& counts,
    const std::string& key) {
    const auto it = counts.find(key);
    return it == counts.end() ? 0 : it->second;
}

} // namespace

std::string NormalizeBlueprintKey(const std::string& blueprint) {
    return NormalizeBlueprintKeyImpl(blueprint);
}

MapIdentity MakeMapIdentity(const std::string& mapName,
                            const std::string& instancePath) {
    if (mapName.empty()) throw std::invalid_argument("Map name is required");
    if (instancePath.empty())
        throw std::invalid_argument("Instance path is required");
    const auto characters = Utf8CharacterCount(mapName);
    const auto prefix = FirstThreeNonSpaceCharacters(mapName);
    if (characters == 0 || prefix.empty())
        throw std::invalid_argument("Map name has no usable characters");
    const auto normalizedPath = NormalizePath(instancePath);
    return {(characters < 10 ? "0" : "") + std::to_string(characters) + prefix +
                InstanceFolderNumber(normalizedPath), normalizedPath};
}

std::uint64_t Configuration::GlobalExtra() const {
    return CalculateExtra(globalPrimary, extraPercentage);
}

std::uint64_t Configuration::GlobalCapacity() const {
    const auto extra = GlobalExtra();
    if (globalPrimary > (std::numeric_limits<std::uint64_t>::max)() - extra)
        throw std::overflow_error("Global capacity overflows uint64");
    return globalPrimary + extra;
}

std::uint64_t Configuration::SpecificExtra(std::uint64_t primary) const {
    return CalculateExtra(primary, extraPercentage);
}

void Configuration::Validate() const {
    if (globalPrimary == 0)
        throw std::invalid_argument("LPG must be greater than zero");
    (void)GlobalCapacity();
    for (const auto& [blueprint, primary] : specificPrimary) {
        if (NormalizeBlueprintKey(blueprint).empty())
            throw std::invalid_argument("Specific limit blueprint cannot be empty");
        if (primary == 0)
            throw std::invalid_argument("LEG must be greater than zero");
        const auto extra = SpecificExtra(primary);
        if (primary > (std::numeric_limits<std::uint64_t>::max)() - extra)
            throw std::overflow_error("Specific capacity overflows uint64");
    }
}

Owner Owner::ForPlayer(const std::string& tribeId, const std::string& steamId) {
    if (steamId.empty()) return {};
    if (!tribeId.empty()) return {"tribe:" + tribeId, tribeId, steamId};
    return {"solo:" + steamId, {}, steamId};
}

std::string FormatPrimaryLimitsMessage(const LimitsSummary& summary) {
    std::ostringstream message;
    message << "Limites primarios | LPG: " << summary.globalUsed << '/'
            << summary.globalPrimary << " (restam "
            << summary.globalRemainingPrimary << ')';
    for (const auto& specific : summary.specific) {
        message << " | LEG " << specific.blueprint << ": " << specific.used << '/'
                << specific.primary << " (restam " << specific.remainingPrimary << ')';
    }
    message << ". Capacidades extras (LPE/LEE) e licença: Minha Área ARKLAND.";
    return message.str();
}

LimitEngine::LimitEngine(Configuration config, MapIdentity map)
    : config_(std::move(config)), map_(std::move(map)) {
    std::map<std::string, std::uint64_t> normalizedBlueprints;
    for (const auto& [blueprint, primary] : config_.specificPrimary) {
        const auto key = NormalizeBlueprintKey(blueprint);
        if (key.empty() || !normalizedBlueprints.emplace(key, primary).second)
            throw std::invalid_argument("Specific blueprint keys collide after normalization");
    }
    config_.specificPrimary = std::move(normalizedBlueprints);
    config_.Validate();
    if (map_.displayId.empty() || map_.canonicalInstancePath.empty())
        throw std::invalid_argument("Complete map identity is required");
}

bool LimitEngine::ActivateFromSnapshot(const WorldSnapshot& snapshot,
                                       std::string* error) {
    std::lock_guard<std::mutex> lock(mutex_);
    auto fail = [&](const std::string& message) {
        enforcing_ = false;
        if (error) *error = message;
        return false;
    };
    if (!snapshot.complete || !snapshot.validated)
        return fail("World inventory is incomplete or not validated");
    if (!snapshot.placementHookValidated)
        return fail("Placement hook safety has not been validated");
    if (!reservations_.empty())
        return fail("Cannot replace inventory while placement reservations are pending");
    if (snapshot.map.displayId != map_.displayId ||
        snapshot.map.canonicalInstancePath != map_.canonicalInstancePath)
        return fail("World inventory belongs to a different map instance");

    std::unordered_map<std::string, std::uint64_t> global;
    std::unordered_map<std::string,
        std::unordered_map<std::string, std::uint64_t>> specific;
    std::unordered_map<std::string, StructureRecord> structures;
    for (const auto& structure : snapshot.structures) {
        if (structure.structureId.empty() || structure.owner.key.empty() ||
            structure.blueprint.empty())
            return fail("Snapshot contains a structure without stable identity");
        const auto blueprint = NormalizeBlueprintKey(structure.blueprint);
        if (blueprint.empty())
            return fail("Snapshot contains a structure without a usable blueprint identity");
        if (!structures.emplace(structure.structureId,
            StructureRecord{structure.owner, blueprint}).second)
            return fail("Snapshot contains duplicate structure IDs");
        ++global[structure.owner.key];
        if (config_.specificPrimary.count(blueprint) != 0)
            ++specific[structure.owner.key][blueprint];
    }

    globalCounts_ = std::move(global);
    specificCounts_ = std::move(specific);
    pendingGlobal_.clear();
    pendingSpecific_.clear();
    reservations_.clear();
    structures_ = std::move(structures);
    enforcing_ = true;
    if (error) error->clear();
    return true;
}

void LimitEngine::SuspendEnforcement() {
    std::lock_guard<std::mutex> lock(mutex_);
    enforcing_ = false;
    // Preserve in-flight reservations so their eventual commit/cancel can
    // update counts after enforcement has entered fail-open mode.
}

bool LimitEngine::IsEnforcing() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return enforcing_;
}

void LimitEngine::PutLicense(const std::string& steamId,
                             std::int64_t expiresAtUnixSeconds) {
    if (steamId.empty() || expiresAtUnixSeconds <= 0)
        throw std::invalid_argument("License requires SteamID and expiry");
    std::lock_guard<std::mutex> lock(mutex_);
    licenses_[steamId] = expiresAtUnixSeconds;
}

std::int64_t LimitEngine::RenewLicense(const std::string& steamId,
                                       std::int64_t nowUnixSeconds) {
    if (steamId.empty())
        throw std::invalid_argument("Renewal requires SteamID");
    constexpr std::int64_t secondsPerDay = 24 * 60 * 60;
    constexpr std::int64_t licensePeriodDays = 30;
    const auto seconds = licensePeriodDays * secondsPerDay;
    std::lock_guard<std::mutex> lock(mutex_);
    const auto existing = licenses_.find(steamId);
    const auto base = existing == licenses_.end()
        ? nowUnixSeconds : (std::max)(nowUnixSeconds, existing->second);
    if (base > (std::numeric_limits<std::int64_t>::max)() - seconds)
        throw std::overflow_error("License expiry overflows int64");
    const auto expiry = base + seconds;
    licenses_[steamId] = expiry;
    return expiry;
}

bool LimitEngine::HasActiveLicense(const std::string& steamId,
                                  std::int64_t nowUnixSeconds) const {
    std::lock_guard<std::mutex> lock(mutex_);
    const auto it = licenses_.find(steamId);
    return it != licenses_.end() && it->second > nowUnixSeconds;
}

std::uint64_t LimitEngine::CommittedGlobalCount(const std::string& ownerKey) const {
    return CountFor(globalCounts_, ownerKey);
}

std::uint64_t LimitEngine::CommittedSpecificCount(
    const std::string& ownerKey, const std::string& blueprint) const {
    const auto owner = specificCounts_.find(ownerKey);
    return owner == specificCounts_.end() ? 0 : CountFor(owner->second, blueprint);
}

std::uint64_t LimitEngine::EffectiveGlobalCount(const std::string& ownerKey) const {
    return CommittedGlobalCount(ownerKey) + CountFor(pendingGlobal_, ownerKey);
}

std::uint64_t LimitEngine::EffectiveSpecificCount(
    const std::string& ownerKey, const std::string& blueprint) const {
    const auto pending = pendingSpecific_.find(ownerKey);
    const auto reservations = pending == pendingSpecific_.end()
        ? 0 : CountFor(pending->second, blueprint);
    return CommittedSpecificCount(ownerKey, blueprint) + reservations;
}

PlacementDecision LimitEngine::ReservePlacement(
    const std::string& tribeId, const std::string& steamId,
    const std::string& blueprint, std::int64_t nowUnixSeconds) {
    std::lock_guard<std::mutex> lock(mutex_);
    if (!enforcing_)
        return {PlacementState::BypassEnforcement,
                "Enforcement suspended until inventory is validated", {}, false, false};
    const auto blueprintKey = NormalizeBlueprintKey(blueprint);
    if (steamId.empty() || blueprintKey.empty())
        return {PlacementState::BypassEnforcement,
                "Player or blueprint identity unavailable", {}, false, false};

    Owner owner = Owner::ForPlayer(tribeId, steamId);
    const bool specific = config_.specificPrimary.count(blueprintKey) != 0;
    const auto globalUsed = EffectiveGlobalCount(owner.key);
    if (globalUsed >= config_.GlobalCapacity())
        return {PlacementState::Denied, "Global capacity exhausted", {}, false, false};

    bool usesGlobalExtra = globalUsed >= config_.globalPrimary;
    bool usesSpecificExtra = false;
    if (specific) {
        const auto primary = config_.specificPrimary.at(blueprintKey);
        const auto used = EffectiveSpecificCount(owner.key, blueprintKey);
        const auto extra = config_.SpecificExtra(primary);
        if (used >= primary + extra)
            return {PlacementState::Denied,
                    "Blueprint-specific capacity exhausted", {}, false, false};
        usesSpecificExtra = used >= primary;
    }

    if ((usesGlobalExtra || usesSpecificExtra) &&
        (!licenses_.count(steamId) || licenses_.at(steamId) <= nowUnixSeconds))
        return {PlacementState::Denied,
                "Active license required for extra capacity", {},
                usesGlobalExtra, usesSpecificExtra};

    const auto reservationId = "r" + std::to_string(nextReservation_++);
    Reservation reservation{owner, blueprintKey, specific};
    reservations_.emplace(reservationId, reservation);
    ++pendingGlobal_[owner.key];
    if (specific) ++pendingSpecific_[owner.key][blueprintKey];
    return {PlacementState::Reserved, "Capacity reserved", reservationId,
            usesGlobalExtra, usesSpecificExtra};
}

void LimitEngine::RemoveReservationCounts(const Reservation& reservation) {
    auto global = pendingGlobal_.find(reservation.owner.key);
    if (global != pendingGlobal_.end()) {
        if (global->second > 1) --global->second;
        else pendingGlobal_.erase(global);
    }
    if (!reservation.specific) return;
    auto owner = pendingSpecific_.find(reservation.owner.key);
    if (owner == pendingSpecific_.end()) return;
    auto blueprint = owner->second.find(reservation.blueprint);
    if (blueprint != owner->second.end()) {
        if (blueprint->second > 1) --blueprint->second;
        else owner->second.erase(blueprint);
    }
    if (owner->second.empty()) pendingSpecific_.erase(owner);
}

bool LimitEngine::CommitPlacement(const std::string& reservationId,
                                  const std::string& structureId) {
    if (structureId.empty()) return false;
    std::lock_guard<std::mutex> lock(mutex_);
    const auto reservation = reservations_.find(reservationId);
    if (reservation == reservations_.end() || structures_.count(structureId))
        return false;
    StructureRecord record{reservation->second.owner, reservation->second.blueprint};
    ++globalCounts_[record.owner.key];
    if (reservation->second.specific)
        ++specificCounts_[record.owner.key][record.blueprint];
    structures_.emplace(structureId, std::move(record));
    RemoveReservationCounts(reservation->second);
    reservations_.erase(reservation);
    return true;
}

bool LimitEngine::CancelPlacement(const std::string& reservationId) {
    std::lock_guard<std::mutex> lock(mutex_);
    const auto reservation = reservations_.find(reservationId);
    if (reservation == reservations_.end()) return false;
    RemoveReservationCounts(reservation->second);
    reservations_.erase(reservation);
    return true;
}

bool LimitEngine::ReleaseStructure(const std::string& structureId) {
    std::lock_guard<std::mutex> lock(mutex_);
    const auto it = structures_.find(structureId);
    if (it == structures_.end()) return false;
    auto global = globalCounts_.find(it->second.owner.key);
    if (global != globalCounts_.end()) {
        if (global->second > 1) --global->second;
        else globalCounts_.erase(global);
    }
    if (config_.specificPrimary.count(it->second.blueprint)) {
        auto owner = specificCounts_.find(it->second.owner.key);
        if (owner != specificCounts_.end()) {
            auto blueprint = owner->second.find(it->second.blueprint);
            if (blueprint != owner->second.end()) {
                if (blueprint->second > 1) --blueprint->second;
                else owner->second.erase(blueprint);
            }
            if (owner->second.empty()) specificCounts_.erase(owner);
        }
    }
    structures_.erase(it);
    return true;
}

bool LimitEngine::ReassignStructure(const std::string& structureId,
                                    const Owner& newOwner) {
    if (newOwner.key.empty()) return false;
    std::lock_guard<std::mutex> lock(mutex_);
    const auto structure = structures_.find(structureId);
    if (structure == structures_.end()) return false;
    if (structure->second.owner.key == newOwner.key) return true;

    auto oldGlobal = globalCounts_.find(structure->second.owner.key);
    if (oldGlobal != globalCounts_.end()) {
        if (oldGlobal->second > 1) --oldGlobal->second;
        else globalCounts_.erase(oldGlobal);
    }
    if (config_.specificPrimary.count(structure->second.blueprint)) {
        auto oldOwner = specificCounts_.find(structure->second.owner.key);
        if (oldOwner != specificCounts_.end()) {
            auto oldBlueprint = oldOwner->second.find(structure->second.blueprint);
            if (oldBlueprint != oldOwner->second.end()) {
                if (oldBlueprint->second > 1) --oldBlueprint->second;
                else oldOwner->second.erase(oldBlueprint);
            }
            if (oldOwner->second.empty()) specificCounts_.erase(oldOwner);
        }
    }
    ++globalCounts_[newOwner.key];
    if (config_.specificPrimary.count(structure->second.blueprint))
        ++specificCounts_[newOwner.key][structure->second.blueprint];
    structure->second.owner = newOwner;
    return true;
}

bool LimitEngine::CanMergeTribes(const std::string& tribeA,
                                const std::string& tribeB) const {
    std::lock_guard<std::mutex> lock(mutex_);
    if (!enforcing_) return true;
    if (tribeA.empty() || tribeB.empty() || tribeA == tribeB) return true;
    const auto keyA = "tribe:" + tribeA;
    const auto keyB = "tribe:" + tribeB;
    const auto cap = config_.GlobalCapacity();
    const auto countA = EffectiveGlobalCount(keyA);
    const auto countB = EffectiveGlobalCount(keyB);
    if (countA > cap || countB > cap - countA) return false;
    return true;
}

LimitsSummary LimitEngine::GetSummary(const std::string& tribeId,
                                      const std::string& steamId) const {
    std::lock_guard<std::mutex> lock(mutex_);
    const auto owner = Owner::ForPlayer(tribeId, steamId);
    LimitsSummary result;
    result.globalUsed = CommittedGlobalCount(owner.key);
    result.globalPrimary = config_.globalPrimary;
    result.globalRemainingPrimary = result.globalUsed >= config_.globalPrimary
        ? 0 : config_.globalPrimary - result.globalUsed;
    for (const auto& [blueprint, primary] : config_.specificPrimary) {
        const auto used = CommittedSpecificCount(owner.key, blueprint);
        result.specific.push_back({blueprint, used, primary,
            used >= primary ? 0 : primary - used});
    }
    return result;
}

} // namespace StructureLimits
