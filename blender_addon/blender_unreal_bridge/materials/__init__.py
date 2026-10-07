"""
materials
=========
Material extraction and serialization for the Blender Unreal Bridge.
"""

from .material_extractor import extract_material_data, MATERIAL_FORMAT, MATERIAL_VERSION

__all__ = [
    "extract_material_data",
    "MATERIAL_FORMAT",
    "MATERIAL_VERSION",
]
