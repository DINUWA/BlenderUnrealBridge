# Changelog

All notable changes to the Blender ↔ Unreal Bridge project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-10-05

### Added
- Authoritative documentation suite:
  - `PROJECT_SPEC.md`
  - `ARCHITECTURE.md`
  - `DATA_PROTOCOL.md`
  - `DEVELOPMENT.md`
  - `AGENTS.md`
- Git repository initialization and `.gitignore`.
- **Milestone 0: Repository Foundation**:
  - Blender add-on skeleton in `blender_addon/blender_unreal_bridge/` with `bl_info`, operator, and sidebar UI panel.
  - Blender headless registration unit test in `blender_addon/tests/test_addon_registration.py`.
  - Bridge Core C++ library skeleton and CMake build setup in `bridge_core/`.
  - Bridge Core version header, implementation, and unit test in `bridge_core/tests/test_version.cpp`.
  - Unreal Engine Editor plugin skeleton in `unreal_plugin/` (`BlenderUnrealBridge.uplugin`, `Build.cs`, module interface).

### Validation Status (Milestone 0)
- **Bridge Core**: Built cleanly with MSVC 2022 via CMake; 100% of unit tests (`VersionTest`) passed with 0 errors and 0 warnings.
- **Blender Add-on**: Unit test suite created for execution within Blender's embedded Python runtime (`bpy`). Verified that running outside Blender triggers the required runtime isolation guard. Full headless test execution pending Blender installation.
- **Unreal Plugin**: Structurally validated skeleton adhering to Unreal Engine 5.x plugin standards. Reported as structurally validated but not compiled due to the absence of a complete Unreal Engine installation with Unreal Build Tool (UBT).

