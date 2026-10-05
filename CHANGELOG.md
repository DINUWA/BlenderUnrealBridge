# Changelog

All notable changes to the Blender ↔ Unreal Bridge project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [Milestone 2] - 2026-10-05

### Added
- `blender_addon/blender_unreal_bridge/transforms/__init__.py` — `transforms` package marker.
- `blender_addon/blender_unreal_bridge/transforms/canonical.py` — Authoritative Blender-to-Bridge transform conversion module.
  - Implements canonical axis conversion: Blender +Y (forward) → Bridge +X, Blender +X (right) → Bridge +Y, +Z (up) shared.
  - Implements canonical unit scaling: Meters → Centimeters (factor 100.0).
  - Implements quaternion rotation conversion with handedness basis transformation: `(w, x, y, z)` → `[y, x, -z, w]`.
  - Implements scale conversion with axis swap and negative scale / reflection preservation (`has_negative_scale` flag).
  - Extracts local parent-relative transforms without precision loss or matrix decomposition artifacts.
  - Handles all Blender rotation modes (`QUATERNION`, `AXIS_ANGLE`, and Euler modes `XYZ`, `XZY`, `YXZ`, `YZX`, `ZXY`, `ZYX`).
  - Emits non-fatal warnings for `AXIS_ANGLE` and negative scale winding notifications.
  - Defines `TransformData` conforming strictly to `DATA_PROTOCOL.md` `transform` schema.
- `blender_addon/tests/test_transforms.py` — 54-test comprehensive suite covering:
  - Identity transform
  - Translations (single axis, combined, unit conversion 1 BU = 100 cm)
  - Rotations (X/Y/Z Euler, Quaternion mode, all 6 Euler orders, identity in any mode)
  - Scale (uniform, non-uniform, single/double negative scale reflection flags)
  - Hierarchy (relative parent/child offsets, 3-level deeply nested hierarchies, root objects)
  - Axis angle warning generation
  - Arbitrary combined TRS transforms
  - Repeated extraction stability
  - Schema dictionary serialization
  - Scene collector transform integration
- `blender_addon/blender_unreal_bridge/collectors/scene_collector.py` — updated with optional `extract_transforms` parameter and `ObjectMetadata.transform` attribute, preserving 100% backward compatibility with Milestone 1.

### Validation Status (Milestone 2)
- **Blender 4.5.3 LTS Runtime Verification**:
  - `test_transforms.py`: **54/54 PASSED** (0 failures, 0 errors in 0.021s)
  - `test_scene_collector.py`: **22/22 PASSED** (0 failures, 0 errors in 0.019s)
  - `test_addon_registration.py`: **2/2 PASSED** (0 failures, 0 errors in 0.000s)
  - **Total Blender Tests**: **78/78 PASSED** (0 failures, 0 errors)
- **Bridge Core C++ (MSVC 2022 via CMake)**:
  - `VersionTest`: **1/1 PASSED** (0 errors, 0 warnings)

## [Milestone 1] - 2026-10-05

### Added
- `blender_addon/blender_unreal_bridge/collectors/__init__.py` — `collectors` package.
- `blender_addon/blender_unreal_bridge/collectors/id_generator.py` — Single authoritative module
  for `bubridge_id` generation and assignment. Exposes `ensure_id`, `get_id`, `has_id`,
  and the canonical `BUBRIDGE_ID_KEY` constant. No ID generation occurs anywhere else.
- `blender_addon/blender_unreal_bridge/collectors/scene_collector.py` — Scene Collector module.
  Traverses `bpy.context.scene.objects`, filters to supported types (`MESH`, `EMPTY`, `CURVE`),
  assigns stable `bubridge_id` values, extracts named collection membership, captures parent/child
  relationships by Bridge ID, and returns a `SceneInspectionResult`. Unsupported object types
  produce `INFO`-level messages rather than silent discard.
- `blender_addon/tests/test_scene_collector.py` — 21-test Milestone 1 suite (requires Blender runtime):
  empty scene, single object, multiple objects, collection membership, parent/child hierarchy,
  ID persistence, new object ID assignment, and unsupported type handling.
- `blender_addon/blender_unreal_bridge/__init__.py` — surgically extended:
  - Added `BUBRIDGE_OT_collect_scene` operator (calls `collect_scene`, reports results).
  - Extended sidebar panel with "Collect Scene" button under a "Scene Inspection" label.
  - All Milestone 0 code preserved intact.

### Validation Status (Milestone 1)
- **id_generator standalone tests (11 tests)**: All **PASSED** using host Python with mock objects.
  - ID format validation (`obj_` prefix, 8 hex chars)
  - 500-sample uniqueness check
  - `BUBRIDGE_ID_KEY` constant correctness
  - `ensure_id` assigns on first call, does not overwrite existing
  - `get_id` returns `None` when absent, correct value when present
  - `has_id` returns correct bool in both states
  - Multiple objects receive distinct IDs
  - Re-running `ensure_id` on same object returns identical ID
- **Blender runtime guard tests**: Both `test_addon_registration.py` and `test_scene_collector.py`
  correctly refused host-Python execution and printed the required error message.
- **Full scene collector tests (21 tests in `test_scene_collector.py`)**: Blocked — require
  Blender's embedded Python runtime. Must be run as:
  `blender --background --python blender_addon/tests/test_scene_collector.py`

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

