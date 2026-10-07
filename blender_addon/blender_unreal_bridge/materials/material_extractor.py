"""
materials/material_extractor.py
===============================
Authoritative Blender material extraction for the Blender Unreal Bridge.

Extracts non-textured PBR material properties from Blender material datablocks:
  - Base Color (RGBA)
  - Metallic [0.0, 1.0]
  - Roughness [0.0, 1.0]
  - Specular [0.0, 1.0]
  - IOR
  - Opacity [0.0, 1.0]
  - Blend Mode and Two Sided flag

Explicit Milestone 6 boundary:
  - Pure scalar/color PBR properties only.
  - Image texture extraction, texture maps, UV remapping, and texture baking are
    explicitly deferred to Milestone 7.
"""

from typing import Any, Dict, List, Optional
import math
import bpy

from ..collectors.id_generator import ensure_material_id
from .texture_extractor import extract_material_textures

MATERIAL_FORMAT = "BUBRIDGE_MATERIAL"
MATERIAL_VERSION = "0.1.0"


def _clamp(val: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp a float to [min_val, max_val] with NaN/Inf protection."""
    if not math.isfinite(val):
        return min_val
    return max(min_val, min(max_val, val))


def _extract_socket_value(socket, default_val: float) -> float:
    """Safely extract a float default value from a node socket."""
    if socket is None or not hasattr(socket, "default_value"):
        return default_val
    try:
        val = float(socket.default_value)
        return val if math.isfinite(val) else default_val
    except (ValueError, TypeError):
        return default_val


def _extract_color_socket(socket, default_color: List[float]) -> List[float]:
    """Safely extract a 4-channel RGBA color from a node socket."""
    if socket is None or not hasattr(socket, "default_value"):
        return list(default_color)
    try:
        dv = socket.default_value
        if hasattr(dv, "__iter__"):
            vals = [float(c) for c in dv]
            # Ensure 4 channels
            while len(vals) < 4:
                vals.append(1.0 if len(vals) == 3 else 0.0)
            return [_clamp(v, 0.0, 1.0) for v in vals[:4]]
    except (ValueError, TypeError):
        pass
    return list(default_color)


def extract_material_data(mat: Optional[bpy.types.Material]) -> Dict[str, Any]:
    """
    Extract canonical PBR material parameters from a Blender Material datablock.

    Args:
        mat: Blender Material datablock (or None for default fallback).

    Returns:
        Dictionary conforming to BUBRIDGE_MATERIAL v0.1.0 schema.
    """
    if mat is None:
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "format": MATERIAL_FORMAT,
            "version": MATERIAL_VERSION,
            "material_id": "mat_default",
            "name": "DefaultMaterial",
            "model": "PBR_METALLIC_ROUGHNESS",
            "base_color": [0.8, 0.8, 0.8, 1.0],
            "metallic": 0.0,
            "roughness": 0.5,
            "specular": 0.5,
            "ior": 1.5,
            "opacity": 1.0,
            "blend_mode": "OPAQUE",
            "two_sided": False,
            "textures": {},
        }

    # Stable, deterministic material ID
    mat_id = ensure_material_id(mat)
    name = mat.name

    # Default PBR values
    base_color = [0.8, 0.8, 0.8, 1.0]
    metallic = 0.0
    roughness = 0.5
    specular = 0.5
    ior = 1.5
    opacity = 1.0
    blend_mode = "OPAQUE"
    two_sided = False

    # Check two-sided flag (defaults to False for standard PBR; enabled if explicitly configured)
    two_sided = bool(mat.get("two_sided", False) or mat.get("bubridge_two_sided", False))

    # Inspect node tree if enabled
    if mat.use_nodes and mat.node_tree:
        # Find Principled BSDF node
        principled_node = None
        for node in mat.node_tree.nodes:
            if node.type == "BSDF_PRINCIPLED":
                principled_node = node
                break

        if principled_node is not None:
            inputs = principled_node.inputs

            # Base Color
            base_col_socket = inputs.get("Base Color")
            if base_col_socket:
                raw_color = _extract_color_socket(base_col_socket, [0.8, 0.8, 0.8, 1.0])
                base_color = [round(c, 6) for c in raw_color]

            # Metallic
            met_socket = inputs.get("Metallic")
            if met_socket:
                metallic = round(_clamp(_extract_socket_value(met_socket, 0.0)), 6)

            # Roughness
            rough_socket = inputs.get("Roughness")
            if rough_socket:
                roughness = round(_clamp(_extract_socket_value(rough_socket, 0.5)), 6)

            # Specular: check "Specular IOR Level" (Blender 4.0+), fallback to "Specular" (Blender <4.0)
            spec_socket = inputs.get("Specular IOR Level") or inputs.get("Specular")
            if spec_socket:
                specular = round(_clamp(_extract_socket_value(spec_socket, 0.5)), 6)

            # IOR
            ior_socket = inputs.get("IOR")
            if ior_socket:
                val = _extract_socket_value(ior_socket, 1.5)
                ior = round(max(0.0, val), 6)

            # Alpha / Opacity
            alpha_socket = inputs.get("Alpha")
            if alpha_socket:
                opacity = round(_clamp(_extract_socket_value(alpha_socket, 1.0)), 6)
                base_color[3] = opacity
        else:
            # Fallback for non-principled nodes: use diffuse_color if set
            if hasattr(mat, "diffuse_color"):
                raw_color = [float(c) for c in mat.diffuse_color]
                base_color = [round(_clamp(c), 6) for c in raw_color[:4]]
    else:
        # Material without node tree: read diffuse_color
        if hasattr(mat, "diffuse_color"):
            raw_color = [float(c) for c in mat.diffuse_color]
            base_color = [round(_clamp(c), 6) for c in raw_color[:4]]

    # Map blend mode
    blend_mode = "OPAQUE"
    if hasattr(mat, "blend_method"):
        bm = str(mat.blend_method).upper()
        if bm == "CLIP":
            blend_mode = "MASKED"
        elif bm == "BLEND":
            blend_mode = "TRANSLUCENT"
        elif bm == "HASHED":
            # In Blender 4.2+, HASHED is the default on EEVEE Next.
            # Only treat as translucent if opacity is genuinely below 1.0.
            blend_mode = "TRANSLUCENT" if opacity < 0.999 else "OPAQUE"
        elif opacity < 0.999:
            blend_mode = "TRANSLUCENT"
        else:
            blend_mode = "OPAQUE"
    elif opacity < 0.999:
        blend_mode = "TRANSLUCENT"

    textures_map, _, _ = extract_material_textures(mat)

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "format": MATERIAL_FORMAT,
        "version": MATERIAL_VERSION,
        "material_id": mat_id,
        "name": name,
        "model": "PBR_METALLIC_ROUGHNESS",
        "base_color": base_color,
        "metallic": metallic,
        "roughness": roughness,
        "specular": specular,
        "ior": ior,
        "opacity": opacity,
        "blend_mode": blend_mode,
        "two_sided": two_sided,
        "textures": textures_map,
    }
