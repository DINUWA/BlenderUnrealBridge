# Blender ↔ Unreal Bridge

## 1. Project Overview

### Project Name

**Blender ↔ Unreal Bridge**

### Purpose

Create an open-source bridge between **Blender** and **Unreal Engine** that preserves as much Blender scene information as realistically possible when transferring assets into Unreal Engine.

The system should eventually support:

* Geometry
* Transforms
* Object hierarchy
* Materials
* Textures
* UVs
* Normals
* LODs
* Collision
* Skeletal meshes
* Animations
* Morph targets
* Material parameters
* Live synchronization

The project must NOT attempt to reproduce Blender's internal rendering system inside Unreal.

Instead, it should translate Blender data into an **engine-independent intermediate representation**, then convert that representation into Unreal-compatible assets.

---

# 2. Core Architecture

```text
                         BLENDER
                            │
                            ▼
                 ┌────────────────────┐
                 │ Blender Add-on     │
                 │                    │
                 │ Scene Collector    │
                 │ Geometry Exporter  │
                 │ Material Analyzer  │
                 │ Animation Exporter │
                 │ Transform Mapper   │
                 └─────────┬──────────┘
                           │
                           ▼
                  BRIDGE DATA PACKAGE
                           │
                 ┌─────────▼──────────┐
                 │    Bridge Core     │
                 │                    │
                 │ Scene Data         │
                 │ Geometry           │
                 │ Materials          │
                 │ Textures           │
                 │ Animation          │
                 │ Transform          │
                 │ Validation         │
                 └─────────┬──────────┘
                           │
                           ▼
                 ┌────────────────────┐
                 │ Unreal Plugin      │
                 │                    │
                 │ Package Reader     │
                 │ Asset Importer     │
                 │ Material Builder   │
                 │ Actor Synchronizer │
                 └─────────┬──────────┘
                           │
                           ▼
                        UNREAL
```

The architecture must keep the **Bridge Core independent from Blender and Unreal whenever practical**.

---

# 3. Technology Stack

## Blender Side

### Language

**Python 3.x**

Use Blender's official Python API.

### Blender Add-on

Responsibilities:

* Scene inspection
* Object collection
* Transform extraction
* Material analysis
* Texture discovery
* Export preparation
* Validation
* User interface
* Communication with Unreal

---

# Unreal Side

### Language

**C++**

Use Unreal Engine's official plugin architecture.

Blueprints may be exposed for convenience, but the core bridge functionality must be implemented in C++.

---

# Bridge Core

Preferred implementation:

**C++**

The core should eventually be usable independently from the Blender and Unreal UI layers.

However, during MVP development, keep the architecture simple and avoid premature abstraction.

---

# Data Format

Primary metadata format:

**JSON**

Binary assets:

* GLB/glTF where appropriate
* PNG/JPG/TGA/EXR or original supported texture formats
* Other binary resources when required

The Bridge package should contain metadata separately from binary asset files.

---

# Version Control

Use:

**Git**

Recommended repository hosting:

GitHub.

---

# Documentation

Use Markdown.

Required documentation:

```text
README.md
PROJECT_SPEC.md
ARCHITECTURE.md
DATA_PROTOCOL.md
DEVELOPMENT.md
CHANGELOG.md
```

---

# Testing

Blender:

* Python unit tests
* Export validation tests

Bridge Core:

* C++ unit tests where practical

Unreal:

* Automated import/validation tests where practical

Every major feature should have at least one reproducible test scene.

---

# 4. Repository Structure

Use the following structure:

```text
blender-unreal-bridge/
│
├── README.md
├── PROJECT_SPEC.md
├── ARCHITECTURE.md
├── DATA_PROTOCOL.md
├── DEVELOPMENT.md
├── CHANGELOG.md
├── LICENSE
├── .gitignore
│
├── docs/
│   ├── architecture/
│   ├── blender/
│   ├── unreal/
│   └── protocol/
│
├── blender_addon/
│   ├── blender_unreal_bridge/
│   │   ├── __init__.py
│   │   │
│   │   ├── operators/
│   │   ├── panels/
│   │   ├── exporters/
│   │   ├── collectors/
│   │   ├── materials/
│   │   ├── geometry/
│   │   ├── animation/
│   │   ├── transforms/
│   │   ├── textures/
│   │   ├── protocol/
│   │   ├── validation/
│   │   ├── utils/
│   │   └── tests/
│   │
│   └── requirements.txt
│
├── bridge_core/
│   ├── include/
│   ├── src/
│   └── tests/
│
├── unreal_plugin/
│   ├── BlenderUnrealBridge.uplugin
│   ├── Source/
│   │   ├── BlenderUnrealBridge/
│   │   ├── Importer/
│   │   ├── Materials/
│   │   ├── Geometry/
│   │   ├── Animation/
│   │   ├── Synchronization/
│   │   ├── Protocol/
│   │   ├── Validation/
│   │   └── Utilities/
│   │
│   ├── Resources/
│   └── Content/
│
├── examples/
│   ├── basic_mesh/
│   ├── materials/
│   ├── animation/
│   └── live_sync/
│
├── test_assets/
│   ├── geometry/
│   ├── materials/
│   ├── animations/
│   └── edge_cases/
│
└── tools/
    ├── validators/
    └── development/
```

Do NOT create every directory immediately if it has no implementation.

Create directories progressively as features are implemented.

---

# 5. Design Principles

## Principle 1 — Do not promise 100% Blender compatibility

Blender and Unreal have fundamentally different rendering and material systems.

The project should aim for:

**maximum practical compatibility**, not theoretical 100% compatibility.

---

## Principle 2 — Use semantic translation

Do NOT simply attempt:

```text
Blender Node → Unreal Node
```

Instead:

```text
Blender Data
     ↓
Semantic Interpretation
     ↓
Bridge Representation
     ↓
Unreal Representation
```

Example:

```text
Blender Principled BSDF
        ↓
PBR Material Description
        ↓
Unreal Material
```

---

# 6. Coordinate System

The Bridge must define a canonical coordinate system.

Initial specification:

```text
Up Axis: Z
Unit: Centimeter
Handedness: Unreal-compatible representation
```

Blender coordinates must be converted into the canonical representation in exactly one controlled location.

Avoid scattering coordinate conversions throughout the code.

---

# 7. Transform Specification

Each object should contain:

```json
{
    "location": [0.0, 0.0, 0.0],
    "rotation": [0.0, 0.0, 0.0],
    "scale": [1.0, 1.0, 1.0]
}
```

Also store:

* rotation mode
* object origin information
* parent
* hierarchy
* object name
* unique object ID

Do not rely on object names as unique identifiers.

---

# 8. Object Identity

Every exported object must receive a stable Bridge ID.

Example:

```json
{
    "id": "obj_7f9d31a2",
    "name": "SM_Rock_01"
}
```

The Bridge ID is used for synchronization.

Object names may change without breaking synchronization.

---

# 9. Bridge Package

Example:

```text
MyEnvironment.bubridge/
│
├── manifest.json
├── scene.json
├── objects.json
├── materials.json
├── textures.json
├── animations.json
│
├── meshes/
│   ├── mesh_001.glb
│   └── mesh_002.glb
│
├── textures/
│   ├── tex_001.png
│   └── tex_002.png
│
└── metadata/
```

The actual package format may evolve.

---

# 10. Manifest

Example:

```json
{
    "format": "BUBRIDGE",
    "version": "0.1.0",
    "source": {
        "application": "Blender",
        "version": "5.x"
    },
    "target": {
        "application": "Unreal Engine",
        "version": "5.x"
    },
    "unit": "centimeter",
    "up_axis": "Z"
}
```

The importer must validate the format version before processing.

---

# 11. MVP

The first version must be intentionally small.

## MVP Goal

Transfer a Blender scene into Unreal with reliable:

### Geometry

* Static meshes
* Multiple objects
* Multiple mesh instances

### Transform

* Location
* Rotation
* Scale

### Hierarchy

* Parent-child relationships
* Collections

### Materials

Support basic PBR:

* Base Color
* Metallic
* Roughness
* Normal
* Emission
* Opacity where practical

### Textures

* Image textures
* Texture paths
* Basic UV mapping

### Scene

* Object names
* Stable Bridge IDs

---

# 12. MVP Explicitly DOES NOT Include

Do not implement these during the initial MVP:

* Geometry Nodes
* Cycles-only shaders
* Complex procedural materials
* Hair systems
* Cloth simulation
* Fluid simulation
* Particle systems
* Advanced compositing
* Full Blender shader-node compatibility
* Two-way synchronization
* Automatic perfect material recreation
* Every Blender modifier
* Every Unreal material feature

These should be future milestones.

---

# 13. Material Translation

Initial supported material model:

```text
PBR Material
│
├── Base Color
├── Metallic
├── Roughness
├── Normal
├── Emission
└── Opacity
```

The translator should inspect Blender's material node graph.

If a supported pattern is detected:

```text
Supported → convert
```

If unsupported:

```text
Unsupported → warning + fallback
```

Never silently discard data.

---

# 14. Error Handling

The system must never silently fail.

Use three levels:

```text
INFO
WARNING
ERROR
```

Example:

```text
[INFO] Export started
[INFO] Found 24 objects

[WARNING] Material Glass_01 contains unsupported shader nodes.

[ERROR] Texture file could not be found:
C:/Project/Textures/Rock_N.png
```

Export should produce a report.

---

# 15. Live Synchronization

This is NOT part of the initial MVP.

Future architecture:

```text
Blender
   │
   │ Change Event
   ▼
Bridge Synchronization Layer
   │
   │ Object ID + Changed Data
   ▼
Unreal
```

Example:

```json
{
    "event": "transform_changed",
    "object_id": "obj_7f9d31a2",
    "transform": {
        "location": [100, 200, 50],
        "rotation": [0, 45, 0],
        "scale": [1, 1, 1]
    }
}
```

---

# 16. Future Two-Way Synchronization

Eventually support:

```text
Blender → Unreal
```

and:

```text
Blender ← Unreal
```

However, two-way synchronization must not be implemented until stable one-way synchronization exists.

Conflict resolution will be required.

---

# 17. Development Milestones

## Milestone 0

Project skeleton.

## Milestone 1

Blender scene inspection.

## Milestone 2

Transform export/import.

## Milestone 3

Static mesh transfer.

## Milestone 4

Basic PBR materials.

## Milestone 5

Textures and UVs.

## Milestone 6

Hierarchy and instances.

## Milestone 7

Validation and error reporting.

## Milestone 8

Animation.

## Milestone 9

Live synchronization.

## Milestone 10

Optimization and production readiness.

---

# 18. Success Criteria

The MVP is successful when the following Blender scene:

```text
Scene
├── House
├── Tree
├── Rock
├── Ground
└── Light
```

can be transferred to Unreal while preserving:

* Correct relative positions
* Correct scale
* Correct rotations
* Correct mesh geometry
* Correct UVs
* Correct basic PBR materials
* Correct textures
* Correct object hierarchy

and produces a useful import report.

---

# 19. AI Development Rules

Antigravity must follow these rules:

1. Do not rewrite working modules unnecessarily.
2. Do not introduce dependencies without justification.
3. Do not implement future features during MVP unless required architecturally.
4. Always explain architectural changes.
5. Maintain backward compatibility for the Bridge data format.
6. Add tests for new functionality.
7. Never silently ignore unsupported Blender features.
8. Prefer small, isolated commits.
9. Keep Blender and Unreal responsibilities separate.
10. Do not make assumptions about Unreal APIs; verify the correct API before implementation.
11. Keep the code readable and documented.
12. Avoid premature optimization.
13. Do not generate huge files when smaller modules are appropriate.
14. Preserve existing functionality when adding features.

---

# 20. First 10 Antigravity Prompts

## Prompt 1 — Architecture

```text
Read PROJECT_SPEC.md completely.

Do not write implementation code yet.

Analyze the project and create:

1. ARCHITECTURE.md
2. DATA_PROTOCOL.md
3. DEVELOPMENT.md

Define the responsibilities of:

- Blender Add-on
- Bridge Core
- Unreal Plugin
- Bridge Package
- Synchronization Layer

Define the data flow from Blender to Unreal.

Do not implement functionality yet.

Before making changes, inspect the repository structure and existing files.
```

---

## Prompt 2 — Repository Foundation

```text
Based on PROJECT_SPEC.md and ARCHITECTURE.md, create the minimum repository structure required for the project.

Create only directories and files that are currently needed.

Implement:

- Basic Blender add-on package
- Basic Unreal plugin skeleton
- Bridge Core skeleton
- Test structure
- Documentation structure

Do not implement mesh/material/animation functionality yet.

The project must build cleanly at this stage.
```

---

## Prompt 3 — Blender Scene Collector

```text
Implement the Blender Scene Collector.

Requirements:

- Discover scene objects.
- Collect mesh objects.
- Collect object names.
- Generate stable Bridge IDs.
- Collect parent relationships.
- Collect collection membership.
- Collect transforms.
- Do not export geometry yet.
- Do not implement materials yet.

Create clean Python modules.

Add unit tests using representative Blender test data where practical.

Do not modify unrelated files.
```

---

## Prompt 4 — Transform System

```text
Implement the Bridge transform system.

Requirements:

- Blender location
- Blender rotation
- Blender scale
- Rotation mode
- Parent relationship
- Coordinate conversion
- Unit conversion

Use the canonical coordinate system defined in PROJECT_SPEC.md.

Create a single authoritative transform conversion module.

Do not scatter coordinate conversion logic across the codebase.

Add tests for:

- identity transform
- translation
- rotation
- non-uniform scale
- negative scale
- parented objects

Document the conversion rules.
```

---

## Prompt 5 — Bridge Package

```text
Implement version 0.1 of the Bridge Package.

Create:

- manifest.json
- scene.json
- objects.json

Implement serialization from the Blender Scene Collector into this package.

Requirements:

- deterministic output
- stable object IDs
- format version
- source application information
- unit information
- coordinate system information

Add validation before writing the package.

Invalid data must generate clear errors.

Do not implement materials or geometry yet.
```

---

## Prompt 6 — Unreal Package Reader

```text
Implement the Unreal-side Bridge Package reader.

The Unreal plugin must:

1. Locate a Bridge package.
2. Read manifest.json.
3. Validate the package version.
4. Read scene/object metadata.
5. Report invalid or unsupported data clearly.

Do not import meshes yet.

Do not create materials yet.

Create clean C++ classes with clear ownership and responsibilities.

Add logging for:

- package loaded
- package version
- object count
- validation errors
```

---

## Prompt 7 — Static Mesh Pipeline

```text
Implement the first static mesh pipeline.

Goal:

Blender Mesh
    ↓
Bridge Package
    ↓
Unreal Static Mesh

Use the most reliable standard mesh interchange method available for the current supported Blender and Unreal versions.

Requirements:

- preserve geometry
- preserve UVs
- preserve normals where supported
- preserve object identity
- preserve transforms

Do not implement advanced material conversion yet.

Create a test scene containing:

- cube
- sphere
- non-uniform object
- rotated object
- multiple objects

Document known limitations.
```

---

## Prompt 8 — PBR Material Translator

```text
Implement the initial Blender-to-Unreal PBR material translator.

Support only these semantic properties:

- Base Color
- Metallic
- Roughness
- Normal
- Emission
- Opacity

Do not attempt arbitrary Blender node conversion.

Analyze Blender material node graphs and recognize supported PBR patterns.

Unsupported node configurations must generate warnings rather than silently failing.

Create:

1. Blender material analyzer
2. Bridge material representation
3. Unreal material importer/builder

Add test materials for every supported property.
```

---

## Prompt 9 — Textures and Validation

```text
Implement texture discovery and validation.

Requirements:

- discover image textures used by supported materials
- validate file existence
- preserve texture references in the Bridge Package
- copy/package textures when appropriate
- detect missing textures
- detect unsupported texture configurations

Add a clear import/export report.

Example:

INFO:
Texture found

WARNING:
Texture colorspace requires conversion

ERROR:
Texture file missing

Do not silently replace missing textures.
```

---

## Prompt 10 — End-to-End MVP

```text
Now integrate the completed MVP pipeline.

The complete workflow must be:

Blender Scene
    ↓
Scene Collection
    ↓
Transform Conversion
    ↓
Geometry Export
    ↓
Material Analysis
    ↓
Texture Collection
    ↓
Bridge Package
    ↓
Unreal Package Reader
    ↓
Static Mesh Import
    ↓
Material Creation
    ↓
Texture Assignment
    ↓
Actor Creation
    ↓
Transform Application

Create an end-to-end test scene.

Verify:

- geometry
- transforms
- scale
- hierarchy
- UVs
- textures
- PBR materials
- object IDs

Generate a final import/export report.

Do not implement live synchronization yet.

At the end, provide:

1. What works
2. What does not work
3. Known limitations
4. Test results
5. Recommended next milestone

Do not rewrite stable code unnecessarily.
```

---

# 21. After MVP

Only after the MVP is stable, continue in this order:

```text
MVP
 ↓
Material Instances
 ↓
LOD
 ↓
Collision
 ↓
Skeletal Mesh
 ↓
Animation
 ↓
Morph Targets
 ↓
Live Sync
 ↓
Two-way Sync
 ↓
Performance Optimization
 ↓
Production Release
```

---

# 22. Long-Term Vision

The ultimate architecture should become:

```text
                     BLENDER
                        │
                 Blender Adapter
                        │
                        ▼
              ┌───────────────────┐
              │                   │
              │   BRIDGE CORE     │
              │                   │
              │ Scene             │
              │ Geometry          │
              │ Materials         │
              │ Animation         │
              │ Transforms        │
              │ Metadata          │
              │ Synchronization   │
              │                   │
              └─────────┬─────────┘
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
       Unreal         Unity         Godot
       Adapter        Adapter       Adapter
          │             │             │
          ▼             ▼             ▼
       Unreal         Unity         Godot
```

The long-term goal is not merely an exporter.

The goal is to create a **general-purpose 3D DCC-to-game-engine interoperability framework**, beginning with Blender → Unreal.

---

# 23. Project Philosophy

Build the smallest reliable bridge first.

Do not attempt to support everything Blender can do.

A reliable 80% workflow is more valuable than an unstable 100% workflow.

Prioritize:

**Correctness → Compatibility → Stability → Performance → Convenience**
