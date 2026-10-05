cmake_minimum_required(VERSION 3.20)
project(BridgeCore VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Compiler warning settings
if(MSVC)
    add_compile_options(/W4 /permissive-)
else()
    add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Core static library
add_library(BridgeCore STATIC
    include/bridge_core/bridge_core_export.h
    include/bridge_core/version.h
    src/version.cpp
)

target_include_directories(BridgeCore PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)

target_compile_definitions(BridgeCore PUBLIC BRIDGE_CORE_STATIC)

# Testing
enable_testing()

add_executable(BridgeCoreTests
    tests/test_version.cpp
)

target_link_libraries(BridgeCoreTests PRIVATE BridgeCore)

add_test(NAME VersionTest COMMAND BridgeCoreTests)
