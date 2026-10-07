"""
animation/skinning_extractor.py
===============================
Extracts vertex skinning weights and mesh-armature associations for Milestone 9.

Rules:
  - Discovers controlling Armature via Armature Modifier or direct parent.
  - Maps Blender vertex groups to stable Bone IDs.
  - Normalizes and sorts influences deterministically per vertex.
  - Limits influences to a maximum (default 8) without discarding significant weights.
"""

from typing import Any, Dict, List, Optional
import bpy

from ..collectors.id_generator import (
    ensure_skeleton_id,
    ensure_bone_id,
    get_bone_id,
)


def find_associated_armature(mesh_obj: bpy.types.Object) -> Optional[bpy.types.Object]:
    """
    Find the controlling Armature object for a given Mesh object.
    Inspects Armature modifiers first, then object parent.
    """
    if mesh_obj.type != "MESH":
        return None

    # 1. Inspect modifiers
    for mod in mesh_obj.modifiers:
        if mod.type == "ARMATURE" and getattr(mod, "object", None):
            arm_obj = mod.object
            if arm_obj and arm_obj.type == "ARMATURE":
                return arm_obj

    # 2. Check parent
    if mesh_obj.parent and mesh_obj.parent.type == "ARMATURE":
        return mesh_obj.parent

    return None


def extract_skinning_data(
    mesh_obj: bpy.types.Object,
    armature_obj: bpy.types.Object,
    mesh_data: bpy.types.Mesh,
    max_influences_per_vertex: int = 8,
) -> Optional[Dict[str, Any]]:
    """
    Extracts per-vertex skinning weights linking vertices to stable bone IDs.

    Args:
        mesh_obj: Blender Mesh Object (contains vertex groups).
        armature_obj: Blender Armature Object (contains bones).
        mesh_data: Blender Mesh datablock (contains vertices).
        max_influences_per_vertex: Max influences allowed per vertex (default 8).

    Returns:
        Dictionary conforming to BUBRIDGE_MESH skinning schema, or None if no valid weights.
    """
    if not armature_obj or armature_obj.type != "ARMATURE" or not armature_obj.data:
        return None

    skel_id = ensure_skeleton_id(armature_obj)
    armature_data = armature_obj.data

    # Map bone names to stable bone IDs
    bone_name_to_id: Dict[str, str] = {}
    for bone in armature_data.bones:
        bone_name_to_id[bone.name] = ensure_bone_id(bone)

    # Map vertex group index to bone ID
    vg_index_to_bone_id: Dict[int, str] = {}
    for vg_idx, vg in enumerate(mesh_obj.vertex_groups):
        if vg.name in bone_name_to_id:
            vg_index_to_bone_id[vg_idx] = bone_name_to_id[vg.name]

    if not vg_index_to_bone_id:
        return None

    influences_list: List[List[Dict[str, Any]]] = []

    vertices_source = mesh_data.vertices if hasattr(mesh_data, "vertices") else mesh_obj.data.vertices

    for v in vertices_source:
        vertex_infs = []
        for g in v.groups:
            bone_id = vg_index_to_bone_id.get(g.group)
            if bone_id and g.weight > 0.0001:
                vertex_infs.append({
                    "bone_id": bone_id,
                    "weight": float(g.weight),
                })

        # Sort deterministically: descending weight, then ascending bone_id
        vertex_infs.sort(key=lambda inf: (-inf["weight"], inf["bone_id"]))

        # Limit influences
        if len(vertex_infs) > max_influences_per_vertex:
            vertex_infs = vertex_infs[:max_influences_per_vertex]

        # Normalize weights so they sum to 1.0
        total_weight = sum(inf["weight"] for inf in vertex_infs)
        if total_weight > 1e-6:
            for inf in vertex_infs:
                inf["weight"] = round(inf["weight"] / total_weight, 6)
        else:
            # If vertex has 0 influences, pick the first root bone or first available bone
            if armature_data.bones:
                first_bone = armature_data.bones[0]
                vertex_infs = [{
                    "bone_id": ensure_bone_id(first_bone),
                    "weight": 1.0,
                }]

        influences_list.append(vertex_infs)

    return {
        "skeleton_id": skel_id,
        "influences": influences_list,
    }
