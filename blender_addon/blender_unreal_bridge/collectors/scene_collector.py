"""
Scene Collector
---------------
Traverses the active Blender scene and collects metadata for all relevant
objects into a structured, engine-independent representation.

Scope for Milestone 1:
  - Scene traversal via bpy.context.scene.objects
  - Relevant object type filtering
  - Stable bubridge_id assignment (via id_generator — not inline)
  - Collection membership extraction
  - Parent/child relationship metadata
  - Basic object metadata (id, name, type, collections, parent_id)

NOT in scope for this module:
  - Transform conversion or coordinate math
  - Geometry or mesh data extraction
  - Material or texture analysis
  - Animation data
  - .bubridge package serialization
  - Any Unreal Engine communication
"""

import bpy

from .id_generator import ensure_id, get_id, BUBRIDGE_ID_KEY

# Object types the bridge considers as exportable/relevant at this stage.
# This set will grow in later milestones (e.g. ARMATURE, LIGHT, CAMERA).
SUPPORTED_OBJECT_TYPES = frozenset({"MESH", "EMPTY", "CURVE"})


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class CollectionInfo:
    """Lightweight metadata for a Blender collection."""

    __slots__ = ("name",)

    def __init__(self, name: str):
        self.name = name

    def to_dict(self) -> dict:
        return {"name": self.name}


class ObjectMetadata:
    """
    Metadata for a single Blender object as seen by the Scene Collector.

    Fields
    ------
    bubridge_id : str
        Stable, persistent Bridge ID stored as a custom property on the object.
    name : str
        Current Blender object name (informational only — not used as identifier).
    object_type : str
        Blender object type string, e.g. 'MESH', 'EMPTY', 'CURVE'.
    collections : list[str]
        Names of all Blender collections this object is directly a member of.
    parent_id : str | None
        bubridge_id of the parent object, or None if there is no parent.
    """

    __slots__ = ("bubridge_id", "name", "object_type", "collections", "parent_id")

    def __init__(
        self,
        bubridge_id: str,
        name: str,
        object_type: str,
        collections: list,
        parent_id: str | None,
    ):
        self.bubridge_id = bubridge_id
        self.name = name
        self.object_type = object_type
        self.collections = collections
        self.parent_id = parent_id

    def to_dict(self) -> dict:
        return {
            "bubridge_id": self.bubridge_id,
            "name": self.name,
            "object_type": self.object_type,
            "collections": self.collections,
            "parent_id": self.parent_id,
        }


class SceneInspectionResult:
    """
    The complete output of a single scene inspection run.

    Fields
    ------
    scene_name : str
        Name of the inspected Blender scene.
    objects : list[ObjectMetadata]
        All collected object metadata records.
    warnings : list[str]
        Non-fatal issues encountered during inspection.
    errors : list[str]
        Fatal issues encountered during inspection.
    """

    def __init__(self, scene_name: str):
        self.scene_name: str = scene_name
        self.objects: list = []
        self.warnings: list = []
        self.errors: list = []

    def to_dict(self) -> dict:
        return {
            "scene_name": self.scene_name,
            "objects": [o.to_dict() for o in self.objects],
            "warnings": self.warnings,
            "errors": self.errors,
        }


# ---------------------------------------------------------------------------
# Collection membership helpers
# ---------------------------------------------------------------------------

def _get_collection_names_for_object(obj) -> list:
    """
    Return the names of all Blender collections that directly contain this
    object, excluding the scene's root collection.

    The root collection (bpy.context.scene.collection) is skipped because
    every object belongs to it implicitly and it carries no user-meaningful
    organisational information.

    Args:
        obj: A bpy.types.Object instance.

    Returns:
        A sorted list of collection name strings.
    """
    scene = bpy.context.scene
    root_collection = scene.collection
    result = []

    def _walk(collection, is_root: bool):
        if not is_root and obj.name in collection.objects:
            result.append(collection.name)
        for child in collection.children:
            _walk(child, False)

    _walk(root_collection, True)
    return sorted(result)


# ---------------------------------------------------------------------------
# Core collector
# ---------------------------------------------------------------------------

def collect_scene(scene=None) -> SceneInspectionResult:
    """
    Traverse the given Blender scene (or the active scene if None) and collect
    metadata for all relevant objects.

    This function:
      1. Iterates over every object in the scene.
      2. Filters to supported object types only.
      3. Assigns or retrieves the stable bubridge_id for each object.
      4. Records collection membership and parent relationships.
      5. Returns a SceneInspectionResult with all collected metadata.

    Unsupported object types are noted as INFO-level warnings rather than
    silently discarded, in accordance with project error-handling policy.

    Args:
        scene: An optional bpy.types.Scene. Defaults to bpy.context.scene.

    Returns:
        A SceneInspectionResult containing all gathered metadata.
    """
    if scene is None:
        scene = bpy.context.scene

    result = SceneInspectionResult(scene_name=scene.name)

    # First pass: ensure all supported objects have IDs assigned before
    # resolving parent references, so parent_id lookups are always valid even
    # if a parent object appears after its child in iteration order.
    for obj in scene.objects:
        if obj.type in SUPPORTED_OBJECT_TYPES:
            ensure_id(obj)

    # Second pass: collect full metadata now that all IDs exist.
    for obj in scene.objects:
        if obj.type not in SUPPORTED_OBJECT_TYPES:
            result.warnings.append(
                f"[INFO] Object '{obj.name}' has unsupported type '{obj.type}' — skipped."
            )
            continue

        bubridge_id = get_id(obj)
        if bubridge_id is None:
            # Should not happen after the first pass, but guard defensively.
            result.errors.append(
                f"[ERROR] Object '{obj.name}' did not receive a bubridge_id. Skipping."
            )
            continue

        parent_id = None
        if obj.parent is not None:
            parent_id = get_id(obj.parent)
            if parent_id is None:
                result.warnings.append(
                    f"[WARNING] Object '{obj.name}' has parent '{obj.parent.name}' "
                    f"which is not a supported type and has no bubridge_id. "
                    f"parent_id will be null."
                )

        collections = _get_collection_names_for_object(obj)

        metadata = ObjectMetadata(
            bubridge_id=bubridge_id,
            name=obj.name,
            object_type=obj.type,
            collections=collections,
            parent_id=parent_id,
        )
        result.objects.append(metadata)

    return result
