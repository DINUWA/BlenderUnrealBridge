"""
Package Writer
--------------
Serializes collected scene and canonical transform data into a deterministic,
schema-compliant .bubridge package on disk.

Ensures:
  - Deterministic serialization (sorted object lists, consistent formatting)
  - Full pre-write validation (aborts on errors to prevent corrupt packages)
  - Atomic writing via temporary staging directory to avoid partial writes
  - Structured diagnostic reporting conforming to DATA_PROTOCOL.md
"""

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional, Union
import uuid

import bpy

from ..collectors.scene_collector import collect_scene
from ..geometry.mesh_extractor import extract_mesh_data
from ..version import FORMAT_NAME, FORMAT_VERSION, VERSION_STRING
from .json_serializer import serialize_json
from .package_validator import PackageValidator, ValidationResult


class PackageValidationError(Exception):
    """Raised when package data fails validation."""

    def __init__(self, message: str, validation_result: ValidationResult):
        super().__init__(message)
        self.validation_result = validation_result


def _generate_collection_id(name: str) -> str:
    """Generate a stable, deterministic collection ID based on collection name."""
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:8]
    return f"col_{digest}"


def _map_object_type(blender_type: str) -> str:
    """Map Blender object types to DATA_PROTOCOL.md canonical types."""
    if blender_type == "MESH":
        return "STATIC_MESH"
    if blender_type == "EMPTY":
        return "EMPTY"
    if blender_type == "CURVE":
        return "STATIC_MESH"
    return blender_type


def build_package_data(
    scene: Optional[bpy.types.Scene] = None,
    created_at: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Collect scene data, canonical transforms, and assemble the full package model in memory.

    Args:
        scene: bpy.types.Scene instance (defaults to bpy.context.scene).
        created_at: Optional ISO 8601 UTC timestamp string for deterministic testing.
                    If omitted, current UTC time is used.

    Returns:
        Dictionary containing 'manifest', 'scene', 'objects', and 'validation_result'.
    """
    if scene is None:
        scene = bpy.context.scene

    timestamp = created_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. Collect scene with canonical transforms (Milestone 1 + 2 integration)
    inspection = collect_scene(scene, extract_transforms=True)

    # 2. Build Collections Metadata
    collections_list: List[Dict[str, Any]] = []
    col_name_to_id: Dict[str, str] = {}

    def _traverse_collection(col: bpy.types.Collection, parent_id: Optional[str] = None):
        col_id = _generate_collection_id(col.name)
        col_name_to_id[col.name] = col_id

        color_tag = getattr(col, "color_tag", "NONE")
        collections_list.append({
            "id": col_id,
            "name": col.name,
            "parent_id": parent_id,
            "color_tag": color_tag,
        })
        for child in col.children:
            _traverse_collection(child, parent_id=col_id)

    # Traverse user collections linked to scene
    for child_col in scene.collection.children:
        _traverse_collection(child_col, parent_id=None)

    # Sort collections deterministically by ID
    collections_list.sort(key=lambda c: c["id"])

    # 3. Build Objects List and Mesh Payloads
    objects_list: List[Dict[str, Any]] = []
    meshes_dict: Dict[str, Dict[str, Any]] = {}

    for meta in inspection.objects:
        obj = scene.objects.get(meta.name)
        is_visible = True
        if obj is not None:
            # Check visibility
            is_visible = not (obj.hide_viewport or obj.hide_render)

        # Primary collection assignment
        col_id: Optional[str] = None
        if meta.collections:
            primary_col_name = meta.collections[0]
            col_id = col_name_to_id.get(primary_col_name)

        # Transform dictionary from Milestone 2 canonical representation
        transform_dict = (
            meta.transform.to_dict()["transform"]
            if meta.transform is not None
            else {
                "location": [0.0, 0.0, 0.0],
                "rotation_quaternion": [0.0, 0.0, 0.0, 1.0],
                "rotation_euler": [0.0, 0.0, 0.0],
                "rotation_mode": "QUATERNION",
                "scale": [1.0, 1.0, 1.0],
                "has_negative_scale": False,
                "origin_offset": [0.0, 0.0, 0.0],
            }
        )

        mesh_ref = None
        mat_slots = []
        if meta.object_type == "MESH" and obj is not None and getattr(obj, "data", None):
            try:
                mesh_data = extract_mesh_data(obj)
                mesh_id = mesh_data["mesh_id"]
                if mesh_id not in meshes_dict:
                    meshes_dict[mesh_id] = mesh_data

                mesh_ref = {
                    "mesh_id": mesh_id,
                    "file": f"meshes/{mesh_id}.json",
                    "submesh_index": 0,
                }
                mat_slots = mesh_data.get("material_slots", [])
            except Exception as exc:
                inspection.errors.append(f"Failed to extract mesh geometry for '{meta.name}': {exc}")

        obj_data = {
            "id": meta.bubridge_id,
            "name": meta.name,
            "type": _map_object_type(meta.object_type),
            "visible": is_visible,
            "collection_id": col_id,
            "parent_id": meta.parent_id,
            "transform": transform_dict,
            "mesh_reference": mesh_ref,
            "material_slots": mat_slots,
        }
        objects_list.append(obj_data)

    # Sort objects deterministically by Bridge ID
    objects_list.sort(key=lambda o: o["id"])

    # 4. Build Scene Model
    scene_dict = {
        "name": scene.name,
        "collections": collections_list,
        "environment": {
            "background_color": [0.05, 0.05, 0.05, 1.0],
            "ambient_intensity": 1.0,
        },
    }

    # 5. Build Manifest Model
    unit_scale = (
        scene.unit_settings.scale_length
        if hasattr(scene, "unit_settings")
        else 1.0
    )

    manifest_dict = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "format": FORMAT_NAME,
        "version": FORMAT_VERSION,
        "created_at": timestamp,
        "generator": {
            "name": "BlenderUnrealBridgeAddon",
            "version": VERSION_STRING,
        },
        "source": {
            "application": "Blender",
            "version": bpy.app.version_string,
            "scene_name": scene.name,
            "unit_length": "meter",
            "unit_scale": unit_scale,
        },
        "target": {
            "application": "Unreal Engine",
            "version": "5.x",
            "unit_length": "centimeter",
        },
        "coordinate_system": {
            "up_axis": "Z",
            "forward_axis": "X",
            "right_axis": "Y",
            "handedness": "left_handed",
            "unit": "centimeter",
        },
        "content_summary": {
            "object_count": len(objects_list),
            "mesh_count": len(meshes_dict),
            "material_count": 0,
            "texture_count": 0,
        },
    }

    objects_dict = {"objects": objects_list}

    # 6. Run validation
    validation_result = PackageValidator.validate_package(manifest_dict, scene_dict, objects_dict, meshes=meshes_dict)

    # Transfer inspection warnings/errors into the validation result
    for w in inspection.warnings:
        validation_result.add_warning("SCENE_INSPECTION_WARNING", w)
    for e in inspection.errors:
        validation_result.add_error("SCENE_INSPECTION_ERROR", e)

    return {
        "manifest": manifest_dict,
        "scene": scene_dict,
        "objects": objects_dict,
        "meshes": meshes_dict,
        "validation_result": validation_result,
        "timestamp": timestamp,
    }


def write_bridge_package(
    package_data: Dict[str, Any],
    output_directory: Union[str, Path],
    package_name: Optional[str] = None,
) -> Path:
    """
    Write the assembled package model to disk as a .bubridge directory package.

    Validates before writing and writes atomically via staging to prevent corrupt or partial packages.

    Args:
        package_data: Data returned by build_package_data().
        output_directory: Directory in which to create the package, or direct package path.
        package_name: Name of package (without .bubridge). If None, inferred from scene name.

    Returns:
        Path to the completed, validated .bubridge package.

    Raises:
        PackageValidationError: If package validation reports fatal errors.
        IOError: If writing to disk fails.
    """
    validation_result: ValidationResult = package_data["validation_result"]
    if not validation_result.is_valid:
        raise PackageValidationError(
            f"Package validation failed with {validation_result.error_count} error(s).",
            validation_result,
        )

    out_path = Path(output_directory).resolve()
    if out_path.suffix == ".bubridge":
        package_dir = out_path
    else:
        pkg_name = package_name or package_data["scene"]["name"]
        package_dir = out_path / f"{pkg_name}.bubridge"

    # Temporary staging directory for atomic commit
    stage_dir = package_dir.parent / f".tmp_{uuid.uuid4().hex[:8]}_{package_dir.name}"
    stage_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1. Write manifest.json
        manifest_content = serialize_json(package_data["manifest"])
        (stage_dir / "manifest.json").write_text(manifest_content, encoding="utf-8")

        # 2. Write scene.json
        scene_content = serialize_json(package_data["scene"])
        (stage_dir / "scene.json").write_text(scene_content, encoding="utf-8")

        # 3. Write objects.json
        objects_content = serialize_json(package_data["objects"])
        (stage_dir / "objects.json").write_text(objects_content, encoding="utf-8")

        # 4. Create metadata directory & write report.json
        metadata_dir = stage_dir / "metadata"
        metadata_dir.mkdir(exist_ok=True)
        report_data = validation_result.to_report_dict(package_data["timestamp"])
        report_content = serialize_json(report_data)
        (metadata_dir / "report.json").write_text(report_content, encoding="utf-8")

        # 5. Create payload directories and write mesh assets conforming to DATA_PROTOCOL.md §2
        meshes_dir = stage_dir / "meshes"
        meshes_dir.mkdir(exist_ok=True)
        for mesh_id, mesh_data in package_data.get("meshes", {}).items():
            mesh_content = serialize_json(mesh_data)
            (meshes_dir / f"{mesh_id}.json").write_text(mesh_content, encoding="utf-8")

        (stage_dir / "textures").mkdir(exist_ok=True)

        # 6. Finalize: Atomic move/replace
        if package_dir.exists():
            shutil.rmtree(package_dir)
        stage_dir.rename(package_dir)

    except Exception as exc:
        # Clean up temporary staging directory on failure
        if stage_dir.exists():
            shutil.rmtree(stage_dir, ignore_errors=True)
        raise IOError(f"Failed to write bridge package to '{package_dir}': {exc}") from exc

    return package_dir


def create_bridge_package(
    scene: Optional[bpy.types.Scene] = None,
    output_directory: Optional[Union[str, Path]] = None,
    package_name: Optional[str] = None,
    created_at: Optional[str] = None,
) -> Path:
    """
    High-level convenience API: Collects scene, builds package model, validates,
    and writes the .bubridge package.

    Args:
        scene: bpy.types.Scene (defaults to bpy.context.scene).
        output_directory: Destination folder path (defaults to current blend file folder or temp).
        package_name: Name of package (defaults to scene name).
        created_at: Optional fixed ISO 8601 timestamp for deterministic testing.

    Returns:
        Path to the generated .bubridge package directory.
    """
    if output_directory is None:
        if bpy.data.filepath:
            output_directory = Path(bpy.data.filepath).parent
        else:
            output_directory = Path.cwd()

    package_data = build_package_data(scene=scene, created_at=created_at)
    return write_bridge_package(package_data, output_directory, package_name)
