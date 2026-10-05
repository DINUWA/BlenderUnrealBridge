#include "bridge_core/version.h"

namespace bubridge {

const char* GetVersionString() noexcept {
    return BUBRIDGE_VERSION_STRING;
}

const char* GetFormatName() noexcept {
    return BUBRIDGE_FORMAT_NAME;
}

int GetVersionMajor() noexcept {
    return BUBRIDGE_VERSION_MAJOR;
}

int GetVersionMinor() noexcept {
    return BUBRIDGE_VERSION_MINOR;
}

int GetVersionPatch() noexcept {
    return BUBRIDGE_VERSION_PATCH;
}

bool IsFormatCompatible(const std::string& formatName, int majorVersion, int /*minorVersion*/) noexcept {
    if (formatName != BUBRIDGE_FORMAT_NAME) {
        return false;
    }
    // Major version must match exactly for compatibility
    return majorVersion == BUBRIDGE_VERSION_MAJOR;
}

} // namespace bubridge
