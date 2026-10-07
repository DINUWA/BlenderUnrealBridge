"""
geometry/mesh_extractor.py
==========================
Authoritative Blender mesh geometry extraction for the Blender Unreal Bridge.

Extracts static mesh geometry into canonical Bridge coordinates:
  - Coordinate system: Left-Handed, Z-Up, Centimeters
  - Winding order: Flipped for Left-Handed space (v0, v2, v1)
  - Split / corner normals and UV coordinates preserved
  - Non-destructive: evaluated geometry without modifying source Blender mesh
  - Material slot indices mapped to triangles
"""

from typing import Any, Dict, List, Optional
import math
import bpy

from ..collectors.id_generator import ensure_mesh_id, ensure_material_id

# Canonical format identifiers
MESH_FORMAT = "BUBRIDGE_MESH"
MESH_VERSION = "0.1.0"


def _convert_vertex_to_canonical(co) -> List[float]:
    """
    Convert a Blender vertex coordinate (Right-Handed, Z-Up, Meters)
    into Canonical Bridge coordinate (Left-Handed, Z-Up, Centimeters).
      Canon_X = Blender_Y * 100.0
      Canon_Y = Blender_X * 100.0
      Canon_Z = Blender_Z * 100.0
    """
    return [
        round(float(co[1]) * 100.0, 6),
        round(float(co[0]) * 100.0, 6),
        round(float(co[2]) * 100.0, 6)
    ]


def _convert_normal_to_canonical(normal) -> List[float]:
    """
    Convert a Blender normal direction vector into Canonical Bridge coordinates.
      Canon_Nx = Blender_Ny
      Canon_Ny = Blender_Nx
      Canon_Nz = Blender_Nz
    Normalizes the vector to unit length.
    """
    nx = float(normal[1])
    ny = float(normal[0])
    nz = float(normal[2])
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length > 1e-6:
        nx /= length
        ny /= length
        nz /= length
    else:
        nx, ny, nz = 0.0, 0.0, 1.0

    return [round(nx, 6), round(ny, 6), round(nz, 6)]


def extract_mesh_data(obj: bpy.types.Object, depsgraph: Optional[bpy.types.Depsgraph] = None) -> Dict[str, Any]:
    """
    Extracts complete canonical mesh geometry from a Blender MESH object.

    Args:
        obj: Blender Object with type == 'MESH'.
        depsgraph: Optional dependency graph for modifier evaluation.

    Returns:
        Dictionary conforming to the BUBRIDGE_MESH schema.
    """
    if obj.type != 'MESH' or not obj.data:
        raise ValueError(f"Object '{obj.name}' is not a valid MESH object.")

    # 1. Stable Mesh Asset ID
    mesh_id = ensure_mesh_id(obj.data)

    # 2. Non-destructive evaluated mesh extraction
    eval_obj = obj.evaluated_get(depsgraph) if depsgraph else obj
    mesh = eval_obj.to_mesh() if depsgraph else obj.data

    try:
        # Ensure triangulated loops and normals are calculated
        mesh.calc_loop_triangles()

        # Try calculating split normals if supported
        try:
            mesh.calc_normals_split()
        except Exception:
            pass

        # 3. Extract Canonical Vertices
        vertices: List[List[float]] = []
        min_x = min_y = min_z = float("inf")
        max_x = max_y = max_z = float("-inf")

        for v in mesh.vertices:
            canon_co = _convert_vertex_to_canonical(v.co)
            vertices.append(canon_co)

            min_x = min(min_x, canon_co[0])
            min_y = min(min_y, canon_co[1])
            min_z = min(min_z, canon_co[2])
            max_x = max(max_x, canon_co[0])
            max_y = max(max_y, canon_co[1])
            max_z = max(max_z, canon_co[2])

        if not vertices:
            min_x = min_y = min_z = 0.0
            max_x = max_y = max_z = 0.0

        bounds = {
            "min": [min_x, min_y, min_z],
            "max": [max_x, max_y, max_z]
        }

        # 4. Extract UV Layers
        uv_layer = mesh.uv_layers.active

        # 5. Extract Triangles with Left-Handed winding flip
        triangles: List[Dict[str, Any]] = []

        for lt in mesh.loop_triangles:
            # Blender right-handed triangle corners: (0, 1, 2)
            # Left-handed flipped winding order: (0, 2, 1)
            v0, v1, v2 = lt.vertices[0], lt.vertices[1], lt.vertices[2]
            l0, l1, l2 = lt.loops[0], lt.loops[1], lt.loops[2]

            # Flipped corners: corner 0, corner 2, corner 1
            tri_vertex_indices = [int(v0), int(v2), int(v1)]

            # Normals per corner
            n0 = _convert_normal_to_canonical(mesh.loops[l0].normal)
            n1 = _convert_normal_to_canonical(mesh.loops[l1].normal)
            n2 = _convert_normal_to_canonical(mesh.loops[l2].normal)
            tri_normals = [n0, n2, n1]

            # UVs per corner
            if uv_layer and len(uv_layer.data) > max(l0, l1, l2):
                uv0 = [round(float(uv_layer.data[l0].uv[0]), 6), round(float(uv_layer.data[l0].uv[1]), 6)]
                uv1 = [round(float(uv_layer.data[l1].uv[0]), 6), round(float(uv_layer.data[l1].uv[1]), 6)]
                uv2 = [round(float(uv_layer.data[l2].uv[0]), 6), round(float(uv_layer.data[l2].uv[1]), 6)]
                tri_uvs = [uv0, uv2, uv1]
            else:
                tri_uvs = [[0.0, 0.0], [0.0, 0.0], [0.0, 0.0]]

            mat_slot_idx = int(lt.material_index)

            triangles.append({
                "vertex_indices": tri_vertex_indices,
                "normals": tri_normals,
                "uvs": tri_uvs,
                "material_slot_index": mat_slot_idx
            })

        # 6. Extract Material Slots
        material_slots: List[Dict[str, Any]] = []
        for idx, slot in enumerate(obj.material_slots):
            material_slots.append({
                "slot_index": idx,
                "slot_name": slot.name if slot.name else f"Material_Slot_{idx}",
                "material_id": ensure_material_id(slot.material) if slot.material else None
            })

        if not material_slots:
            material_slots.append({
                "slot_index": 0,
                "slot_name": "DefaultMaterial",
                "material_id": None
            })

        uv_layer_count = len(mesh.uv_layers)

        payload = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "format": MESH_FORMAT,
            "version": MESH_VERSION,
            "mesh_id": mesh_id,
            "name": obj.data.name,
            "source": {
                "application": "Blender",
                "version": bpy.app.version_string
            },
            "coordinate_system": {
                "up_axis": "Z",
                "forward_axis": "X",
                "right_axis": "Y",
                "handedness": "left_handed",
                "unit": "centimeter"
            },
            "counts": {
                "vertex_count": len(vertices),
                "triangle_count": len(triangles),
                "uv_layer_count": uv_layer_count,
                "material_slot_count": len(material_slots)
            },
            "bounds": bounds,
            "vertices": vertices,
            "triangles": triangles,
            "material_slots": material_slots
        }

        # 6. Extract Skinning Weights (Milestone 9)
        from ..animation.skinning_extractor import find_associated_armature, extract_skinning_data
        arm_obj = find_associated_armature(obj)
        if arm_obj and len(obj.vertex_groups) > 0:
            skinning_info = extract_skinning_data(obj, arm_obj, mesh)
            if skinning_info:
                payload["skinning"] = skinning_info

        return payload

    finally:
        if depsgraph and eval_obj != obj:
            eval_obj.to_mesh_clear()
