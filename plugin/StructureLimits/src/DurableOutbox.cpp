#include "DurableOutbox.h"

#include <algorithm>
#include <fstream>
#include <iterator>
#include <stdexcept>

#ifdef _WIN32
#define NOMINMAX
#include <Windows.h>
#endif

namespace StructureLimits {
namespace {

std::string ReadFile(const std::filesystem::path& path) {
    std::ifstream input(path, std::ios::binary);
    if (!input) throw std::runtime_error("Unable to read outbox event");
    return std::string(std::istreambuf_iterator<char>(input),
                       std::istreambuf_iterator<char>());
}

bool SetError(std::string* error, const std::string& message) {
    if (error) *error = message;
    return false;
}

} // namespace

DurableOutbox::DurableOutbox(std::filesystem::path directory)
    : directory_(std::move(directory)) {
    if (directory_.empty()) throw std::invalid_argument("Outbox directory is required");
}

void DurableOutbox::Initialize() {
    std::error_code ec;
    std::filesystem::create_directories(directory_, ec);
    if (ec) throw std::runtime_error("Unable to create outbox directory: " + ec.message());
    if (!std::filesystem::is_directory(directory_))
        throw std::runtime_error("Outbox path is not a directory");
}

bool DurableOutbox::IsSafeEventId(const std::string& eventId) {
    if (eventId.empty() || eventId.size() > 128) return false;
    return std::all_of(eventId.begin(), eventId.end(), [](unsigned char c) {
        return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
               (c >= '0' && c <= '9') || c == '-' || c == '_';
    });
}

std::filesystem::path DurableOutbox::EventPath(const std::string& eventId) const {
    return directory_ / (eventId + ".evt");
}

bool DurableOutbox::Enqueue(const std::string& eventId,
                            const std::string& payload,
                            std::string* error) {
    if (!IsSafeEventId(eventId))
        return SetError(error, "Event ID contains unsupported characters");
    const auto destination = EventPath(eventId);
    std::error_code ec;
    const bool destinationExists = std::filesystem::exists(destination, ec);
    if (ec) return SetError(error, "Unable to inspect existing outbox event");
    if (destinationExists) {
        try {
            if (ReadFile(destination) == payload) {
                if (error) error->clear();
                return true;
            }
        } catch (const std::exception& e) {
            return SetError(error, e.what());
        }
        return SetError(error, "Event ID already exists with different payload");
    }

#ifdef _WIN32
    static volatile LONG tempSequence = 0;
    std::filesystem::path temporary;
    HANDLE file = INVALID_HANDLE_VALUE;
    for (int attempt = 0; attempt < 32 && file == INVALID_HANDLE_VALUE; ++attempt) {
        const auto sequence = InterlockedIncrement(&tempSequence);
        temporary = directory_ / (eventId + "." + std::to_string(sequence) + ".tmp");
        file = CreateFileW(temporary.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_NEW,
                           FILE_ATTRIBUTE_NORMAL, nullptr);
        if (file == INVALID_HANDLE_VALUE && GetLastError() != ERROR_FILE_EXISTS &&
            GetLastError() != ERROR_ALREADY_EXISTS)
            return SetError(error, "Unable to create outbox temporary file");
    }
    if (file == INVALID_HANDLE_VALUE)
        return SetError(error, "Unable to allocate unique outbox temporary file");

    std::size_t offset = 0;
    bool written = payload.size() <= static_cast<std::size_t>(MAXDWORD);
    while (written && offset < payload.size()) {
        DWORD bytesWritten = 0;
        const DWORD requested = static_cast<DWORD>(payload.size() - offset);
        written = WriteFile(file, payload.data() + offset, requested, &bytesWritten, nullptr)
            != 0 && bytesWritten != 0;
        offset += bytesWritten;
    }
    if (written) written = FlushFileBuffers(file) != 0;
    CloseHandle(file);
    if (!written) {
        DeleteFileW(temporary.c_str());
        return SetError(error, "Unable to durably write outbox event");
    }
    if (!MoveFileExW(temporary.c_str(), destination.c_str(), MOVEFILE_WRITE_THROUGH)) {
        const DWORD moveError = GetLastError();
        DeleteFileW(temporary.c_str());
        if ((moveError == ERROR_ALREADY_EXISTS || moveError == ERROR_FILE_EXISTS) &&
            std::filesystem::exists(destination, ec) && !ec) {
            try {
                if (ReadFile(destination) == payload) {
                    if (error) error->clear();
                    return true;
                }
            } catch (const std::exception& e) {
                return SetError(error, e.what());
            }
            return SetError(error, "Event ID already exists with different payload");
        }
        return SetError(error, "Unable to atomically publish outbox event");
    }
#else
    (void)payload;
    return SetError(error, "Durable outbox currently supports Windows only");
#endif
    if (error) error->clear();
    return true;
}

std::vector<OutboxEvent> DurableOutbox::Pending(std::string* error) const {
    std::vector<std::filesystem::path> paths;
    bool interruptedWriteFound = false;
    std::error_code ec;
    for (std::filesystem::directory_iterator it(directory_, ec), end;
         !ec && it != end; it.increment(ec)) {
        if (it->is_regular_file() && it->path().extension() == ".evt")
            paths.push_back(it->path());
        else if (it->is_regular_file() && it->path().extension() == ".tmp")
            interruptedWriteFound = true;
    }
    if (ec) {
        if (error) *error = "Unable to enumerate outbox: " + ec.message();
        return {};
    }
    std::sort(paths.begin(), paths.end());
    std::vector<OutboxEvent> events;
    try {
        for (const auto& path : paths)
            events.push_back({path.stem().string(), ReadFile(path)});
    } catch (const std::exception& e) {
        if (error) *error = e.what();
        return {};
    }
    if (error) {
        *error = interruptedWriteFound
            ? "Outbox contains interrupted temporary files; preserve and investigate"
            : std::string{};
    }
    return events;
}

bool DurableOutbox::Acknowledge(const std::string& eventId, std::string* error) {
    if (!IsSafeEventId(eventId))
        return SetError(error, "Event ID contains unsupported characters");
    std::error_code ec;
    const bool removed = std::filesystem::remove(EventPath(eventId), ec);
    if (ec) return SetError(error, "Unable to acknowledge outbox event: " + ec.message());
    if (!removed) return SetError(error, "Outbox event does not exist");
    if (error) error->clear();
    return true;
}

} // namespace StructureLimits
