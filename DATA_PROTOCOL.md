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
        "file": "meshes/house_01.glb",
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
        "file": "meshes/chimney_01.glb",
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

### 4.4 `materials.json`

Captures the semantic PBR parameters extracted from Blender shader graphs.

```json
{
  "materials": [
    {
      "id": "mat_roof_01",
      "name": "M_Roof",
      "shading_model": "DEFAULT_LIT_PBR",
      "blend_mode": "OPAQUE",
      "two_sided": false,
      "channels": {
        "base_color": {
          "type": "TEXTURE",
          "value": [1.0, 1.0, 1.0, 1.0],
          "texture_id": "tex_roof_diff",
          "uv_channel": 0
        },
        "metallic": {
          "type": "CONSTANT",
          "value": 0.0,
          "texture_id": null
        },
        "roughness": {
          "type": "TEXTURE",
          "value": 0.7,
          "texture_id": "tex_roof_rough",
          "uv_channel": 0
        },
        "normal": {
          "type": "TEXTURE",
          "texture_id": "tex_roof_norm",
          "strength": 1.0,
          "uv_channel": 0,
          "invert_green": false
        },
        "emission": {
          "type": "CONSTANT",
          "value": [0.0, 0.0, 0.0],
          "strength": 0.0
        },
        "opacity": {
          "type": "CONSTANT",
          "value": 1.0,
          "texture_id": null
        }
      },
      "unsupported_nodes_detected": []
    }
  ]
}
```

#### Channel Value Types:
* `CONSTANT`: Constant scalar or vector value.
* `TEXTURE`: Bound to a texture reference from `textures.json`.
* `FALLBACK`: Default value substituted when an unsupported procedural node network is detected.

---

### 4.5 `textures.json`

Tracks image textures required by materials, including file paths and color space requirements.

```json
{
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
