# Blender ↔ Unreal Bridge

An open-source bridge between **Blender** and **Unreal Engine** designed to transfer 3D scenes, transforms, hierarchies, geometry, UVs, normals, materials, and textures while preserving scene fidelity through an engine-independent intermediate representation.

---

## 1. Documentation & Specifications

The project architecture and development rules are specified in the following authoritative documents:

* [**`PROJECT_SPEC.md`**](PROJECT_SPEC.md): Primary product specification, requirements, and milestones.
* [**`ARCHITECTURE.md`**](ARCHITECTURE.md): System components, data flows, and coordinate conventions.
* [**`DATA_PROTOCOL.md`**](DATA_PROTOCOL.md): Detailed specification of the `.bubridge` package and schemas.
* [**`DEVELOPMENT.md`**](DEVELOPMENT.md): Development roadmap, testing methodology, and guidelines.
* [**`AGENTS.md`**](AGENTS.md): AI agent instructions and development rules.
* [**`CHANGELOG.md`**](CHANGELOG.md): History of milestone changes and releases.

---

## 2. Core Architecture

```text
Blender (Python Add-on)
       │
       ▼
Bridge Data Package (.bubridge)
       │
       ▼
Bridge Core (C++ Intermediate Representation)
       │
       ▼
Unreal Engine (C++ Plugin)
```

The system preserves Blender scene data using a decoupled **Bridge Data Package** (`.bubridge`) adhering to a canonical coordinate space ($+Z$ Up, Centimeters, Left-Handed Unreal basis).

---

## 3. Project Status

* **Current Milestone**: Milestone 0 — Repository Foundation
* **Status**: Initialized repository structure, module skeletons, and unit test harnesses.

---

## 4. License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
