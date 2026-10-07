"""
animation/armature_extractor.py
===============================
Authoritative Blender armature and bone hierarchy extraction for Milestone 9.

Extracts:
  - Armature objects and skeleton identity (skel_<8 hex chars>)
  - Bone hierarchies (root bones, child bones, arbitrary depth)
  - Stable bone identifiers (bone_<8 hex chars>)
  - Parent-relative bone rest transforms converted to canonical Bridge coordinates
  - Deterministic topological ordering (roots first, sorted by name)
"""

from typing import Any, Dict, List, Optional
import bpy
from mathutils import Matrix

from ..collectors.id_generator import (
    ensure_skeleton_id,
    get_skeleton_id,
    ensure_bone_id,
    get_bone_id,
    get_id,
)
from ..transforms.canonical import (
    _convert_location,
    _convert_quaternion,
    _convert_scale,
    _quat_to_euler_deg_xyz,
)


def extract_skeleton_data(armature_obj: bpy.types.Object) -> Dict[str, Any]:
    """
    Extracts complete skeleton and bone hierarchy data from a Blender ARMATURE object.

    Args:
        armature_obj: Blender Object with type == 'ARMATURE'.

    Returns:
        Dictionary conforming to BUBRIDGE_ANIMATIONS skeleton schema.
    """
    if armature_obj.type != "ARMATURE" or not armature_obj.data:
        raise ValueError(f"Object '{armature_obj.name}' is not an ARMATURE object.")

    # 1. Stable Skeleton ID
    skel_id = ensure_skeleton_id(armature_obj)
    armature_data = armature_obj.data

    # Ensure all bones have stable IDs assigned
    for bone in armature_data.bones:
        ensure_bone_id(bone)

    # 2. Extract bones with rest transforms
    bone_entries = {}
    for bone in armature_data.bones:
        bone_id = get_bone_id(bone)
        parent_id = get_bone_id(bone.parent) if bone.parent else None

        # Parent-relative rest transform
        # bone.matrix_local is bone rest pose relative to armature object
        if bone.parent:
            parent_rest_inv = bone.parent.matrix_local.inverted()
            local_rest_matrix = parent_rest_inv @ bone.matrix_local
        else:
            local_rest_matrix = bone.matrix_local.copy()

        loc, rot, sc = local_rest_matrix.decompose()

        canon_loc = _convert_location((loc.x, loc.y, loc.z))
        canon_rot = _convert_quaternion((rot.w, rot.x, rot.y, rot.z))
        canon_sc = _convert_scale((sc.x, sc.y, sc.z))

        transform_dict = {
            "location": [round(c, 6) for c in canon_loc],
            "rotation_quaternion": [round(c, 6) for c in canon_rot],
            "rotation_euler": [round(c, 4) for c in _quat_to_euler_deg_xyz(canon_rot)],
            "rotation_mode": "QUATERNION",
            "scale": [round(c, 6) for c in canon_sc],
            "has_negative_scale": any(s < 0.0 for s in canon_sc),
            "origin_offset": [0.0, 0.0, 0.0],
        }

        bone_entries[bone.name] = {
            "id": bone_id,
            "name": bone.name,
            "parent_id": parent_id,
            "transform": transform_dict,
        }

    # 3. Deterministic topological sort: roots first, children after parent
    ordered_bones: List[Dict[str, Any]] = []
    visited_names = set()

    # Find root bones sorted alphabetically
    root_bones = sorted([b for b in armature_data.bones if b.parent is None], key=lambda b: b.name)
    queue = list(root_bones)

    while queue:
        curr_bone = queue.pop(0)
        if curr_bone.name in visited_names:
            continue
        visited_names.add(curr_bone.name)

        if curr_bone.name in bone_entries:
            ordered_bones.append(bone_entries[curr_bone.name])

        # Add children sorted alphabetically
        children = sorted(list(curr_bone.children), key=lambda b: b.name)
        for child in children:
            queue.append(child)

    # Fallback in case of disconnected or cyclic loops
    for bone in sorted(armature_data.bones, key=lambda b: b.name):
        if bone.name not in visited_names and bone.name in bone_entries:
            ordered_bones.append(bone_entries[bone.name])

    return {
        "id": skel_id,
        "name": armature_obj.name,
        "armature_object_id": get_id(armature_obj),
        "bones": ordered_bones,
    }
