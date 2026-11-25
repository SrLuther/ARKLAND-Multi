#include "LocalSnapshotStore.h"

#include <json.hpp>

#include <atomic>
#include <fstream>
#include <iterator>
#include <limits>
#include <set>
#include <stdexcept>

#ifdef _WIN32
#define NOMINMAX
#include <Windows.h>
#endif

namespace StructureLimits {
namespace {

using Json = nlohmann::json;
constexpr std::uint32_t schemaVersion = 1;
constexpr std::uintmax_t maximumSnapshotBytes = 128ull * 1024ull * 1024ull;

std::uint32_t Crc32(const std::string& data) {
    std::uint32_t crc = 0xFFFFFFFFu;
    for (unsigned char byte : data) {
        crc ^= byte;
        for (int bit = 0; bit < 8; ++bit)
            crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
    }
    return ~crc;
}

Json SnapshotPayload(const WorldSnapshot& snapshot) {
    Json payload;
    payload["schema_version"] = schemaVersion;
    payload["map"] = {
        {"display_id", snapshot.map.displayId},
        {"canonical_instance_path", snapshot.map.canonicalInstancePath}
    };
    payload["structures"] = Json::array();
    for (const auto& structure : snapshot.structures) {
        payload["structures"].push_back({
            {"structure_id", structure.structureId},
            {"owner_key", structure.owner.key},
            {"tribe_id", structure.owner.tribeId},
            {"steam_id", structure.owner.steamId},
            {"blueprint", structure.blueprint}
        });
    }
    return payload;
}

std::string ReadFile(const std::filesystem::path& path) {
    std::ifstream input(path, std::ios::binary);
    if (!input) throw std::runtime_error("Unable to read local world snapshot");
    return std::string(std::istreambuf_iterator<char>(input),
                       std::istreambuf_iterator<char>());
}

bool SetError(std::string* error, const std::string& message) {
    if (error) *error = message;
    return false;
}

void WriteAtomically(const std::filesystem::path& path,
                     const std::string& contents) {
#ifdef _WIN32
    static std::atomic<unsigned long> sequence{0};
    const auto temporary = std::filesystem::path(
        path.wstring() + L"." + std::to_wstring(++sequence) + L".tmp");
    HANDLE file = CreateFileW(temporary.c_str(), GENERIC_WRITE, 0, nullptr,
        CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE)
        throw std::runtime_error("Unable to create local snapshot temporary file");

    bool written = contents.size() <= static_cast<std::size_t>(MAXDWORD);
    std::size_t offset = 0;
    while (written && offset < contents.size()) {
        DWORD bytesWritten = 0;
        const DWORD requested = static_cast<DWORD>(contents.size() - offset);
        written = WriteFile(file, contents.data() + offset, requested,
            &bytesWritten, nullptr) != 0 && bytesWritten != 0;
        offset += bytesWritten;
    }
    if (written) written = FlushFileBuffers(file) != 0;
    CloseHandle(file);
    if (!written) {
        DeleteFileW(temporary.c_str());
        throw std::runtime_error("Unable to flush local snapshot to disk");
    }
    if (!MoveFileExW(temporary.c_str(), path.c_str(),
                     MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        DeleteFileW(temporary.c_str());
        throw std::runtime_error("Unable to atomically publish local snapshot");
    }
#else
    (void)path;
    (void)contents;
    throw std::runtime_error("Local snapshot persistence currently supports Windows only");
#endif
}

} // namespace

LocalSnapshotStore::LocalSnapshotStore(std::filesystem::path filePath,
                                       MapIdentity expectedMap)
    : filePath_(std::move(filePath)), expectedMap_(std::move(expectedMap)) {
    if (filePath_.empty()) throw std::invalid_argument("Snapshot path is required");
    if (expectedMap_.displayId.empty() || expectedMap_.canonicalInstancePath.empty())
        throw std::invalid_argument("Snapshot map identity is required");
}

bool LocalSnapshotStore::Save(const WorldSnapshot& snapshot,
                              std::string* error) const {
    if (!snapshot.complete || !snapshot.validated)
        return SetError(error, "Only complete validated inventories can be persisted");
    if (snapshot.map.displayId != expectedMap_.displayId ||
        snapshot.map.canonicalInstancePath != expectedMap_.canonicalInstancePath)
        return SetError(error, "Snapshot belongs to a different map instance");
    std::set<std::string> ids;
    for (const auto& structure : snapshot.structures) {
        if (structure.structureId.empty() || structure.owner.key.empty() ||
            structure.blueprint.empty())
            return SetError(error, "Snapshot contains incomplete structure identity");
        if (!ids.insert(structure.structureId).second)
            return SetError(error, "Snapshot contains duplicate structure IDs");
    }

    try {
        std::error_code ec;
        if (!filePath_.parent_path().empty())
            std::filesystem::create_directories(filePath_.parent_path(), ec);
        if (ec) return SetError(error, "Unable to create snapshot directory: " + ec.message());
        const auto payload = SnapshotPayload(snapshot);
        const auto payloadText = payload.dump();
        if (payloadText.size() > maximumSnapshotBytes)
            return SetError(error, "Local snapshot exceeds the 128 MiB safety limit");
        Json envelope = {
            {"format", "arkland-structure-limits-snapshot"},
            {"crc32", Crc32(payloadText)},
            {"payload", payload}
        };
        WriteAtomically(filePath_, envelope.dump());
        if (error) error->clear();
        return true;
    } catch (const std::exception& e) {
        return SetError(error, e.what());
    }
}

SnapshotLoadResult LocalSnapshotStore::LoadCandidate() const {
    SnapshotLoadResult result;
    std::error_code ec;
    const auto temporaryPrefix = filePath_.filename().wstring() + L".";
    const auto parent = filePath_.parent_path().empty()
        ? std::filesystem::current_path() : filePath_.parent_path();
    const bool parentExists = std::filesystem::exists(parent, ec);
    if (ec) {
        result.error = "Unable to inspect snapshot directory: " + ec.message();
        return result;
    }
    if (!parentExists) return result;
    for (std::filesystem::directory_iterator it(parent, ec), end;
         !ec && it != end; it.increment(ec)) {
        const auto name = it->path().filename().wstring();
        if (it->is_regular_file() && name.starts_with(temporaryPrefix) &&
            it->path().extension() == L".tmp")
            result.interruptedWriteFound = true;
    }
    if (ec) {
        result.error = "Unable to inspect snapshot directory: " + ec.message();
        return result;
    }
    const bool snapshotExists = std::filesystem::exists(filePath_, ec);
    if (ec) {
        result.error = "Unable to inspect snapshot path: " + ec.message();
        return result;
    }
    if (!snapshotExists) {
        if (result.interruptedWriteFound)
            result.error = "Snapshot is missing and an interrupted temporary write was found";
        return result;
    }
    result.found = true;
    try {
        const auto size = std::filesystem::file_size(filePath_);
        if (size > maximumSnapshotBytes)
            throw std::runtime_error("Local snapshot exceeds the 128 MiB safety limit");
        const auto envelope = Json::parse(ReadFile(filePath_));
        if (!envelope.is_object() || envelope.value("format", std::string{}) !=
                "arkland-structure-limits-snapshot" || !envelope.contains("payload") ||
            !envelope.contains("crc32"))
            throw std::runtime_error("Local snapshot envelope is invalid");
        const auto payload = envelope.at("payload");
        if (Crc32(payload.dump()) != envelope.at("crc32").get<std::uint32_t>())
            throw std::runtime_error("Local snapshot checksum does not match");
        if (!payload.is_object() ||
            payload.at("schema_version").get<std::uint32_t>() != schemaVersion)
            throw std::runtime_error("Unsupported local snapshot schema version");

        const auto& map = payload.at("map");
        MapIdentity candidateMap{
            map.at("display_id").get<std::string>(),
            map.at("canonical_instance_path").get<std::string>()
        };
        if (candidateMap.displayId != expectedMap_.displayId ||
            candidateMap.canonicalInstancePath != expectedMap_.canonicalInstancePath)
            throw std::runtime_error("Local snapshot belongs to a different map instance");

        WorldSnapshot candidate;
        candidate.map = std::move(candidateMap);
        candidate.complete = false;
        candidate.validated = false;
        candidate.placementHookValidated = false;
        const auto& structures = payload.at("structures");
        if (!structures.is_array())
            throw std::runtime_error("Local snapshot structures field is not an array");
        std::set<std::string> ids;
        for (const auto& item : structures) {
            ExistingStructure structure;
            structure.structureId = item.at("structure_id").get<std::string>();
            structure.owner.key = item.at("owner_key").get<std::string>();
            structure.owner.tribeId = item.at("tribe_id").get<std::string>();
            structure.owner.steamId = item.at("steam_id").get<std::string>();
            structure.blueprint = item.at("blueprint").get<std::string>();
            if (structure.structureId.empty() || structure.owner.key.empty() ||
                structure.blueprint.empty() || !ids.insert(structure.structureId).second)
                throw std::runtime_error("Local snapshot contains invalid/duplicate structure identity");
            candidate.structures.push_back(std::move(structure));
        }
        result.candidate = std::move(candidate);
        result.usable = true;
        result.error = result.interruptedWriteFound
            ? "A temporary snapshot write was interrupted; the validated snapshot is still available"
            : std::string{};
    } catch (const std::exception& e) {
        result.error = e.what();
    }
    return result;
}

} // namespace StructureLimits
