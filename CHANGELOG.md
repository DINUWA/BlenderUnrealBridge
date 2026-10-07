# Changelog

All notable changes to the Blender ↔ Unreal Bridge project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [Milestone 7] - 2026-10-07

### Added
- `blender_addon/blender_unreal_bridge/collectors/id_generator.py`:
  - Added `_generate_texture_id()`, `ensure_texture_id()`, `get_texture_id()`, and `has_texture_id()` to generate and maintain stable `tex_<8 hex chars>` on `bpy.types.Image` datablocks.
- `blender_addon/blender_unreal_bridge/materials/texture_extractor.py`:
  - Implemented semantic texture discovery and extraction supporting Base Color, Roughness, Metallic, and Normal Map channels.
  - Added support for direct socket links, reroute nodes, and `ShaderNodeNormalMap` connections.
  - Image path resolution supporting relative (`//`), absolute paths, and embedded packed images (`image.packed_file.data`).
  - Color space validation (`sRGB` for Base Color, `Linear`/`Non-Color` for Roughness, Metallic, Normal), emitting structured `TEX_COLORSPACE_MISMATCH` diagnostics.
  - Image metadata extraction: dimensions, channels, alpha channel detection, format detection, and compression setting mapping (`TC_Default` vs `TC_Normalmap`).
- `blender_addon/blender_unreal_bridge/materials/material_extractor.py`:
  - Updated `extract_material_data()` to trace connected textures and populate the canonical `"textures"` map (`{"base_color": "tex_...", ...}`) while preserving all constant fallback PBR values.
- `blender_addon/blender_unreal_bridge/serialization/package_writer.py`:
  - Collected unique textures during scene traversal and serialized `textures.json` conforming to `BUBRIDGE_TEXTURES` v0.1.0.
  - Implemented atomic extraction/copying of texture files into `<package>/textures/<tex_id>.<ext>`.
  - Populated `manifest.content_summary.texture_count`.
- `blender_addon/blender_unreal_bridge/serialization/package_validator.py`:
  - Added `TEXTURE_ID_PATTERN` (`^tex_[0-9a-f]{8,16}$`).
  - Added `validate_texture()` verifying ID format, relative path, dimensions, channels, and color space.
  - Enforced referential integrity between material texture references and the texture catalog (`MATERIAL_BROKEN_TEXTURE_REF`).
- `blender_addon/tests/test_texture_extractor.py`:
  - 10 unit and integration tests covering stable texture IDs, Base Color discovery, Normal Map nodes, Roughness/Metallic linear textures, missing files, packed images, deduplication, packaging, and M6 constant fallback regression.
- `unreal_plugin/Source/BlenderUnrealBridge/Public/Core/BridgeDataModel.h`:
  - Added `FBridgeTextureData` struct.
  - Extended `FBridgeMaterialData` with `Textures` map (`TMap<FString, FString>`).
  - Extended `FBridgePackageData` with `Textures` map (`TMap<FString, FBridgeTextureData>`) and `FindTextureById()`.
- `unreal_plugin/Source/BlenderUnrealBridge/Public/Reader/BridgePackageReader.h` & `Private/Reader/BridgePackageReader.cpp`:
  - Implemented `ParseTexture()` and `LoadTextures()` parsing `textures.json`.
  - Hooked texture loading into `LoadPackage()` and parsed `"textures"` field in `ParseMaterial()`.
- `unreal_plugin/Source/BlenderUnrealBridge/Public/Reader/BridgePackageValidator.h` & `Private/Reader/BridgePackageValidator.cpp`:
  - Implemented `IsValidTextureId()`, `ValidateTexture()`, and `ValidateTextures()`.
  - Hooked texture schema, on-disk file existence (`TEX_FILE_NOT_FOUND`), and material texture reference validation (`MATERIAL_BROKEN_TEXTURE_REF`) into `ValidatePackage()`.
- `unreal_plugin/Source/BlenderUnrealBridge/Public/Material/BridgeMaterialBuilder.h` & `Private/Material/BridgeMaterialBuilder.cpp`:
  - Extended dynamic material creation to import textures on demand via `FImageUtils::ImportFileAsTexture2D()`.
  - Configured sRGB and `TC_Normalmap` compression settings.
  - Implemented per-package texture caching to ensure deduplicated texture loading across materials.
  - Bound imported textures to dynamic material parameters (`BaseColorTexture`, `RoughnessTexture`, `MetallicTexture`, `NormalTexture`).
- `scripts/generate_test_fixtures.py`:
  - Extended fixture generator with texture payloads and automatic 1x1 valid PNG generation.
  - Added test fixtures 22 (`22_texture_payload`), 23 (`23_textured_material_payload`), 24 (`24_multi_texture_material`), 25 (`25_missing_texture_reference`), 26 (`26_missing_texture_file`), 27 (`27_invalid_texture_schema`), and 28 (`28_shared_texture_payload`).
- `unreal_plugin/Tests/test_unreal_package_reader.py`:
  - Expanded engine-independent test suite to 51 tests with validation coverage for fixtures 22-28 and dedicated `TestMilestone7TextureValidation`.
- `DATA_PROTOCOL.md`:
  - Formalized material `"textures"` map and `textures.json` schema specification.

### Verification
- Blender unit tests: 123/123 passed.
- Unreal engine-independent tests: 51/51 passed.
- Bridge Core C++ tests: 1/1 passed.
- Unreal Engine 5.8 UBT compilation: 0 errors, 0 warnings (`UnrealEditor-BlenderUnrealBridge.dll` built).

## [Milestone 6] - 2026-10-07

### Added
- `blender_addon/blender_unreal_bridge/collectors/id_generator.py`:
  - Added `_generate_material_id()`, `ensure_material_id()`, `get_material_id()`, and `has_material_id()` to generate and maintain stable `mat_<8 hex chars>` on `bpy.types.Material` datablocks.
- `blender_addon/blender_unreal_bridge/materials/__init__.py` & `material_extractor.py`:
  - `extract_material_data()` extracting semantic non-textured PBR properties from Blender materials conforming to `BUBRIDGE_MATERIAL` v0.1.0 and `PBR_METALLIC_ROUGHNESS`.
  - Principled BSDF node inspection extracting Base Color (RGBA), Metallic `[0.0, 1.0]`, Roughness `[0.0, 1.0]`, Specular `[0.0, 1.0]` (supporting both Blender 4.0+ "Specular IOR Level" and legacy "Specular"), IOR, Opacity, BlendMode, and TwoSided.
  - Fallback extraction for materials without node trees or legacy diffuse color configurations.
  - Automatic handling of Blender 4.2+ default `HASHED` blend method, mapping to `OPAQUE` when alpha $\ge 0.999$, and defaulting `two_sided` to `false` for game engine PBR conventions.
- `blender_addon/blender_unreal_bridge/geometry/mesh_extractor.py`:
  - Integrated material ID assignment: mesh material slots now resolve and record stable material IDs (`ensure_material_id(slot.material)`) instead of placeholder strings.
- `blender_addon/blender_unreal_bridge/serialization/package_validator.py`:
  - Added `MATERIAL_ID_PATTERN` (`^mat_[0-9a-f]{8}$`).
  - Added `validate_material()` validating format, model, finite color ranges `[0.0, 1.0]`, metallic, roughness, and specular bounds.
  - Updated `validate_package()` to validate materials and enforce slot referential integrity (`OBJECT_BROKEN_MATERIAL_REF`, `MESH_BROKEN_MATERIAL_REF`).
- `blender_addon/blender_unreal_bridge/serialization/package_writer.py`:
  - Extracted referenced materials into `materials_dict`.
  - Serialized individual atomic files `materials/<material_id>.json`.
  - Populated `content_summary.material_count` in `manifest.json`.
  - Passed materials to validator during atomic package writing.
- `blender_addon/tests/test_material_extractor.py`:
  - 15 unit and integration tests covering material ID stability, Principled BSDF extraction, fallback handling, blend modes, slot integration, package serialization, and validation.
- `unreal_plugin/Source/BlenderUnrealBridge/Public/Core/BridgeDataModel.h`:
  - Added `FBridgeMaterialData` representing canonical PBR material properties.
  - Updated `FBridgePackageData` with `Materials` map (`TMap<FString, FBridgeMaterialData>`) and `FindMaterialById()`.
- `unreal_plugin/Source/BlenderUnrealBridge/Public/Reader/BridgePackageValidator.h` & `Private/Reader/BridgePackageValidator.cpp`:
  - Implemented `IsValidMaterialId()`, `ValidateMaterial()`, `ValidateMaterials()`, and hooked material validation and slot referential checks into `ValidatePackage()`.
- `unreal_plugin/Source/BlenderUnrealBridge/Public/Reader/BridgePackageReader.h` & `Private/Reader/BridgePackageReader.cpp`:
  - Implemented `ParseMaterial()`, `LoadMaterials()`, and added step 6 in `LoadPackage()` to deserialize `materials/*.json`.
- `unreal_plugin/Source/BlenderUnrealBridge/Public/Material/BridgeMaterialBuilder.h` & `Private/Material/BridgeMaterialBuilder.cpp`:
  - Implemented `FBridgeMaterialBuilder::CreateMaterial()` creating native `UMaterialInstanceDynamic` from `FBridgeMaterialData` with parameters for BaseColor, Metallic, Roughness, Specular, Opacity, and IOR.
  - Implemented `FBridgeMaterialBuilder::CreateMaterialsForPackage()`.
- `unreal_plugin/Source/BlenderUnrealBridge/Public/Mesh/BridgeMeshBuilder.h` & `Private/Mesh/BridgeMeshBuilder.cpp`:
  - Updated `FBridgeMeshBuilder::CreateStaticMesh()` to accept an optional `MaterialMap` and assign `UMaterialInterface` to mesh material slots both on the `FStaticMaterial` descriptor and `UStaticMesh::SetMaterial()`.
- `scripts/generate_test_fixtures.py`:
  - Extended fixture generator to output `materials/<material_id>.json` payloads.
  - Added fixtures 17 (`17_material_payload`), 18 (`18_multi_material_payload`), 19 (`19_broken_material_ref`), 20 (`20_invalid_pbr_value`), 21 (`21_invalid_material_schema`).
- `unreal_plugin/Tests/test_unreal_package_reader.py`:
  - Expanded test suite from 24 to 37 tests, adding validation for fixtures 17-21 and dedicated `TestMilestone6MaterialValidation`.

### Verification
- Blender unit tests: 113/113 passed.
- Unreal engine-independent tests: 37/37 passed.
- Bridge Core C++ tests: 1/1 passed.
- Unreal Engine 5.8 UBT compilation: 0 errors, 0 warnings (`UnrealEditor-BlenderUnrealBridge.dll` built).

## [Milestone 5] - 2026-10-07

### Added
- `blender_addon/blender_unreal_bridge/geometry/__init__.py` & `mesh_extractor.py`:
  - `extract_mesh_data()` non-destructive static mesh extractor.
  - Evaluation of evaluated meshes (`to_mesh()`) without modifying source Blender objects.
  - Canonical coordinate transformation (Left-Handed, Z-Up, Centimeters: $X_{canon} = Y_{blender} \times 100$, $Y_{canon} = X_{blender} \times 100$, $Z_{canon} = Z_{blender} \times 100$).
  - Normal direction conversion and unit normalization ($Nx_{canon} = Ny_{blender}$, $Ny_{canon} = Nx_{blender}$, $Nz_{canon} = Nz_{blender}$).
  - Flipped triangle winding order (`v0, v2, v1`) for Unreal left-handed space.
  - Extraction of active UV layer to per-triangle corner coordinates.
  - Extraction and mapping of material slots to triangle indices.
- `blender_addon/blender_unreal_bridge/collectors/id_generator.py`:
  - `ensure_mesh_id()`, `get_mesh_id()`, `_generate_mesh_id()` generating stable `mesh_<8 hex chars>` on `bpy.types.Mesh` datablocks.
  - Mesh deduplication: multiple objects sharing one mesh datablock reference the same mesh ID.
- `blender_addon/blender_unreal_bridge/serialization/package_writer.py`:
  - `build_package_data()` extracts unique meshes, populates `mesh_reference` and `material_slots` on `objects.json`.
  - Serializes `meshes/<mesh_id>.json` files adhering to `BUBRIDGE_MESH v0.1.0`.
  - Accurately tracks `content_summary.mesh_count` in `manifest.json`.
- `blender_addon/blender_unreal_bridge/serialization/package_validator.py`:
  - `validate_mesh()` for canonical mesh format, IDs, vertices, triangles, and material slots.
  - Referential integrity validation verifying that all object `mesh_reference`s resolve to existing mesh assets.
- `blender_addon/tests/test_mesh_extractor.py`:
  - 9 comprehensive unit tests verifying cube extraction, coordinates, normals, winding order, UVs, material slots, deduplication, non-destructive behavior, and determinism.
- `unreal_plugin/Source/BlenderUnrealBridge/Public/Core/BridgeDataModel.h`:
  - Data structs: `FBridgeMeshReference`, `FBridgeMaterialSlot`, `FBridgeMeshTriangle`, `FBridgeMeshBounds`, `FBridgeMeshData`.
  - Updated `FBridgeObject` with `MeshReference` and `MaterialSlots`.
  - Updated `FBridgePackageData` with `Meshes` map (`TMap<FString, FBridgeMeshData>`) and `FindMeshById()`.
- `unreal_plugin/Source/BlenderUnrealBridge/Private/Reader/BridgePackageValidator.cpp`:
  - `IsValidMeshId()`, `ValidateMesh()`, `ValidateMeshes()` enforcing referential integrity, finite attributes, and valid triangle indices.
- `unreal_plugin/Source/BlenderUnrealBridge/Private/Reader/BridgePackageReader.cpp`:
  - Added step 5 in `LoadPackage()` to deserialize `meshes/*.json` via `LoadMeshes()` and `ParseMesh()`.
- `unreal_plugin/Source/BlenderUnrealBridge/Public/Mesh/BridgeMeshBuilder.h` & `Private/Mesh/BridgeMeshBuilder.cpp`:
  - `FBridgeMeshBuilder::CreateStaticMesh()` constructing native `UStaticMesh` from `FBridgeMeshData` using Unreal's `FMeshDescription` and `StaticMeshDescription` APIs.
  - Registers attributes, assigns vertex positions, material slots, triangles, vertex instances, normals, and UVs.
  - Calls `BuildFromMeshDescriptions()` for render and collision generation.
- `scripts/generate_test_fixtures.py`:
  - Extended fixture generator to output `meshes/<mesh_id>.json` payloads.
  - Added fixtures 14 (`14_mesh_payload`), 15 (`15_broken_mesh_ref`), 16 (`16_mesh_index_out_of_bounds`).
- `unreal_plugin/Tests/test_unreal_package_reader.py`:
  - Expanded test suite from 14 to 24 tests, adding validation for fixtures 14-16 and dedicated `TestMilestone5MeshValidation`.

### Validation Status (Milestone 5)
- **Blender 4.5.3 LTS Runtime Verification**:
  - `test_mesh_extractor.py`: **9/9 PASSED**
  - `test_package_serialization.py`: **11/11 PASSED**
  - `test_transforms.py`: **54/54 PASSED**
  - `test_scene_collector.py`: **22/22 PASSED**
  - `test_addon_registration.py`: **2/2 PASSED**
  - **Total Blender Tests**: **98/98 PASSED** (0 failures, 0 errors in 0.251s)
- **Engine-Independent Tests (`test_unreal_package_reader.py`)**:
  - **24/24 PASSED** (0 failures, 0 errors in 0.529s)
- **Bridge Core C++ (MSVC 2022 via CMake)**:
  - `VersionTest`: **1/1 PASSED** (0 errors, 0 warnings)
- **Unreal Engine 5.8 Build Tool (UBT) Compilation**:
  - Target: `UE_Bridge_UBT_TestEditor Win64 Development`
  - Modules added: `MeshDescription`, `StaticMeshDescription`
  - Compiler: MSVC 14.44.35229 / WinSDK 10.0.22621.0 via .NET 10.0.401
  - Result: **Compilation Succeeded (0 errors, 0 warnings)**
  - Output Binaries: `UnrealEditor-BlenderUnrealBridge.dll`

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

