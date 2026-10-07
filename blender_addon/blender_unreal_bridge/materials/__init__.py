"""
materials
=========
Material and texture extraction and serialization for the Blender Unreal Bridge.
"""

from .material_extractor import extract_material_data, MATERIAL_FORMAT, MATERIAL_VERSION
from .texture_extractor import (
    extract_texture_from_image,
    extract_material_textures,
    TEXTURE_FORMAT,
    TEXTURE_VERSION,
)

__all__ = [
    "extract_material_data",
    "MATERIAL_FORMAT",
    "MATERIAL_VERSION",
    "extract_texture_from_image",
    "extract_material_textures",
    "TEXTURE_FORMAT",
    "TEXTURE_VERSION",
]
