# Changelog

All notable changes to the Blender ↔ Unreal Bridge project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [Milestone 4] - 2026-10-05

### Added
- `unreal_plugin/Source/BlenderUnrealBridge/Public/Core/BridgeDiagnostics.h` — Diagnostic severity levels (`EBridgeDiagnosticLevel`), structured messages (`FBridgeDiagnosticMessage`), and reports (`FBridgeValidationReport`).
- `unreal_plugin/Source/BlenderUnrealBridge/Public/Core/BridgeDataModel.h` — Unreal C++ data representations for manifest, scene, objects, and canonical transforms (`FBridgeManifest`, `FBridgeScene`, `FBridgeObject`, `FBridgeCanonicalTransform`, `FBridgePackageData`).
- `unreal_plugin/Source/BlenderUnrealBridge/Public/Core/BridgeTransformConverter.h` & `Private/Core/BridgeTransformConverter.cpp` — Authoritative Unreal-side transform converter:
  - Canonical location $[x, y, z]$ (cm) → Unreal `FVector`
  - Canonical unit quaternion $[x, y, z, w]$ → Unreal `FQuat` & `FRotator`
  - Canonical scale $[sx, sy, sz]$ → Unreal `FVector` with negative reflection preservation
  - Local transform `FTransform` construction
  - Parent-child world transform composition: `WorldTransform = LocalTransform * ParentWorldTransform`
- `unreal_plugin/Source/BlenderUnrealBridge/Public/Reader/BridgePackageValidator.h` & `Private/Reader/BridgePackageValidator.cpp` — Full package validator enforcing:
  - Format (`BUBRIDGE`) and version compatibility (v0.1.x)
  - Canonical coordinate axes and units (Z-Up, X-Forward, Y-Right, left_handed, centimeter)
  - Bridge ID format (`obj_<hex>`) and strict uniqueness
  - Referential hierarchy integrity (no broken parents, no self-parenting, cycle detection)
  - Finite floating-point transform validation
- `unreal_plugin/Source/BlenderUnrealBridge/Public/Reader/BridgePackageReader.h` & `Private/Reader/BridgePackageReader.cpp` — Public package reader API:
  - `LoadPackage()`: Verifies filesystem structure, parses `manifest.json`, `scene.json`, `objects.json` using Unreal JSON APIs, validates metadata, and builds package data.
  - `GetUnrealLocalTransform()`: Evaluates native Unreal local `FTransform`.
  - `GetUnrealWorldTransform()`: Computes accumulated native Unreal world `FTransform` across hierarchy.
- `scripts/generate_test_fixtures.py` — Deterministic test fixture generator producing 13 `.bubridge` fixtures covering valid and malformed edge cases.
- `test_assets/fixtures/` — 13 deterministic `.bubridge` test packages.
- `unreal_plugin/Tests/test_unreal_package_reader.py` — 14-test engine-independent automated test suite covering all fixtures, transform math, and Milestone 3 integration.

### Validation Status (Milestone 4)
- **Engine-Independent Tests (`test_unreal_package_reader.py`)**: **14/14 PASSED** (0 failures, 0 errors in 0.139s).
  - Fixtures 01-07 (identity, translation, rotation, scale, negative scale, parent-child, deep hierarchy): **PASSED**
  - Fixtures 08-13 (invalid manifest, duplicate ID, broken parent, hierarchy cycle, invalid transform, unsupported version): **PASSED**
  - Milestone 3 Integration (`DemoScene.bubridge`): **PASSED** with exact transform matching (parent locator at $(200, 100, 300)$ cm, child mesh world at $(200, 100, 400)$ cm).
- **Blender 4.5.3 LTS Runtime Verification**:
  - `test_package_serialization.py`: **11/11 PASSED**
  - `test_transforms.py`: **54/54 PASSED**
  - `test_scene_collector.py`: **22/22 PASSED**
  - `test_addon_registration.py`: **2/2 PASSED**
  - **Total Blender Tests**: **89/89 PASSED** (0 failures, 0 errors in 0.117s)
- **Bridge Core C++ (MSVC 2022 via CMake)**:
  - `VersionTest`: **1/1 PASSED** (0 errors, 0 warnings)
- **Unreal Engine 5.8 Build Tool (UBT) Compilation**:
  - Compiler: MSVC 14.44.35229 toolchain / Windows 10.0.22621.0 SDK via .NET 10.0.401 runtime.
  - Target: `UE_Bridge_UBT_TestEditor` (Win64 Development).
  - Result: **Compilation Succeeded (0 errors, 0 warnings)**.
  - Output Binaries: `UnrealEditor-BlenderUnrealBridge.dll` (199 KB), `UnrealEditor-BlenderUnrealBridge.pdb`, `UnrealEditor.modules`.

## [Milestone 3] - 2026-10-05

### Added
- `blender_addon/blender_unreal_bridge/serialization/__init__.py` — `serialization` package public API exports.
- `blender_addon/blender_unreal_bridge/serialization/json_serializer.py` — Safe, strict JSON serializer with finite float enforcement and custom mathutils encoding.
- `blender_addon/blender_unreal_bridge/serialization/package_validator.py` — Pre-write package validator checking:
  - Manifest correctness (version, format, coordinate system, units)
  - Stable Bridge ID format and uniqueness
  - Referential integrity (parent ID existence, self-parenting check, and cycle detection)
  - Transform schema validity and finite numerical values
  - Collection hierarchy consistency
  - Structured diagnostic reporting conforming to `DATA_PROTOCOL.md` §5 (`report.json`)
- `blender_addon/blender_unreal_bridge/serialization/package_writer.py` — Atomic `.bubridge` package writer:
  - Consumes Scene Collector metadata and canonical Milestone 2 transforms
  - Deterministically sorts objects by Bridge ID and collections by Collection ID
  - Generates schema-compliant `manifest.json`, `scene.json`, `objects.json`, `metadata/report.json`
  - Creates empty payload directories `meshes/`, `textures/`
  - Atomic writing via staging directory to prevent partial/corrupted output
  - High-level public export API: `build_package_data()`, `write_bridge_package()`, `create_bridge_package()`
- `blender_addon/blender_unreal_bridge/__init__.py` — Extended UI with `BUBRIDGE_OT_export_package` operator and "Export Package" panel button.
- `blender_addon/tests/test_package_serialization.py` — 11-test comprehensive suite covering:
  - Package directory structure and required files/directories
  - Manifest schema compliance and dynamic environment extraction
  - Scene and collection hierarchy serialization
  - Object metadata, stable Bridge IDs, and deterministic ordering
  - Canonical transform serialization (Milestone 2 integration)
  - Negative scale flag preservation
  - Parent/child relationships and deep hierarchies
  - Determinism (two exports produce identical byte-for-byte JSON)
  - JSON validity (strict parsing, no NaN/Infinity)
  - PackageValidator error detection (duplicate IDs, broken parents, cycles)
  - Atomic writing and cleanup on failure

### Validation Status (Milestone 3)
- **Blender 4.5.3 LTS Runtime Verification**:
  - `test_package_serialization.py`: **11/11 PASSED** (0 failures, 0 errors in 0.085s)
  - `test_transforms.py`: **54/54 PASSED** (0 failures, 0 errors in 0.021s)
  - `test_scene_collector.py`: **22/22 PASSED** (0 failures, 0 errors in 0.019s)
  - `test_addon_registration.py`: **2/2 PASSED** (0 failures, 0 errors in 0.000s)
  - **Total Blender Tests**: **89/89 PASSED** (0 failures, 0 errors)
- **Bridge Core C++ (MSVC 2022 via CMake)**:
  - `VersionTest`: **1/1 PASSED** (0 errors, 0 warnings)

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

