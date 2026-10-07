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
├── materials.json      # Optional/MVP: Semantic PBR material definitions
├── textures.json       # Optional/MVP: Texture metadata and color space information
├── animations.json     # Reserved for Milestone 8
│
├── meshes/             # Binary mesh assets (.glb or raw buffers)
│   ├── mesh_001.glb
│   └── mesh_002.glb
│
├── textures/           # Texture image files (PNG, JPG, TGA, EXR)
│   ├── tex_001.png
│   └── tex_002.png
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
    "texture_count": 6
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
  ]
}
```

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
