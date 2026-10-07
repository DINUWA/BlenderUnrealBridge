"""
materials/texture_extractor.py
==============================
Authoritative Blender image texture extraction for the Blender Unreal Bridge.

Extracts semantic PBR texture mappings and metadata from Blender materials:
  - Base Color (sRGB)
  - Roughness (Linear / Non-Color)
  - Metallic (Linear / Non-Color)
  - Normal Map (Linear / Non-Color via Normal Map node or direct)
  - Alpha (opacity)

Handles:
  - Stable texture IDs (tex_<8 hex chars>)
  - Deduplication across materials
  - Path resolution (Blender relative '//', absolute, and packed images)
  - Color space validation and diagnostics
  - Missing texture diagnostics (TEX_FILE_NOT_FOUND)
  - Non-destructive execution
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import bpy

from ..collectors.id_generator import ensure_texture_id

TEXTURE_FORMAT = "BUBRIDGE_TEXTURE"
TEXTURE_VERSION = "0.1.0"


def _resolve_image_format(image: bpy.types.Image) -> Tuple[str, str]:
    """
    Determine the texture file extension and format string from a Blender Image.

    Returns:
        Tuple of (extension with leading dot, format string e.g. 'PNG')
    """
    ext = ""
    if image.filepath:
        ext = Path(image.filepath).suffix.lower()

    file_format = getattr(image, "file_format", "PNG")
    fmt_map = {
        "PNG": ".png",
        "JPEG": ".jpg",
        "TARGA": ".tga",
        "TARGA_RAW": ".tga",
        "OPEN_EXR": ".exr",
        "OPEN_EXR_MULTILAYER": ".exr",
        "TIFF": ".tif",
        "BMP": ".bmp",
        "HDR": ".hdr",
    }

    if not ext or ext == ".":
        ext = fmt_map.get(file_format, ".png")

    fmt_name = file_format if file_format else "PNG"
    if ext in (".jpg", ".jpeg"):
        fmt_name = "JPEG"
    elif ext == ".png":
        fmt_name = "PNG"
    elif ext == ".tga":
        fmt_name = "TARGA"
    elif ext == ".exr":
        fmt_name = "EXR"

    return ext, fmt_name


def _normalize_color_space(cs_name: str) -> str:
    """Normalize Blender color space name to canonical 'sRGB' or 'Linear'."""
    cs_lower = cs_name.lower()
    if "srgb" in cs_lower:
        return "sRGB"
    return "Linear"


def extract_texture_from_image(
    image: bpy.types.Image,
    semantic_channel: str,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Extract canonical texture metadata from a Blender Image datablock.

    Args:
        image: Blender Image datablock.
        semantic_channel: Channel role ('base_color', 'roughness', 'metallic', 'normal').

    Returns:
        Tuple of (metadata_dict, diagnostics_list).
    """
    diagnostics: List[Dict[str, Any]] = []

    tex_id = ensure_texture_id(image)
    ext, fmt_name = _resolve_image_format(image)
    relative_path = f"textures/{tex_id}{ext}"

    # Determine color space
    raw_cs = "sRGB"
    if hasattr(image, "colorspace_settings") and image.colorspace_settings.name:
        raw_cs = image.colorspace_settings.name
    canonical_cs = _normalize_color_space(raw_cs)

    # Validate color space expectations
    if semantic_channel == "base_color":
        if canonical_cs != "sRGB":
            diagnostics.append({
                "level": "WARNING",
                "code": "TEX_COLORSPACE_MISMATCH",
                "target_id": tex_id,
                "message": (
                    f"Texture '{image.name}' ({tex_id}) used as Base Color has color space '{raw_cs}', "
                    "expected 'sRGB'."
                ),
            })
    elif semantic_channel in ("roughness", "metallic", "normal"):
        if canonical_cs == "sRGB":
            diagnostics.append({
                "level": "WARNING",
                "code": "TEX_COLORSPACE_MISMATCH",
                "target_id": tex_id,
                "message": (
                    f"Texture '{image.name}' ({tex_id}) used as {semantic_channel} has color space '{raw_cs}', "
                    "expected 'Linear' / 'Non-Color'."
                ),
            })

    # Check packed vs external file
    is_packed = bool(getattr(image, "packed_file", None))
    source_path: Optional[str] = None

    if not is_packed:
        if image.filepath:
            source_path = bpy.path.abspath(image.filepath)
            if not Path(source_path).is_file():
                diagnostics.append({
                    "level": "ERROR",
                    "code": "TEX_FILE_NOT_FOUND",
                    "target_id": tex_id,
                    "message": f"Texture file '{source_path}' for image '{image.name}' does not exist on disk.",
                })
        else:
            diagnostics.append({
                "level": "ERROR",
                "code": "TEX_FILE_NOT_FOUND",
                "target_id": tex_id,
                "message": f"Image '{image.name}' has no filepath and is not packed.",
            })

    # Dimensions
    width, height = 1, 1
    if hasattr(image, "size") and len(image.size) >= 2:
        width = int(image.size[0]) if image.size[0] > 0 else 1
        height = int(image.size[1]) if image.size[1] > 0 else 1

    channels = int(getattr(image, "channels", 4))
    if channels <= 0:
        channels = 4

    has_alpha = (channels == 4) or (getattr(image, "depth", 0) in (32, 64))

    compression_settings = "TC_Normalmap" if semantic_channel == "normal" else "TC_Default"

    metadata: Dict[str, Any] = {
        "id": tex_id,
        "name": image.name,
        "relative_path": relative_path,
        "format": fmt_name,
        "color_space": canonical_cs,
        "dimensions": [width, height],
        "channels": channels,
        "has_alpha": has_alpha,
        "compression_settings": compression_settings,
        "_is_packed": is_packed,
        "_source_path": source_path,
        "_image": image,
    }

    return metadata, diagnostics


def _find_texture_node_connected_to_socket(socket) -> Optional[bpy.types.ShaderNodeTexImage]:
    """Find a ShaderNodeTexImage connected directly or through reroutes to a socket."""
    if not socket or not socket.is_linked:
        return None

    for link in socket.links:
        from_node = link.from_node
        if from_node.type == "TEX_IMAGE" and getattr(from_node, "image", None):
            return from_node
        # Handle reroutes
        if from_node.type == "REROUTE":
            rec_node = _find_texture_node_connected_to_socket(from_node.inputs[0])
            if rec_node:
                return rec_node

    return None


def extract_material_textures(
    mat: Optional[bpy.types.Material],
) -> Tuple[Dict[str, str], Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Inspect a Blender Material and extract connected PBR image textures.

    Args:
        mat: Blender Material datablock.

    Returns:
        Tuple containing:
          - material_textures_map: Dict mapping channel ('base_color', 'roughness', etc.) -> texture_id
          - discovered_textures: Dict mapping texture_id -> texture_metadata_dict
          - diagnostics: List of diagnostic dictionaries
    """
    textures_map: Dict[str, str] = {}
    discovered_textures: Dict[str, Dict[str, Any]] = {}
    diagnostics: List[Dict[str, Any]] = []

    if mat is None or not mat.use_nodes or not mat.node_tree:
        return textures_map, discovered_textures, diagnostics

    # Find Principled BSDF node
    principled_node = None
    for node in mat.node_tree.nodes:
        if node.type == "BSDF_PRINCIPLED":
            principled_node = node
            break

    if principled_node is None:
        return textures_map, discovered_textures, diagnostics

    inputs = principled_node.inputs

    # 1. Base Color
    base_col_socket = inputs.get("Base Color")
    tex_node = _find_texture_node_connected_to_socket(base_col_socket)
    if tex_node and tex_node.image:
        meta, diags = extract_texture_from_image(tex_node.image, "base_color")
        textures_map["base_color"] = meta["id"]
        discovered_textures[meta["id"]] = meta
        diagnostics.extend(diags)

    # 2. Roughness
    rough_socket = inputs.get("Roughness")
    tex_node = _find_texture_node_connected_to_socket(rough_socket)
    if tex_node and tex_node.image:
        meta, diags = extract_texture_from_image(tex_node.image, "roughness")
        textures_map["roughness"] = meta["id"]
        discovered_textures[meta["id"]] = meta
        diagnostics.extend(diags)

    # 3. Metallic
    met_socket = inputs.get("Metallic")
    tex_node = _find_texture_node_connected_to_socket(met_socket)
    if tex_node and tex_node.image:
        meta, diags = extract_texture_from_image(tex_node.image, "metallic")
        textures_map["metallic"] = meta["id"]
        discovered_textures[meta["id"]] = meta
        diagnostics.extend(diags)

    # 4. Normal
    norm_socket = inputs.get("Normal")
    if norm_socket and norm_socket.is_linked:
        for link in norm_socket.links:
            from_node = link.from_node
            # Check for Normal Map node: Principled -> Normal Map -> Image Texture
            if from_node.type == "NORMAL_MAP":
                color_socket = from_node.inputs.get("Color")
                tex_node = _find_texture_node_connected_to_socket(color_socket)
                if tex_node and tex_node.image:
                    meta, diags = extract_texture_from_image(tex_node.image, "normal")
                    textures_map["normal"] = meta["id"]
                    discovered_textures[meta["id"]] = meta
                    diagnostics.extend(diags)
                    break
            elif from_node.type == "TEX_IMAGE" and getattr(from_node, "image", None):
                meta, diags = extract_texture_from_image(from_node.image, "normal")
                textures_map["normal"] = meta["id"]
                discovered_textures[meta["id"]] = meta
                diagnostics.extend(diags)
                break

    return textures_map, discovered_textures, diagnostics
