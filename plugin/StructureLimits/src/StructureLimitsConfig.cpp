#include "StructureLimitsConfig.h"

#include <json.hpp>

#include <fstream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <unordered_set>
#include <vector>

namespace StructureLimits {
namespace {

using Json = nlohmann::json;

std::filesystem::path PathFromUtf8(const std::string& value) {
    std::u8string encoded;
    encoded.reserve(value.size());
    for (unsigned char c : value) encoded.push_back(static_cast<char8_t>(c));
    return std::filesystem::path(encoded);
}

std::uint64_t ReadUnsigned(const Json& object, const char* key,
                           std::uint64_t fallback) {
    const auto it = object.find(key);
    if (it == object.end()) return fallback;
    if (it->is_number_unsigned()) return it->get<std::uint64_t>();
    if (it->is_number_integer()) {
        const auto value = it->get<std::int64_t>();
        if (value < 0) throw std::invalid_argument(std::string(key) + " cannot be negative");
        return static_cast<std::uint64_t>(value);
    }
    throw std::invalid_argument(std::string(key) + " must be an integer");
}

std::string ReadString(const Json& object, const char* key,
                       const std::string& fallback = {}) {
    const auto it = object.find(key);
    if (it == object.end()) return fallback;
    if (!it->is_string()) throw std::invalid_argument(std::string(key) + " must be a string");
    return it->get<std::string>();
}

bool ReadBoolean(const Json& object, const char* key, bool fallback) {
    const auto it = object.find(key);
    if (it == object.end()) return fallback;
    if (!it->is_boolean()) throw std::invalid_argument(std::string(key) + " must be boolean");
    return it->get<bool>();
}

} // namespace

MapIdentity PluginConfiguration::Identity() const {
    if (!enabled) throw std::logic_error("Disabled plugin configuration has no active identity");
    return MakeMapIdentity(mapName, instancePath);
}

PluginConfiguration ParsePluginConfiguration(const std::string& jsonText) {
    Json root;
    std::vector<std::unordered_set<std::string>> objectKeys;
    std::string duplicateKey;
    try {
        root = Json::parse(jsonText,
            [&objectKeys, &duplicateKey](int, Json::parse_event_t event, Json& parsed) {
                if (event == Json::parse_event_t::object_start) {
                    objectKeys.emplace_back();
                } else if (event == Json::parse_event_t::key) {
                    if (objectKeys.empty()) return true;
                    const auto key = parsed.get<std::string>();
                    if (!objectKeys.back().insert(key).second) {
                        duplicateKey = key;
                        return false;
                    }
                } else if (event == Json::parse_event_t::object_end &&
                           !objectKeys.empty()) {
                    objectKeys.pop_back();
                }
                return true;
            });
    } catch (const Json::exception& e) {
        throw std::invalid_argument(std::string("Invalid JSON configuration: ") + e.what());
    }
    if (!duplicateKey.empty())
        throw std::invalid_argument("Duplicate JSON key: " + duplicateKey);
    if (!root.is_object() || !root.contains("StructureLimits") ||
        !root.at("StructureLimits").is_object())
        throw std::invalid_argument("Configuration requires an object named StructureLimits");

    const auto& section = root.at("StructureLimits");
    PluginConfiguration result;
    result.enabled = ReadBoolean(section, "Enabled", false);
    result.observationProbeEnabled = ReadBoolean(section, "ObservationProbeEnabled", false);
    result.lifecycleObservationEnabled = ReadBoolean(section, "LifecycleObservationEnabled", false);
    result.lifecycleBeginPlayObservationEnabled = ReadBoolean(
        section, "LifecycleBeginPlayObservationEnabled", false);
    result.residentInventoryProbeEnabled = ReadBoolean(
        section, "ResidentInventoryProbeEnabled", false);
    result.liveInventoryEnabled = ReadBoolean(section,"LiveInventoryEnabled",false);
    result.enforcementRequiresValidatedInventory =
        ReadBoolean(section, "EnforcementRequiresValidatedInventory", true);
    if (!result.enforcementRequiresValidatedInventory)
        throw std::invalid_argument("EnforcementRequiresValidatedInventory must remain true");
    result.mapName = ReadString(section, "MapName");
    result.instancePath = ReadString(section, "InstancePath");
    result.limits.globalPrimary = ReadUnsigned(section, "LPG", 0);
    const auto percentage = ReadUnsigned(section, "ExtraPercentage", 25);
    if (percentage > (std::numeric_limits<std::uint32_t>::max)())
        throw std::invalid_argument("ExtraPercentage exceeds uint32 range");
    result.limits.extraPercentage = static_cast<std::uint32_t>(percentage);

    const auto blueprints = section.find("SpecificBlueprints");
    if (blueprints != section.end()) {
        if (!blueprints->is_array())
            throw std::invalid_argument("SpecificBlueprints must be an array");
        for (const auto& item : *blueprints) {
            if (!item.is_object())
                throw std::invalid_argument("Each specific blueprint entry must be an object");
            const auto blueprint = NormalizeBlueprintKey(ReadString(item, "Blueprint"));
            const auto limit = ReadUnsigned(item, "LEG", 0);
            if (blueprint.empty() || limit == 0)
                throw std::invalid_argument("Specific blueprint requires Blueprint and positive LEG");
            if (!result.limits.specificPrimary.emplace(blueprint, limit).second)
                throw std::invalid_argument("Duplicate specific blueprint: " + blueprint);
        }
    }

    result.localOutboxDirectory = PathFromUtf8(
        ReadString(section, "LocalOutboxDirectory"));
    result.offlineOwnersFile = PathFromUtf8(ReadString(section, "OfflineOwnersFile"));
    if(!result.offlineOwnersFile.empty()&&!result.offlineOwnersFile.is_absolute())
        throw std::invalid_argument("OfflineOwnersFile must be absolute");
    result.localSnapshotFile = PathFromUtf8(
        ReadString(section, "LocalSnapshotFile"));
    if (result.enabled) {
        if (result.mapName.empty() || result.instancePath.empty())
            throw std::invalid_argument("Enabled plugin requires MapName and InstancePath");
        if (!PathFromUtf8(result.instancePath).is_absolute())
            throw std::invalid_argument("InstancePath must be absolute");
        if (result.localOutboxDirectory.empty())
            throw std::invalid_argument("Enabled plugin requires LocalOutboxDirectory");
        if (!result.localOutboxDirectory.is_absolute())
            throw std::invalid_argument("LocalOutboxDirectory must be absolute");
        if (result.localSnapshotFile.empty() || !result.localSnapshotFile.is_absolute())
            throw std::invalid_argument("Enabled plugin requires an absolute LocalSnapshotFile");
        result.limits.Validate();
        (void)result.Identity();
    } else if (result.limits.globalPrimary != 0) {
        result.limits.Validate();
    }
    return result;
}

PluginConfiguration LoadPluginConfiguration(const std::filesystem::path& path) {
    std::ifstream input(path, std::ios::binary);
    if (!input) throw std::runtime_error("Cannot open Structure Limits configuration");
    std::ostringstream contents;
    contents << input.rdbuf();
    if (!input.good() && !input.eof())
        throw std::runtime_error("Cannot read Structure Limits configuration");
    return ParsePluginConfiguration(contents.str());
}

} // namespace StructureLimits
