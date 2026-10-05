#pragma once

#include "bridge_core_export.h"
#include <string>

#define BUBRIDGE_VERSION_MAJOR 0
#define BUBRIDGE_VERSION_MINOR 1
#define BUBRIDGE_VERSION_PATCH 0
#define BUBRIDGE_VERSION_STRING "0.1.0"
#define BUBRIDGE_FORMAT_NAME "BUBRIDGE"

namespace bubridge {

BRIDGE_CORE_API const char* GetVersionString() noexcept;
BRIDGE_CORE_API const char* GetFormatName() noexcept;
BRIDGE_CORE_API int GetVersionMajor() noexcept;
BRIDGE_CORE_API int GetVersionMinor() noexcept;
BRIDGE_CORE_API int GetVersionPatch() noexcept;
BRIDGE_CORE_API bool IsFormatCompatible(const std::string& formatName, int majorVersion, int minorVersion) noexcept;

} // namespace bubridge
