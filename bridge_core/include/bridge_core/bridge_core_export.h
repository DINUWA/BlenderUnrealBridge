#pragma once

#if defined(_WIN32) || defined(__CYGWIN__)
    #if defined(BRIDGE_CORE_STATIC)
        #define BRIDGE_CORE_API
    #elif defined(BRIDGE_CORE_EXPORTS)
        #define BRIDGE_CORE_API __declspec(dllexport)
    #else
        #define BRIDGE_CORE_API __declspec(dllimport)
    #endif
#else
    #if defined(__GNUC__) && __GNUC__ >= 4
        #define BRIDGE_CORE_API __attribute__((visibility("default")))
    #else
        #define BRIDGE_CORE_API
    #endif
#endif
