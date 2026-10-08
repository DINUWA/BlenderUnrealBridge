# Blender ↔ Unreal Bridge: Data Protocol Specification

## 1. Specification Overview

The **Bridge Data Package** (`.bubridge`) is a self-contained directory or archive containing scene metadata, transform hierarchies, material definitions, texture references, and binary mesh data.

This document defines the formal schema, types, coordinate conventions, and semantics for Bridge Data Package **Version 0.1.0**.

---

## 2. Package Directory Layout

A `.bubridge` package is structured as follows:

```text
<PackageName>.bubridge/
├── manifest.json       # Required: Format, version, units, coordinate metadata
├── scene.json          # Required: Scene hierarchy, collections, global settings
├── objects.json        # Required: Object nodes, stable IDs, transforms, references
├── textures.json       # Optional: Texture metadata and color space information
├── animations.json     # Optional: Skeletal animations and bone hierarchies (Milestone 9)
│
├── materials/          # Atomic semantic PBR material definitions (mat_<hex>.json)
│   ├── mat_00000001.json
│   └── mat_00000002.json
│
├── meshes/             # Canonical mesh geometry payloads (mesh_<hex>.json)
│   ├── mesh_00000001.json
│   └── mesh_00000002.json
│
├── textures/           # Texture image files (PNG, JPG, TGA)
│   ├── tex_00000001.png
│   └── tex_00000002.png
│
└── metadata/           # Diagnostic and validation reports
    └── report.json     # Export log, warnings, and summary
```

---

## 3. Canonical Coordinate System & Units

All numeric transforms and coordinates stored in the Bridge package adhere strictly to the **Canonical Coordinate System**:

| Dimension | Canonical Bridge Value | Blender Source | Unreal Engine Target |
| :--- | :--- | :--- | :--- |
| **Up Axis** | **$+Z$** | $+Z$ | $+Z$ |
| **Forward Axis** | **$+X$** | $+Y$ | $+X$ |
| **Right Axis** | **$+Y$** | $+X$ | $+Y$ |
| **Unit** | **Centimeter (cm)** | Meter (m) | Centimeter (cm) |
| **Handedness** | **Left-Handed** | Right-Handed | Left-Handed |

All unit and axis transformations are applied prior to serialization into the Bridge Package. Readers can assume all values in `.bubridge` are already in Unreal-native coordinate space.

---

## 4. Metadata File Specifications

### 4.1 `manifest.json`

The entry point of any Bridge package. The importer **must** parse and validate this file first.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "format": "BUBRIDGE",
  "version": "0.1.0",
  "created_at": "2026-10-05T14:30:00Z",
  "generator": {
    "name": "BlenderUnrealBridgeAddon",
    "version": "0.1.0"
  },
  "source": {
    "application": "Blender",
    "version": "4.2.0",
    "scene_name": "MainScene",
    "unit_length": "meter",
    "unit_scale": 1.0
  },
  "target": {
    "application": "Unreal Engine",
    "version": "5.x",
    "unit_length": "centimeter"
  },
  "coordinate_system": {
    "up_axis": "Z",
    "forward_axis": "X",
    "right_axis": "Y",
    "handedness": "left_handed",
    "unit": "centimeter"
  },
  "content_summary": {
    "object_count": 5,
    "mesh_count": 3,
    "material_count": 4,
    "texture_count": 6,
    "skeleton_count": 1,
    "animation_count": 2
  }
}
```

---

### 4.2 `scene.json`

Describes scene-level settings and hierarchical organizational structures (e.g., Blender Collections / Unreal World Outliner folders).

```json
{
  "name": "MainScene",
  "collections": [
    {
      "id": "col_env_01",
      "name": "Environment",
      "parent_id": null,
      "color_tag": "GREEN"
    },
    {
      "id": "col_props_01",
      "name": "Props",
      "parent_id": "col_env_01",
      "color_tag": "YELLOW"
    }
  ],
  "environment": {
    "background_color": [0.05, 0.05, 0.05, 1.0],
    "ambient_intensity": 1.0
  }
}
```

---

### 4.3 `objects.json`

Defines all scene entities, their transforms, hierarchy, mesh references, and material bindings.

```json
{
  "objects": [
    {
      "id": "obj_7f9d31a2",
      "name": "SM_House",
      "type": "STATIC_MESH",
      "visible": true,
      "collection_id": "col_env_01",
      "parent_id": null,
      "transform": {
        "location": [0.0, 0.0, 0.0],
        "rotation_euler": [0.0, 0.0, 0.0],
        "rotation_quaternion": [0.0, 0.0, 0.0, 1.0],
        "rotation_mode": "QUATERNION",
        "scale": [1.0, 1.0, 1.0],
        "origin_offset": [0.0, 0.0, 0.0]
      },
      "mesh_reference": {
        "mesh_id": "mesh_house_01",
        "file": "meshes/mesh_house_01.json",
        "submesh_index": 0
      },
      "material_slots": [
        {
          "slot_index": 0,
          "slot_name": "M_Roof",
          "material_id": "mat_roof_01"
        },
        {
          "slot_index": 1,
          "slot_name": "M_Walls",
          "material_id": "mat_walls_01"
        }
      ]
    },
    {
      "id": "obj_a831e5f0",
      "name": "SM_Chimney",
      "type": "STATIC_MESH",
      "visible": true,
      "collection_id": "col_env_01",
      "parent_id": "obj_7f9d31a2",
      "transform": {
        "location": [50.0, 20.0, 350.0],
        "rotation_euler": [0.0, 0.0, 0.0],
        "rotation_quaternion": [0.0, 0.0, 0.0, 1.0],
        "rotation_mode": "QUATERNION",
        "scale": [1.0, 1.0, 1.0],
        "origin_offset": [0.0, 0.0, 0.0]
      },
      "mesh_reference": {
        "mesh_id": "mesh_chimney_01",
        "file": "meshes/mesh_chimney_01.json",
        "submesh_index": 0
      },
      "material_slots": [
        {
          "slot_index": 0,
          "slot_name": "M_Brick",
          "material_id": "mat_brick_01"
        }
      ]
    }
  ]
}
```

#### Object Types:
* `STATIC_MESH`: Standard polygonal mesh.
* `SKELETAL_MESH`: Deformed polygonal mesh bound to an armature (`skeleton_id`, skinning weights).
* `ARMATURE`: Skeletal hierarchy root object referencing a skeleton (`skeleton_id`).
* `EMPTY`: Transform-only node (Null/Locator) used for hierarchical grouping.
* `LIGHT`: (Future) Directional, point, or spot light.
* `CAMERA`: (Future) Perspective or orthographic camera.

---

### 4.4 `meshes/<mesh_id>.json` (Canonical Geometry Payload)

Captures extracted static mesh geometry converted into Canonical Bridge coordinates (`BUBRIDGE_MESH` v0.1.0).

* **Coordinate space**: Left-Handed, Z-Up, Centimeter units ($Canon_X = Blender_Y \times 100$, $Canon_Y = Blender_X \times 100$, $Canon_Z = Blender_Z \times 100$).
* **Normals**: Canonical unit vectors ($Canon_{Nx} = Blender_{Ny}$, $Canon_{Ny} = Blender_{Nx}$, $Canon_{Nz} = Blender_{Nz}$).
* **Winding order**: Flipped for Left-Handed space (`[v0, v2, v1]`).
* **UVs**: Triangle-corner UV coordinates from active UV layer.
* **Material slots**: Indexed slot assignments per triangle.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "format": "BUBRIDGE_MESH",
  "version": "0.1.0",
  "mesh_id": "mesh_00000001",
  "name": "CubeMesh",
  "source": {
    "application": "Blender",
    "version": "4.5.3 LTS"
  },
  "coordinate_system": {
    "up_axis": "Z",
    "forward_axis": "X",
    "right_axis": "Y",
    "handedness": "left_handed",
    "unit": "centimeter"
  },
  "counts": {
    "vertex_count": 8,
    "triangle_count": 12,
    "uv_layer_count": 1,
    "material_slot_count": 1
  },
  "bounds": {
    "min": [-100.0, -100.0, -100.0],
    "max": [100.0, 100.0, 100.0]
  },
  "vertices": [
    [-100.0, -100.0, -100.0],
    [-100.0, -100.0, 100.0],
    [-100.0, 100.0, -100.0],
    [-100.0, 100.0, 100.0]
  ],
  "triangles": [
    {
      "vertex_indices": [0, 2, 1],
      "normals": [
        [-1.0, 0.0, 0.0],
        [-1.0, 0.0, 0.0],
        [-1.0, 0.0, 0.0]
      ],
      "uvs": [
        [0.0, 0.0],
        [1.0, 1.0],
        [1.0, 0.0]
      ],
      "material_slot_index": 0
    }
  ],
  "material_slots": [
    {
      "slot_index": 0,
      "slot_name": "M_Default",
      "material_id": null
    }
  ],
  "skinning": {
    "skeleton_id": "skel_a1b2c3d4",
    "vertex_weights": [
      [
        {
          "bone_id": "bone_00000001",
          "weight": 0.8
        },
        {
          "bone_id": "bone_00000002",
          "weight": 0.2
        }
      ]
    ]
  }
}
```

#### Skinning Specification (Milestone 9):
* `skinning`: Optional object present when the mesh is bound to an armature.
  * `skeleton_id`: Stable Bridge Skeleton ID (`skel_<8 hex chars>`).
  * `vertex_weights`: Array with length matching `vertex_count`. Each entry is a list of bone influences `{"bone_id": string, "weight": float}`.
  * Clamped to a maximum of 8 bone influences per vertex, sorted in descending order of weight, with weights normalized to sum to 1.0.

---

---

### 4.5 `materials/<material_id>.json` (Canonical PBR Material Payload)

Captures semantic PBR material parameters extracted from Blender shader graphs (`BUBRIDGE_MATERIAL` v0.1.0).

* **Format**: `BUBRIDGE_MATERIAL`
* **Version**: `0.1.0`
* **Model**: `PBR_METALLIC_ROUGHNESS`
* **Material ID format**: `mat_<8 hex chars>` (e.g. `mat_7f9d31a2`), stable and deterministic per Blender material datablock.
* **Storage**: Atomic per-material file located at `materials/<material_id>.json`.
* **Scope (Milestone 6)**: Constant scalar and color properties only (no textures).

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "format": "BUBRIDGE_MATERIAL",
  "version": "0.1.0",
  "material_id": "mat_7f9d31a2",
  "name": "M_Roof",
  "model": "PBR_METALLIC_ROUGHNESS",
  "properties": {
    "base_color": [0.8, 0.1, 0.1, 1.0],
    "metallic": 0.0,
    "roughness": 0.7,
    "specular": 0.5,
    "ior": 1.5,
    "opacity": 1.0,
    "blend_mode": "OPAQUE",
    "two_sided": false
  },
  "textures": {
    "base_color": "tex_roof_diff",
    "normal": "tex_roof_norm"
  }
}
```

#### Property Specifications:
* `base_color`: RGBA array of four floats normalized to `[0.0, 1.0]`. Extracted from Principled BSDF "Base Color" socket or legacy diffuse color.
* `metallic`: Float normalized to `[0.0, 1.0]`. Extracted from Principled BSDF "Metallic" socket.
* `roughness`: Float normalized to `[0.0, 1.0]`. Extracted from Principled BSDF "Roughness" socket.
* `specular`: Float normalized to `[0.0, 1.0]`. Extracted from Principled BSDF "Specular IOR Level" (Blender 4.0+) or "Specular" (<4.0) socket. Defaults to 0.5.
* `ior`: Float index of refraction (default 1.5). Extracted from Principled BSDF "IOR" socket.
* `opacity`: Float normalized to `[0.0, 1.0]`. Extracted from Principled BSDF "Alpha" socket.
* `blend_mode`: String enum (`OPAQUE`, `TRANSLUCENT`). Defaults to `OPAQUE` when opacity $\ge 0.999$.
* `two_sided`: Boolean flag indicating double-sided rendering. Defaults to `false` (single-sided standard).
* `textures`: Optional map of semantic channel names (`base_color`, `roughness`, `metallic`, `normal`) to stable Bridge Texture IDs (`tex_<hex>`). Fallback constant scalar and color properties remain active for untextured channels or fallback display.

---

### 4.6 `textures.json` (Milestone 7 Specification)

Tracks image textures required by materials, including package-relative file paths, dimensions, channels, and color space / compression configurations.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "format": "BUBRIDGE_TEXTURES",
  "version": "0.1.0",
  "textures": [
    {
      "id": "tex_roof_diff",
      "name": "T_Roof_BaseColor",
      "relative_path": "textures/T_Roof_BaseColor.png",
      "format": "PNG",
      "color_space": "sRGB",
      "dimensions": [2048, 2048],
      "channels": 4,
      "has_alpha": false,
      "compression_settings": "TC_Default"
    },
    {
      "id": "tex_roof_norm",
      "name": "T_Roof_Normal",
      "relative_path": "textures/T_Roof_Normal.png",
      "format": "PNG",
      "color_space": "Linear",
      "dimensions": [2048, 2048],
      "channels": 3,
      "has_alpha": false,
      "compression_settings": "TC_Normalmap"
    }
  ]
}
```

---

### 4.7 `animations.json` (Milestone 9 Specification)

Defines skeletal hierarchies (`skeletons`) and sampled bone animation clips (`animations`) adhering to `BUBRIDGE_ANIMATIONS` v0.1.0 in canonical coordinates.

* **Format**: `BUBRIDGE_ANIMATIONS`
* **Version**: `0.1.0`
* **Skeleton ID format**: `skel_<8 hex chars>` (e.g. `skel_a1b2c3d4`), persistent on Blender armature datablocks.
* **Bone ID format**: `bone_<8 hex chars>` (e.g. `bone_00000001`), persistent per bone.
* **Animation ID format**: `anim_<8 hex chars>` (e.g. `anim_e5f6a7b8`), persistent per Blender action.
* **Coordinate space**: Canonical Left-Handed Z-up centimeters.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "format": "BUBRIDGE_ANIMATIONS",
  "version": "0.1.0",
  "skeletons": [
    {
      "skeleton_id": "skel_a1b2c3d4",
      "name": "Armature",
      "bones": [
        {
          "bone_id": "bone_00000001",
          "name": "Root",
          "parent_bone_id": null,
          "rest_transform": {
            "location": [0.0, 0.0, 0.0],
            "rotation_euler": [0.0, 0.0, 0.0],
            "rotation_quaternion": [0.0, 0.0, 0.0, 1.0],
            "rotation_mode": "QUATERNION",
            "scale": [1.0, 1.0, 1.0],
            "origin_offset": [0.0, 0.0, 0.0]
          },
          "length": 100.0
        },
        {
          "bone_id": "bone_00000002",
          "name": "Spine",
          "parent_bone_id": "bone_00000001",
          "rest_transform": {
            "location": [0.0, 0.0, 100.0],
            "rotation_euler": [0.0, 0.0, 0.0],
            "rotation_quaternion": [0.0, 0.0, 0.0, 1.0],
            "rotation_mode": "QUATERNION",
            "scale": [1.0, 1.0, 1.0],
            "origin_offset": [0.0, 0.0, 0.0]
          },
          "length": 80.0
        }
      ]
    }
  ],
  "animations": [
    {
      "animation_id": "anim_e5f6a7b8",
      "name": "Walk",
      "skeleton_id": "skel_a1b2c3d4",
      "frame_rate": 30.0,
      "frame_start": 1,
      "frame_end": 30,
      "duration": 0.9667,
      "tracks": [
        {
          "bone_id": "bone_00000001",
          "bone_name": "Root",
          "location_keyframes": [
            {
              "frame": 1,
              "time": 0.0,
              "value": [0.0, 0.0, 0.0]
            },
            {
              "frame": 30,
              "time": 0.9667,
              "value": [50.0, 0.0, 0.0]
            }
          ],
          "rotation_keyframes": [
            {
              "frame": 1,
              "time": 0.0,
              "value": [0.0, 0.0, 0.0, 1.0]
            },
            {
              "frame": 30,
              "time": 0.9667,
              "value": [0.0, 0.0, 0.0, 1.0]
            }
          ],
          "scale_keyframes": [
            {
              "frame": 1,
              "time": 0.0,
              "value": [1.0, 1.0, 1.0]
            },
            {
              "frame": 30,
              "time": 0.9667,
              "value": [1.0, 1.0, 1.0]
            }
          ]
        }
      ]
    }
  ]
}
```

#### Skeleton & Bone Specifications:
* `skeletons`: List of armature hierarchies.
  * `skeleton_id`: Unique identifier formatted as `skel_<8 hex chars>`.
  * `bones`: Array of bones topologically ordered (parents appear before children).
    * `bone_id`: Unique identifier formatted as `bone_<8 hex chars>`.
    * `parent_bone_id`: Reference to parent `bone_id` or `null` for root bones.
    * `rest_transform`: Local rest pose transform relative to parent bone.
    * `length`: Bone length in canonical centimeter units.

#### Animation Clip Specifications:
* `animations`: List of action animation clips.
  * `animation_id`: Unique identifier formatted as `anim_<8 hex chars>`.
  * `skeleton_id`: Target skeleton identifier (`skel_<hex>`).
  * `frame_rate`: Evaluation frame rate (fps).
  * `tracks`: Per-bone animation tracks.
    * `location_keyframes`: Sampled local translation vector `[x, y, z]` in cm.
    * `rotation_keyframes`: Sampled local rotation quaternion `[x, y, z, w]`.
    * `scale_keyframes`: Sampled local scale vector `[x, y, z]`.
    * Keyframe times are monotonic and non-decreasing.

---

### 4.8 Live Synchronization Protocol (`BUBRIDGE_LIVESYNC` v0.1.0)

Defines the real-time TCP socket delta protocol for live scene updates between Blender and Unreal Engine without full `.bubridge` re-imports.

* **Wire format**: Single-line UTF-8 JSON terminated by `\n` (newline-delimited).
* **Transport**: Localhost TCP socket (default host: `127.0.0.1`, default port: `27284`).
* **Protocol Version**: `0.1.0`.
* **Coordinates**: All transform values are ALREADY in Bridge canonical space (Left-Handed, +Z Up, +X Forward, +Y Right, cm).
* **Idempotency**: All transform updates are absolute (not relative deltas).

#### Supported Messages:

1. **`HELLO`** (Blender $\rightarrow$ Unreal Handshake):
```json
{
  "message_type": "HELLO",
  "protocol_version": "0.1.0",
  "session_id": "a1b2c3d4",
  "source": "BlenderUnrealBridge_Addon",
  "source_version": "0.1.0",
  "sequence": 0
}
```

2. **`HELLO_ACK`** (Unreal $\rightarrow$ Blender Handshake Response):
```json
{
  "message_type": "HELLO_ACK",
  "protocol_version": "0.1.0",
  "session_id": "a1b2c3d4",
  "accepted": true,
  "sequence": 0
}
```

3. **`OBJECT_TRANSFORM_UPDATE`** (Blender $\rightarrow$ Unreal Transform Delta):
```json
{
  "message_type": "OBJECT_TRANSFORM_UPDATE",
  "protocol_version": "0.1.0",
  "session_id": "a1b2c3d4",
  "sequence": 1,
  "object_id": "obj_7f9d31a2",
  "transform": {
    "location": [50.0, 20.0, 350.0],
    "rotation": [0.0, 0.0, 0.0, 1.0],
    "scale": [1.0, 1.0, 1.0],
    "has_negative_scale": false
  }
}
```

4. **`KEEPALIVE`** (Heartbeat):
```json
{
  "message_type": "KEEPALIVE",
  "protocol_version": "0.1.0",
  "session_id": "a1b2c3d4",
  "sequence": 2
}
```

5. **`GOODBYE`** (Clean Disconnect):
```json
{
  "message_type": "GOODBYE",
  "protocol_version": "0.1.0",
  "session_id": "a1b2c3d4",
  "sequence": 3,
  "reason": "user_disconnect"
}
```

---

## 5. Diagnostic and Reporting Protocol (`report.json`)

Export and import operations generate a structured diagnostic report detailing progress, warnings, and errors.

```json
{
  "timestamp": "2026-10-05T14:30:05Z",
  "status": "SUCCESS_WITH_WARNINGS",
  "summary": {
    "info_count": 12,
    "warning_count": 2,
    "error_count": 0
  },
  "messages": [
    {
      "level": "INFO",
      "code": "EXPORT_BEGIN",
      "message": "Starting export for scene 'MainScene'"
    },
    {
      "level": "WARNING",
      "code": "MAT_UNSUPPORTED_NODE",
      "target_id": "mat_glass_01",
      "message": "Node 'ShaderNodeBsdfGlass' is unsupported in PBR MVP. Replaced with fallback OPAQUE material."
    },
    {
      "level": "ERROR",
      "code": "TEX_FILE_NOT_FOUND",
      "target_id": "tex_missing_01",
      "message": "Texture file 'D:/Assets/Rock_N.png' does not exist on disk."
    }
  ]
}
```

---

## 6. Versioning and Compatibility Rules

1. **Semantic Versioning**: The protocol version follows `MAJOR.MINOR.PATCH`.
   * **MAJOR**: Breaking structural changes to JSON files or coordinate conventions.
   * **MINOR**: Non-breaking additions of new fields, object types, or channels (e.g., adding `animations.json`).
   * **PATCH**: Bug fixes or schema clarification without field changes.
2. **Backward Compatibility**: Newer importers **must** be capable of reading older minor versions of packages.
3. **Unknown Field Tolerance**: Importers must ignore unrecognized JSON fields rather than failing.
4. **Validation Failure**: Importers must reject packages where `format != "BUBRIDGE"` or `MAJOR` version exceeds supported importer capabilities.
