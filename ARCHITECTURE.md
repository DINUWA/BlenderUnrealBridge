# Blender ↔ Unreal Bridge: Architecture Specification

## 1. System Overview

The **Blender ↔ Unreal Bridge** is an open-source interoperability pipeline designed to transfer 3D scenes from Blender into Unreal Engine while preserving scene structure, transforms, geometry, UVs, normals, materials, and textures with maximum practical fidelity.

The architecture strictly decouples DCC-specific extraction from game-engine-specific asset ingestion through an **engine-independent intermediate representation** known as the **Bridge Data Package** (`.bubridge`).

```
                         BLENDER
                            │
                            ▼
                 ┌────────────────────┐
                 │   Blender Add-on   │
                 │                    │
                 │ Scene Collector    │
                 │ Transform Mapper   │
                 │ Geometry Exporter  │
                 │ Material Analyzer  │
                 │ Texture Discovery  │
                 │ Package Writer     │
                 └─────────┬──────────┘
                           │
                           ▼
                  BRIDGE DATA PACKAGE (.bubridge)
                 ┌─────────────────────────────┐
                 │  manifest.json              │
                 │  scene.json                 │
                 │  objects.json               │
                 │  materials.json             │
                 │  textures.json              │
                 │  meshes/                    │
                 │  textures/                  │
                 └─────────┬───────────────────┘
                           │
                           ▼
                 ┌────────────────────┐
                 │    Bridge Core     │
                 │                    │
                 │ Data Schemas       │
                 │ Canonical Math     │
                 │ Format Validation  │
                 │ Diagnostic Logger  │
                 └─────────┬──────────┘
                           │
                           ▼
                 ┌────────────────────┐
                 │   Unreal Plugin    │
                 │                    │
                 │ Package Reader     │
                 │ Asset Importer     │
                 │ Material Builder   │
                 │ Actor Synchronizer │
                 └─────────┬──────────┘
                           │
                           ▼
                      UNREAL ENGINE
```

---

## 2. Component Responsibilities

### 2.1 Blender Add-on (`blender_addon/`)
* **Technology**: Python 3.x using Blender's official `bpy` API.
* **Responsibilities**:
  * **Scene Collector**: Traverses the active Blender view layer/scene, gathering candidate objects, collection memberships, and parent-child hierarchies.
  * **Identity Manager**: Assigns and persists stable, deterministic 64-bit hex Bridge IDs (`bubridge_id`) on Blender objects and data blocks using custom properties.
  * **Transform Mapper**: Extracts world and local matrices, decomposes them, and converts Blender coordinates into the canonical Bridge coordinate representation.
  * **Material Analyzer**: Parses node graphs (specifically `ShaderNodeBsdfPrincipled` and connected nodes) and performs semantic pattern matching rather than direct node-to-node replication.
  * **Texture Discovery**: Identifies texture image dependencies, validates source file paths on disk, verifies color spaces, and flags missing or unlinked assets.
  * **Geometry Exporter**: Extracts clean static mesh data (triangulated/polygonal vertices, UV layers, normals, material slot assignments) and prepares standard interchange files (e.g., GLB/glTF or canonical binary buffers).
  * **User Interface & Operators**: Blender panels and operator triggers for configuration, validation checks, export execution, and report generation.

### 2.2 Bridge Core (`bridge_core/`)
* **Technology**: Platform-agnostic C++ (standard C++17/20, STL, minimal external dependencies).
* **Responsibilities**:
  * **Data Schemas & Serialization**: Canonical data representations for scenes, objects, transforms, materials, and textures.
  * **Validation Engine**: Validates package structure and data integrity against defined protocol schemas before ingestion or export.
  * **Canonical Transform Math**: Mathematical definitions and matrix operations for coordinate spaces, handedness conversions, and unit scaling.
  * **Diagnostic Reporting**: Structured report generator categorizing messages into `INFO`, `WARNING`, and `ERROR`.
  * **Decoupling Layer**: Ensures neither Blender nor Unreal code leaks into the core data definitions, enabling future adapters (e.g., Unity, Godot, Maya, 3ds Max).

### 2.3 Unreal Plugin (`unreal_plugin/`)
* **Technology**: C++ (Unreal Engine 5.x Plugin architecture, Editor-only modules).
* **Responsibilities**:
  * **Package Reader**: Ingests `.bubridge` directories or bundles, validates `manifest.json`, and loads structured JSON metadata into memory.
  * **Asset Importer**: Converts binary mesh payloads into native Unreal `UStaticMesh` assets, managing LODs, vertex normals, and UV channels.
  * **Texture Importer**: Ingests texture files into `UTexture2D` assets with correct compression settings and sRGB flags.
  * **Material Builder**: Generates Unreal `UMaterial` / `UMaterialInstanceConstant` assets dynamically based on the semantic PBR description.
  * **Actor Synchronizer**: Spawns or updates `AActor` / `AStaticMeshActor` instances in the current World/Level, rebuilding hierarchies and applying world/relative transforms.
  * **Import Reporting**: Outputs structured diagnostic logs to the Unreal Message Log window.

### 2.4 Synchronization Layer (`Synchronization/`)
* **Status**: Architectural foundation in place; full live sync planned post-MVP.
* **Responsibilities**:
  * Event-driven communication protocol transmitting discrete mutations (transform delta, material update, mesh reload) tagged with stable Bridge IDs.
  * One-way transport (Blender → Unreal) initially via socket/IPC (e.g., WebSockets or Named Pipes), laying groundwork for eventual bi-directional synchronization with conflict resolution.

---

## 3. Data Flow

```
[Blender Scene]
      │
      ├─► 1. Scene Traversal & Filtering (Collector)
      ├─► 2. ID Generation / Retrieval (bubridge_id custom property)
      ├─► 3. Transform Extraction & Canonical Conversion
      ├─► 4. Material Node Graph Semantic Inspection (Analyzer)
      ├─► 5. Texture Discovery & File Validation
      ├─► 6. Geometry Export (GLB / Binary Buffers)
      │
      ▼
[Bridge Package Writer]
      │
      ├─► manifest.json (format, version, source, units, coordinate axes)
      ├─► scene.json    (environment, global scale, collections)
      ├─► objects.json  (stable IDs, hierarchy, transforms, mesh & material refs)
      ├─► materials.json(PBR semantic parameters, texture slot bindings)
      ├─► textures.json (path mappings, color spaces, dimensions)
      └─► meshes/ & textures/ payload folders
      │
      ▼
[Unreal Package Reader]
      │
      ├─► 1. Manifest Validation (version check, compatibility)
      ├─► 2. Texture Asset Import (UTexture2D, sRGB/Linear configuration)
      ├─► 3. Material Asset Construction (UMaterial / Master Instance binding)
      ├─► 4. Static Mesh Ingestion (UStaticMesh, materials slotted)
      ├─► 5. Level Actor Instantiation & Hierarchy Rebuilding (AActor)
      ├─► 6. Transform Application (Location, Rotation, Scale)
      │
      ▼
[Unreal Engine World / Level]
```

---

## 4. Coordinate System & Space Conversions

### 4.1 Coordinate Space Definitions
* **Blender**:
  * Right-Handed, Z-Up
  * Default Unit: Meter ($1.0\text{ BU} = 1.0\text{ m}$)
  * Axes: $+X$ Right, $+Y$ Forward, $+Z$ Up
* **Unreal Engine**:
  * Left-Handed, Z-Up
  * Default Unit: Centimeter ($1.0\text{ uu} = 1.0\text{ cm}$)
  * Axes: $+X$ Forward, $+Y$ Right, $+Z$ Up
* **Canonical Bridge Space**:
  * Standardized coordinate system: **Z-Up, Centimeter, Unreal-compatible left-handed basis**.
  * Unit scale factor: $100.0$ (Meters $\rightarrow$ Centimeters).

### 4.2 Authoritative Transform Conversion Rules
To avoid scattering coordinate conversions throughout the codebase, all coordinate transformations occur in **exactly one controlled location** during export:

1. **Translation**:
   $$\text{Location}_{\text{Unreal}} = (Y_{\text{Blender}} \times 100.0,\; X_{\text{Blender}} \times 100.0,\; Z_{\text{Blender}} \times 100.0)$$
   *(Alternatively, preserving right/forward conventions with handedness reflection: $X_{\text{UE}} = X_{\text{Blender}} \times 100.0$, $Y_{\text{UE}} = -Y_{\text{Blender}} \times 100.0$, $Z_{\text{UE}} = Z_{\text{Blender}} \times 100.0$, along with polygon winding adjustment. The exact matrix formulation is centralized in `transforms.py` / `CanonicalTransform.cpp`).*
2. **Rotation**:
   * Evaluated via Quaternions $[x, y, z, w]$ to eliminate gimbal lock.
   * Converted through the canonical basis change matrix.
3. **Scale**:
   * Evaluated as $(S_x, S_y, S_z)$ maintaining axis parity.
   * Negative scaling (reflection) is flagged to trigger polygon winding inversion on mesh import.

---

## 5. Material Translation Philosophy

### 5.1 Semantic Translation vs. Node-by-Node Transpilation
Blender and Unreal utilize fundamentally different shading and rendering architectures:
* Blender's EEVEE/Cycles is an offline/hybrid raytracer evaluating arbitrary procedural closures and shading trees.
* Unreal Engine relies on compiled HLSL/PBR deferred or forward shaders with rigid material models.

Direct 1:1 translation of node graphs is mathematically and practically infeasible. Instead, the Bridge adopts **semantic translation**:
1. Inspect the material's output node (`Material Output`).
2. Identify whether a supported standard BSDF is attached (e.g., `Principled BSDF`).
3. Extract canonical PBR channels:
   * **Base Color** (Constant color $[R, G, B, A]$ or Texture link + UV channel)
   * **Metallic** (Scalar value $[0.0, 1.0]$ or Texture link)
   * **Roughness** (Scalar value $[0.0, 1.0]$ or Texture link)
   * **Normal** (Normal map node reference, strength, invert green flag)
   * **Emission** (Color $[R, G, B]$, strength multiplier)
   * **Opacity / Alpha** (Scalar value $[0.0, 1.0]$ or Texture link)
4. If procedural nodes, unmapped math nodes, or Cycles-only closures (Glass, Velvet, Subsurface Random Walk) are detected:
   * Do not abort silently.
   * Extract whatever fallback PBR values or baked color is available.
   * Issue a clear `WARNING` in the validation report explaining precisely which nodes could not be mapped.

---

## 6. Object Identity & Hierarchy

### 6.1 Stable Bridge IDs
* Never rely on object names for identity. Objects in Blender are frequently renamed (`Cube.001` $\rightarrow$ `SM_Table`).
* Upon first export or scene collection, each object is tagged with a UUID/hash stored in `obj["bubridge_id"]`.
* This ID persists across scene modifications and renames, allowing Unreal to update existing actors rather than duplicating them.

### 6.2 Hierarchy Mapping
* Parent-child relationships are serialized via parent Bridge IDs (`parent_id: "obj_xxx"`).
* If an object has no parent, `parent_id` is `null` (world-root).
* Blender Collections are serialized as organizational tags/folders, mapping to Unreal Editor World Outliner Folders.

---

## 7. Error Handling and Diagnostic System

Three non-negotiable diagnostic levels:
1. **INFO**: Informational milestones (e.g., count of objects exported, package file written, asset imported).
2. **WARNING**: Non-fatal discrepancies (e.g., unsupported shader node bypassed with fallback, texture color space mismatch, missing UV layer).
3. **ERROR**: Fatal conditions aborting asset processing (e.g., missing referenced texture file, unreadable mesh geometry, unsupported package manifest version).

All operations emit a structured report (`report.json` or console log) detailing the findings. Silent failures are strictly forbidden.

---

## 8. Live Synchronization Architecture (Milestone 10)

The live synchronization layer complements the `.bubridge` package pipeline with low-latency, real-time delta synchronization between active Blender and Unreal Editor sessions.

```text
Blender Viewport
       │ (User moves / rotates / scales object)
       ▼
depsgraph_update_post Handler
       │
       ▼
Canonical Transform Authority (transforms/canonical.py)
       │ (Epsilon dirty-check vs last-sent cache)
       ▼
LiveSyncSession (TCP Client, port 27284)
       │ (BUBRIDGE_LIVESYNC v0.1.0 JSON stream)
       ▼
FBridgeLiveSyncReceiver (TCP Server in Unreal Plugin)
       │ (FRunnable background thread)
       ▼
Thread-Safe Pending Update Queue
       │ (Ticker drain onto Game Thread)
       ▼
Actor Lookup (SpawnedActors map via stable bubridge_id)
       │
       ▼
AActor / USceneComponent Transform Update
```

### 8.1 Key Design Principles:
1. **Additive, Not Subtractive**: Live sync does NOT replace `.bubridge` packages. Full scene baseline imports remain package-driven.
2. **Canonical Coordinates Preserved**: Transform deltas use the exact same canonical coordinate system (+Z Up, +X Forward, +Y Right, cm) evaluated by `transforms/canonical.py`.
3. **Hierarchy Preservation**: Root actors receive world transforms; attached child actors receive local relative transforms without double transformation.
4. **Resilient Failure Modes**: Disconnecting Blender or closing Unreal never crashes either application.
5. **Thread Safety**: Unreal network I/O executes on an isolated `FRunnable` thread while all `UObject`/`AActor` mutations are marshaled to the Game Thread via `FTSTicker`.
