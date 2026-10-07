# Blender ↔ Unreal Bridge: Development Guide & Workflow

## 1. Development Philosophy & AI Rules

To ensure stability, maintainability, and clean architecture, all development on the **Blender ↔ Unreal Bridge** must follow these core principles:

1. **Build the Smallest Reliable Bridge First**: Prioritize correctness and stability over breadth of features.
2. **Never Rewrite Working Modules Unnecessarily**: Refactor surgically when needed; preserve stable, tested code.
3. **Semantic Translation, Not Transpilation**: Never attempt direct node-to-node mapping. Translate DCC concepts into canonical semantic descriptions.
4. **Never Fail Silently**: Always capture edge cases and unsupported nodes, emitting clear `INFO`, `WARNING`, or `ERROR` messages.
5. **Single Authoritative Transform Location**: Coordinate conversions must occur in exactly one controlled module, never scattered across the codebase.
6. **No Premature Optimization or Bloat**: Introduce directories and files progressively as features are implemented. Do not generate empty or unused boilerplates.
7. **Strict Separation of Concerns**: Keep Blender-specific logic in `blender_addon/`, Unreal-specific logic in `unreal_plugin/`, and shared schemas/math in `bridge_core/`.

---

## 2. Milestone Roadmap

Development is organized sequentially into discrete milestones. Each milestone must pass its verification criteria before proceeding to the next.

| Milestone | Title | Focus Area | Deliverables | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Milestone 0** | **Project Skeleton** | Repository Foundation | Directory skeletons, basic module files, build setup, CI test runners. | ✅ Complete |
| **Milestone 1** | **Scene Inspection** | Blender Add-on Collector | Traversal of Blender scenes, object tagging with stable `bubridge_id`, collection membership. | ✅ Complete |
| **Milestone 2** | **Transform System** | Canonical Transforms | Authoritative coordinate conversion (Blender RH Z-up $\rightarrow$ Canonical LH Z-up), unit scaling. | ✅ Complete |
| **Milestone 3** | **Bridge Package** | Package Serializer/Validator | v0.1.0 JSON schemas (`manifest`, `scene`, `objects`), determinism, serialization validation. | ✅ Complete |
| **Milestone 4** | **Unreal Reader** | Unreal Ingestion Skeleton | Unreal C++ plugin, package parser, manifest validation, logging. | ✅ Complete |
| **Milestone 5** | **Static Mesh Pipeline** | Geometry Transfer | Mesh export/import, vertex buffers, UVs, normals, multiple objects and instances. | ✅ Complete |
| **Milestone 6** | **PBR Material Translator** | Semantic Materials | Principled BSDF analyzer, fallback handling, Unreal dynamic material builder. | ✅ Complete |
| **Milestone 7** | **Textures & UVs** | Texture Pipeline | Image discovery, path resolution, sRGB/Linear validation, packing, UV slot assignment. | ✅ Complete |
| **Milestone 8** | **Hierarchy & Validation** | Outliner & Verification | Full parent-child hierarchy reconstruction, collection folders, error reporting. | ✅ Complete |
| **Milestone 9** | **Animation Pipeline** | Skeletal & Keyframe Data | Skeletal mesh export, skinning weights, bone hierarchies, animation clips. | ⏳ Next |
| **Milestone 10** | **Live Synchronization** | Real-Time Sync Layer | Socket/IPC delta transport, transform sync, live editing in Blender reflected in Unreal. | ⏳ Planned |

---

## 3. Environment Setup

### 3.1 Blender Add-on Development
* **Blender Version**: Blender 4.2+ LTS (compatible with 4.x / 5.x).
* **Python Runtime**: Blender's embedded Python (Python 3.10+ / 3.11+).
* **Local Testing**:
  * Run headless tests via Blender command line:
    ```bash
    blender --background --python blender_addon/blender_unreal_bridge/tests/run_tests.py
    ```
  * Or install the add-on in developer mode by symlinking `blender_addon/blender_unreal_bridge` into Blender's `scripts/addons` folder.

### 3.2 Bridge Core Development
* **Compiler**: Standard C++17 or C++20 compliant compiler (MSVC 2022 on Windows, Clang/GCC on Linux/macOS).
* **Build System**: CMake 3.22+.
* **Build Command**:
  ```bash
  cmake -B build -S bridge_core
  cmake --build build --config Release
  ctest --test-dir build --output-on-failure
  ```

### 3.3 Unreal Engine Plugin Development
* **Unreal Engine Version**: Unreal Engine 5.3+ (5.4 / 5.5 compatible).
* **Plugin Type**: Editor Module (`Type: "Editor"` in `.uplugin`).
* **Installation**:
  * Copy or symlink `unreal_plugin/` into `<YourUnrealProject>/Plugins/BlenderUnrealBridge`.
  * Generate Visual Studio project files and compile within Unreal Build Tool (UBT).

---

## 4. Testing & Verification Strategy

### 4.1 Unit Testing
* **Blender Add-on**:
  * Tested using Python's `unittest` suite executed inside Blender's python runtime.
  * Test matrix:
    - ID generation stability & persistence across file reloads.
    - Transform calculation with identity, translation, rotation, non-uniform scaling, and negative scaling.
    - Material node analyzer under standard Principled BSDF configurations and unsupported node graphs.
* **Bridge Core**:
  * C++ unit tests covering JSON serialization, coordinate conversion math, and manifest validation.

### 4.2 Standard Test Scenes (`test_assets/`)
Every capability must be verified against dedicated, minimal test scenes:

1. **`basic_mesh`**:
   - Single standard unit cube centered at origin.
   - Sphere, cylinder, and non-uniform mesh.
2. **`transforms_hierarchy`**:
   - Rotated parent empty with scaled children.
   - Negative scale mirrored object (verifies normal/winding correction).
3. **`pbr_materials`**:
   - Material 1: Constant Base Color + Roughness + Metallic.
   - Material 2: Textures mapped to Base Color, Roughness, Normal.
   - Material 3: Unsupported procedural node graph (verifies fallback and warning generation).
4. **`multi_object_scene`** (MVP Acceptance Scene):
   - House, Tree, Rock, Ground, Light.
   - Preserves relative positions, scale, rotations, mesh geometry, UVs, and materials.

---

## 5. Development Workflow Rules

1. **Before Implementing a Milestone**:
   - Review `PROJECT_SPEC.md`, `ARCHITECTURE.md`, and `DATA_PROTOCOL.md`.
   - Formulate a surgical, step-by-step implementation plan.
   - Only create files required for the immediate milestone.
2. **During Implementation**:
   - Maintain documentation integrity and preserve comments.
   - Never hardcode absolute paths; use package-relative paths.
   - Always run unit tests after code modifications.
3. **Commit & Verification**:
   - Check against the milestone success criteria.
   - Document any known limitations, warnings, or discovered edge cases in `CHANGELOG.md`.
