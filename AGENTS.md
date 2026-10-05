# AI Agent Instructions and Development Rules

This document governs all AI-assisted and automated development on the **Blender ↔ Unreal Bridge** project. Any AI agent operating on this repository must read and strictly adhere to these instructions.

---

## 1. Authoritative Project Documents

The following specification files are authoritative and define the project scope, architecture, data formats, and workflow:

1. [**`PROJECT_SPEC.md`**](PROJECT_SPEC.md): The primary product specification document. All requirements, constraints, milestone definitions, and feature scopes derive from this file.
2. [**`ARCHITECTURE.md`**](ARCHITECTURE.md): The system architecture document defining component boundaries, data flow, coordinate system handling, and material translation models.
3. [**`DATA_PROTOCOL.md`**](DATA_PROTOCOL.md): The canonical specification of the `.bubridge` data package, file formats, JSON schemas, coordinate spaces, and diagnostic logging.
4. [**`DEVELOPMENT.md`**](DEVELOPMENT.md): The development roadmap, milestone progression rules, testing criteria, and verification procedures.

**Rule**: Do not make assumptions or introduce architectural changes that contradict these four documents. If an ambiguity or technical incompatibility arises, it must be explicitly identified, documented, and approved before making major changes.

---

## 2. Core AI Development Principles

1. **Incremental Milestone Progression**:
   * Do not attempt to build the entire system in one step.
   * Do not skip milestones. Progress sequentially (Milestone 0 $\rightarrow$ Milestone 1 $\rightarrow$ ...).
   * Wait for milestone completion verification before proceeding to the next milestone.

2. **No Premature Feature Implementation**:
   * Do not implement future features (e.g. geometry, materials, animation, live sync) until their respective milestone is active.
   * Avoid premature abstraction or unnecessary scaffolding.

3. **Codebase Preservation**:
   * Do not rewrite working, tested modules unnecessarily.
   * Refactor surgically when required.
   * Preserve all existing comments and documentation unless instructed otherwise.

4. **Minimal File Footprint**:
   * Do not create unnecessary empty files or speculative directory trees.
   * Create directories and files progressively as features are implemented.

5. **Component Boundary Enforcement**:
   * Keep Blender-specific code strictly inside `blender_addon/`.
   * Keep Unreal-specific code strictly inside `unreal_plugin/`.
   * Keep engine-agnostic schemas, validation logic, and canonical math inside `bridge_core/`.

---

## 3. Environment and Tooling Rules

1. **Blender Python Runtime Isolation**:
   * Treat **Blender's embedded Python runtime** as the *only* Python runtime relevant to the Blender add-on.
   * The host operating system's Python installation must **not** be assumed to be the Blender Python runtime and must **never** be used as the add-on execution runtime.
   * Add-on registration and unit tests must be targeted for execution via Blender headless mode (`blender --background --python ...`).

2. **Coordinate and Geometry Pipeline Verification**:
   * Do **not** assume that the Blender $\rightarrow$ glTF/GLB $\rightarrow$ Unreal coordinate and geometry pipeline is automatically correct.
   * Treat this pipeline as an area requiring explicit, empirical verification.
   * The transform and geometry pipeline must include dedicated test cases for:
     - Axis conversion ($+Z$ Up right-handed $\rightarrow$ $+Z$ Up left-handed)
     - Unit conversion (Meters $\rightarrow$ Centimeters, factor 100)
     - Rotations (Euler and Quaternion)
     - Parent-child relative transforms
     - Non-uniform scale
     - Negative scale (reflections)
     - Mesh polygon winding order
     - Split and vertex normals

3. **Authoritative Coordinate Conversion**:
   * Coordinate and unit conversions must reside in **exactly one authoritative module**.
   * Never scatter ad-hoc axis swaps or scale factors across exporters, importers, or helper functions.

4. **Unreal Plugin Validation Standards**:
   * Do **not** claim successful compilation of the Unreal plugin through generic syntax checks or standalone header compilation.
   * The only valid compilation target is successful compilation inside an Unreal Engine project using the **Unreal Build Tool (UBT)**.
   * If Unreal Engine is not available in the development environment, report the Unreal plugin as **structurally validated but not compiled**.

5. **Bridge Core Compilation Standards**:
   * Bridge Core must compile without errors under standard C++17/20 compilers (MSVC, Clang, GCC).
   * Warnings introduced by project code should be fixed where practical.
   * Do not treat third-party or compiler-specific warnings as automatic failures.

6. **Error Handling & Data Integrity**:
   * Never silently discard unsupported Blender data (e.g. unsupported shader nodes, modifier configurations).
   * Emit structured diagnostics using three explicit levels: `INFO`, `WARNING`, and `ERROR`.
