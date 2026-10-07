"""
Package Validator
-----------------
Validates Bridge Data Package structures against DATA_PROTOCOL.md specifications
prior to serialization and writing to disk.

Strictly enforces:
  - Manifest correctness (version, format, coordinate system, units)
  - Stable Bridge ID format and uniqueness
  - Referential integrity (parent_id existence and cycle detection)
  - Transform schema validity and finite numerical values
  - Collection hierarchy consistency
"""

import math
import re
from typing import Any, Dict, List, Optional, Set

from ..version import FORMAT_NAME, FORMAT_VERSION


class DiagnosticMessage:
    """Represents a structured diagnostic message conforming to DATA_PROTOCOL.md §5."""

    __slots__ = ("level", "code", "message", "target_id")

    def __init__(self, level: str, code: str, message: str, target_id: Optional[str] = None):
        self.level = level  # "INFO", "WARNING", "ERROR"
        self.code = code
        self.message = message
        self.target_id = target_id

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "level": self.level,
            "code": self.code,
            "message": self.message,
        }
        if self.target_id is not None:
            d["target_id"] = self.target_id
        return d


class ValidationResult:
    """Stores the outcome of package validation."""

    def __init__(self):
        self.messages: List[DiagnosticMessage] = []

    @property
    def is_valid(self) -> bool:
        """Returns True if no ERROR-level messages were recorded."""
        return not any(m.level == "ERROR" for m in self.messages)

    @property
    def error_count(self) -> int:
        return sum(1 for m in self.messages if m.level == "ERROR")

    @property
    def warning_count(self) -> int:
        return sum(1 for m in self.messages if m.level == "WARNING")

    @property
    def info_count(self) -> int:
        return sum(1 for m in self.messages if m.level == "INFO")

    def add_info(self, code: str, message: str, target_id: Optional[str] = None) -> None:
        self.messages.append(DiagnosticMessage("INFO", code, message, target_id))

    def add_warning(self, code: str, message: str, target_id: Optional[str] = None) -> None:
        self.messages.append(DiagnosticMessage("WARNING", code, message, target_id))

    def add_error(self, code: str, message: str, target_id: Optional[str] = None) -> None:
        self.messages.append(DiagnosticMessage("ERROR", code, message, target_id))

    def to_report_dict(self, timestamp: str) -> Dict[str, Any]:
        """Convert validation diagnostics to report.json format."""
        if not self.is_valid:
            status = "FAILED"
        elif self.warning_count > 0:
            status = "SUCCESS_WITH_WARNINGS"
        else:
            status = "SUCCESS"

        return {
            "timestamp": timestamp,
            "status": status,
            "summary": {
                "info_count": self.info_count,
                "warning_count": self.warning_count,
                "error_count": self.error_count,
            },
            "messages": [m.to_dict() for m in self.messages],
        }


ID_PATTERN = re.compile(r"^obj_[0-9a-fA-F]{8,}$")
MESH_ID_PATTERN = re.compile(r"^mesh_[0-9a-fA-F]{8,}$")
MATERIAL_ID_PATTERN = re.compile(r"^mat_[0-9a-fA-F]{8,}$")
TEXTURE_ID_PATTERN = re.compile(r"^tex_[0-9a-fA-F]{8,}$")
SKELETON_ID_PATTERN = re.compile(r"^skel_[0-9a-fA-F]{8,}$")
BONE_ID_PATTERN = re.compile(r"^bone_[0-9a-fA-F]{8,}$")
ANIMATION_ID_PATTERN = re.compile(r"^anim_[0-9a-fA-F]{8,}$")


class PackageValidator:
    """Validates complete bridge package metadata models."""

    @classmethod
    def validate_manifest(cls, manifest: Dict[str, Any], result: ValidationResult) -> None:
        """Validates manifest.json contents."""
        if manifest.get("format") != FORMAT_NAME:
            result.add_error(
                "MANIFEST_INVALID_FORMAT",
                f"Expected format '{FORMAT_NAME}', got '{manifest.get('format')}'",
            )

        if manifest.get("version") != FORMAT_VERSION:
            result.add_error(
                "MANIFEST_INVALID_VERSION",
                f"Expected format version '{FORMAT_VERSION}', got '{manifest.get('version')}'",
            )

        coord = manifest.get("coordinate_system", {})
        if coord.get("up_axis") != "Z":
            result.add_error(
                "MANIFEST_INVALID_UP_AXIS",
                f"Expected up_axis 'Z', got '{coord.get('up_axis')}'",
            )
        if coord.get("forward_axis") != "X":
            result.add_error(
                "MANIFEST_INVALID_FORWARD_AXIS",
                f"Expected forward_axis 'X', got '{coord.get('forward_axis')}'",
            )
        if coord.get("right_axis") != "Y":
            result.add_error(
                "MANIFEST_INVALID_RIGHT_AXIS",
                f"Expected right_axis 'Y', got '{coord.get('right_axis')}'",
            )
        if coord.get("handedness") != "left_handed":
            result.add_error(
                "MANIFEST_INVALID_HANDEDNESS",
                f"Expected handedness 'left_handed', got '{coord.get('handedness')}'",
            )
        if coord.get("unit") != "centimeter":
            result.add_error(
                "MANIFEST_INVALID_UNIT",
                f"Expected canonical unit 'centimeter', got '{coord.get('unit')}'",
            )

        source = manifest.get("source", {})
        if not source.get("application"):
            result.add_error("MANIFEST_MISSING_SOURCE", "Manifest missing source application name")
        if not source.get("version"):
            result.add_error("MANIFEST_MISSING_SOURCE_VERSION", "Manifest missing source application version")

    @classmethod
    def validate_scene(cls, scene: Dict[str, Any], result: ValidationResult) -> None:
        """Validates scene.json contents."""
        if not scene.get("name"):
            result.add_error("SCENE_MISSING_NAME", "Scene metadata missing 'name'")

        collections = scene.get("collections", [])
        col_ids: Set[str] = set()
        for col in collections:
            col_id = col.get("id")
            if not col_id:
                result.add_error("COLLECTION_MISSING_ID", "Collection missing 'id'")
                continue
            if col_id in col_ids:
                result.add_error("COLLECTION_DUPLICATE_ID", f"Duplicate collection ID: {col_id}", col_id)
            col_ids.add(col_id)

        # Validate collection parent references and cycles
        parent_col_map: Dict[str, Optional[str]] = {}
        for col in collections:
            col_id = col.get("id")
            if not col_id:
                continue
            parent_id = col.get("parent_id")
            parent_col_map[col_id] = parent_id
            if parent_id is not None:
                if parent_id == col_id:
                    result.add_error(
                        "COLLECTION_SELF_PARENT",
                        f"Collection '{col_id}' cannot be its own parent",
                        col_id,
                    )
                elif parent_id not in col_ids:
                    result.add_error(
                        "COLLECTION_BROKEN_PARENT",
                        f"Collection '{col_id}' references non-existent parent '{parent_id}'",
                        col_id,
                    )

        # Collection hierarchy cycle detection
        for start_id in col_ids:
            visited = set()
            curr = start_id
            while curr is not None:
                if curr in visited:
                    result.add_error(
                        "COLLECTION_HIERARCHY_CYCLE",
                        f"Hierarchy cycle detected involving collection '{curr}'",
                        curr,
                    )
                    break
                visited.add(curr)
                curr = parent_col_map.get(curr)

    @classmethod
    def validate_objects(cls, objects_data: Dict[str, Any], result: ValidationResult) -> None:
        """Validates objects.json contents, including ID uniqueness, hierarchy, and transforms."""
        objects = objects_data.get("objects", [])
        seen_ids: Set[str] = set()
        parent_map: Dict[str, Optional[str]] = {}

        for obj in objects:
            obj_id = obj.get("id")
            name = obj.get("name", "<unnamed>")

            # 1. ID format and uniqueness
            if not obj_id:
                result.add_error("OBJECT_MISSING_ID", f"Object '{name}' is missing 'id'")
                continue

            if not ID_PATTERN.match(obj_id):
                result.add_error(
                    "OBJECT_INVALID_ID_FORMAT",
                    f"Object '{name}' ID '{obj_id}' does not match pattern 'obj_<hex>'",
                    obj_id,
                )

            if obj_id in seen_ids:
                result.add_error(
                    "OBJECT_DUPLICATE_ID",
                    f"Duplicate Bridge ID detected: '{obj_id}' on object '{name}'",
                    obj_id,
                )
            seen_ids.add(obj_id)

            parent_id = obj.get("parent_id")
            parent_map[obj_id] = parent_id

            # 2. Transform validation
            transform = obj.get("transform")
            if not transform:
                result.add_error("OBJECT_MISSING_TRANSFORM", f"Object '{name}' missing 'transform'", obj_id)
            else:
                cls._validate_transform(transform, obj_id, name, result)

        # 3. Hierarchy referential integrity & cycle detection
        for obj_id, parent_id in parent_map.items():
            if parent_id is not None:
                if parent_id not in seen_ids:
                    result.add_error(
                        "OBJECT_BROKEN_PARENT_REF",
                        f"Object '{obj_id}' references non-existent parent '{parent_id}'",
                        obj_id,
                    )
                elif parent_id == obj_id:
                    result.add_error(
                        "OBJECT_SELF_PARENT",
                        f"Object '{obj_id}' cannot be its own parent",
                        obj_id,
                    )

        # Cycle detection
        for start_id in seen_ids:
            visited = set()
            curr = start_id
            while curr is not None:
                if curr in visited:
                    result.add_error(
                        "OBJECT_HIERARCHY_CYCLE",
                        f"Parent cycle detected involving object '{curr}'",
                        curr,
                    )
                    break
                visited.add(curr)
                curr = parent_map.get(curr)

    @classmethod
    def _validate_transform(
        cls,
        transform: Dict[str, Any],
        obj_id: str,
        name: str,
        result: ValidationResult,
    ) -> None:
        """Validates numerical integrity of a canonical transform block."""
        # Location
        loc = transform.get("location")
        if not isinstance(loc, list) or len(loc) != 3 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in loc):
            result.add_error(
                "TRANSFORM_INVALID_LOCATION",
                f"Object '{name}' ({obj_id}) has invalid location: {loc}",
                obj_id,
            )

        # Quaternion [x, y, z, w]
        quat = transform.get("rotation_quaternion")
        if not isinstance(quat, list) or len(quat) != 4 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in quat):
            result.add_error(
                "TRANSFORM_INVALID_QUATERNION",
                f"Object '{name}' ({obj_id}) has invalid quaternion: {quat}",
                obj_id,
            )
        else:
            # Check unit length within tolerance
            length_sq = sum(v * v for v in quat)
            if abs(length_sq - 1.0) > 0.05:
                result.add_warning(
                    "TRANSFORM_QUATERNION_NOT_NORMALIZED",
                    f"Object '{name}' ({obj_id}) quaternion is not normalized (length^2 = {length_sq:.4f})",
                    obj_id,
                )

        # Euler
        euler = transform.get("rotation_euler")
        if not isinstance(euler, list) or len(euler) != 3 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in euler):
            result.add_error(
                "TRANSFORM_INVALID_EULER",
                f"Object '{name}' ({obj_id}) has invalid Euler rotation: {euler}",
                obj_id,
            )

        # Scale
        scale = transform.get("scale")
        if not isinstance(scale, list) or len(scale) != 3 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in scale):
            result.add_error(
                "TRANSFORM_INVALID_SCALE",
                f"Object '{name}' ({obj_id}) has invalid scale: {scale}",
                obj_id,
            )
        elif any(v == 0.0 for v in scale):
            result.add_warning(
                "TRANSFORM_ZERO_SCALE",
                f"Object '{name}' ({obj_id}) has zero scale on one or more axes: {scale}",
                obj_id,
            )

    @classmethod
    def validate_mesh(cls, mesh_data: Dict[str, Any], result: ValidationResult) -> None:
        """Validates canonical mesh payload against BUBRIDGE_MESH specifications."""
        mesh_id = mesh_data.get("mesh_id", "<unnamed_mesh>")

        if mesh_data.get("format") != "BUBRIDGE_MESH":
            result.add_error(
                "MESH_INVALID_FORMAT",
                f"Mesh '{mesh_id}' format must be 'BUBRIDGE_MESH', got '{mesh_data.get('format')}'",
                mesh_id,
            )

        if not mesh_id or not MESH_ID_PATTERN.match(mesh_id):
            result.add_error(
                "MESH_INVALID_ID_FORMAT",
                f"Mesh ID '{mesh_id}' does not match pattern 'mesh_<hex>'",
                mesh_id,
            )

        vertices = mesh_data.get("vertices")
        if not isinstance(vertices, list):
            result.add_error("MESH_MISSING_VERTICES", f"Mesh '{mesh_id}' missing 'vertices' array", mesh_id)
            return

        vertex_count = len(vertices)
        for v_idx, v in enumerate(vertices):
            if not isinstance(v, list) or len(v) != 3 or not all(isinstance(c, (int, float)) and math.isfinite(c) for c in v):
                result.add_error(
                    "MESH_NON_FINITE_COORDINATE",
                    f"Mesh '{mesh_id}' vertex {v_idx} contains invalid or non-finite coordinate: {v}",
                    mesh_id,
                )
                break

        triangles = mesh_data.get("triangles")
        if not isinstance(triangles, list):
            result.add_error("MESH_MISSING_TRIANGLES", f"Mesh '{mesh_id}' missing 'triangles' array", mesh_id)
            return

        material_slots = mesh_data.get("material_slots", [])
        num_slots = len(material_slots) if isinstance(material_slots, list) else 1

        for t_idx, tri in enumerate(triangles):
            indices = tri.get("vertex_indices")
            if not isinstance(indices, list) or len(indices) != 3:
                result.add_error(
                    "MESH_INVALID_TRIANGLE_INDICES",
                    f"Mesh '{mesh_id}' triangle {t_idx} must have exactly 3 vertex indices",
                    mesh_id,
                )
                continue

            for idx in indices:
                if not isinstance(idx, int) or idx < 0 or idx >= vertex_count:
                    result.add_error(
                        "MESH_INDEX_OUT_OF_BOUNDS",
                        f"Mesh '{mesh_id}' triangle {t_idx} references out-of-bounds vertex index {idx} (vertex count: {vertex_count})",
                        mesh_id,
                    )
                    break

            # Normals
            normals = tri.get("normals")
            if isinstance(normals, list) and len(normals) == 3:
                for n_idx, n in enumerate(normals):
                    if not isinstance(n, list) or len(n) != 3 or not all(isinstance(c, (int, float)) and math.isfinite(c) for c in n):
                        result.add_error(
                            "MESH_NON_FINITE_NORMAL",
                            f"Mesh '{mesh_id}' triangle {t_idx} normal {n_idx} is non-finite: {n}",
                            mesh_id,
                        )
                        break

            # UVs
            uvs = tri.get("uvs")
            if isinstance(uvs, list) and len(uvs) == 3:
                for u_idx, uv in enumerate(uvs):
                    if not isinstance(uv, list) or len(uv) != 2 or not all(isinstance(c, (int, float)) and math.isfinite(c) for c in uv):
                        result.add_error(
                            "MESH_NON_FINITE_UV",
                            f"Mesh '{mesh_id}' triangle {t_idx} UV {u_idx} is non-finite: {uv}",
                            mesh_id,
                        )
                        break

            # Material slot index
            slot_idx = tri.get("material_slot_index", 0)
            if not isinstance(slot_idx, int) or slot_idx < 0 or (num_slots > 0 and slot_idx >= num_slots):
                result.add_error(
                    "MESH_INVALID_MATERIAL_SLOT_INDEX",
                    f"Mesh '{mesh_id}' triangle {t_idx} references invalid material slot index {slot_idx} (slot count: {num_slots})",
                    mesh_id,
                )

        # Skinning (Milestone 9)
        skinning = mesh_data.get("skinning")
        if skinning is not None:
            if not isinstance(skinning, dict):
                result.add_error("SKIN_INVALID_FORMAT", f"Mesh '{mesh_id}' skinning must be a dictionary", mesh_id)
            else:
                skel_id = skinning.get("skeleton_id")
                if not skel_id or not SKELETON_ID_PATTERN.match(skel_id):
                    result.add_error("SKIN_INVALID_SKELETON_ID", f"Mesh '{mesh_id}' has invalid skeleton ID '{skel_id}'", mesh_id)

                influences = skinning.get("influences")
                if not isinstance(influences, list) or len(influences) != vertex_count:
                    result.add_error(
                        "SKIN_INVALID_INFLUENCE_COUNT",
                        f"Mesh '{mesh_id}' influence count {len(influences) if isinstance(influences, list) else 0} does not match vertex count {vertex_count}",
                        mesh_id,
                    )
                else:
                    for v_idx, v_infs in enumerate(influences):
                        if not isinstance(v_infs, list):
                            result.add_error("SKIN_INVALID_INFLUENCES_FORMAT", f"Mesh '{mesh_id}' vertex {v_idx} influences must be a list", mesh_id)
                            break
                        seen_vertex_bones = set()
                        for inf in v_infs:
                            b_id = inf.get("bone_id")
                            if not b_id or not BONE_ID_PATTERN.match(b_id):
                                result.add_error("SKIN_INVALID_BONE_ID", f"Mesh '{mesh_id}' vertex {v_idx} has invalid bone ID '{b_id}'", mesh_id)
                                break
                            if b_id in seen_vertex_bones:
                                result.add_error("SKIN_DUPLICATE_BONE_INFLUENCE", f"Mesh '{mesh_id}' vertex {v_idx} has duplicate influence for bone '{b_id}'", mesh_id)
                                break
                            seen_vertex_bones.add(b_id)

                            w = inf.get("weight")
                            if w is None or not isinstance(w, (int, float)) or not math.isfinite(w) or w < 0.0 or w > 1.0:
                                result.add_error("SKIN_INVALID_WEIGHT", f"Mesh '{mesh_id}' vertex {v_idx} has invalid weight '{w}'", mesh_id)
                                break

    @classmethod
    def validate_material(cls, material_data: Dict[str, Any], result: ValidationResult) -> None:
        """Validates a single material payload conforming to BUBRIDGE_MATERIAL v0.1.0."""
        mat_id = material_data.get("material_id", "")
        if material_data.get("format") != "BUBRIDGE_MATERIAL":
            result.add_error(
                "MATERIAL_INVALID_FORMAT",
                f"Material '{mat_id}' format must be 'BUBRIDGE_MATERIAL', got '{material_data.get('format')}'",
                mat_id,
            )

        if not MATERIAL_ID_PATTERN.match(mat_id):
            result.add_error(
                "MATERIAL_INVALID_ID_FORMAT",
                f"Material ID '{mat_id}' must match 'mat_<hex>' pattern",
                mat_id,
            )

        if material_data.get("model") != "PBR_METALLIC_ROUGHNESS":
            result.add_error(
                "MATERIAL_INVALID_MODEL",
                f"Material '{mat_id}' model must be 'PBR_METALLIC_ROUGHNESS', got '{material_data.get('model')}'",
                mat_id,
            )

        # Base Color
        base_color = material_data.get("base_color")
        if not isinstance(base_color, list) or len(base_color) != 4:
            result.add_error(
                "MATERIAL_INVALID_BASE_COLOR",
                f"Material '{mat_id}' base_color must be a list of 4 RGBA values, got {base_color}",
                mat_id,
            )
        else:
            for idx, c in enumerate(base_color):
                if not isinstance(c, (int, float)) or not math.isfinite(c) or c < 0.0 or c > 1.0:
                    result.add_error(
                        "MATERIAL_OUT_OF_RANGE_BASE_COLOR",
                        f"Material '{mat_id}' base_color[{idx}] must be a finite number in [0.0, 1.0], got {c}",
                        mat_id,
                    )
                    break

        # Metallic
        metallic = material_data.get("metallic")
        if not isinstance(metallic, (int, float)) or not math.isfinite(metallic) or metallic < 0.0 or metallic > 1.0:
            result.add_error(
                "MATERIAL_OUT_OF_RANGE_METALLIC",
                f"Material '{mat_id}' metallic must be a finite number in [0.0, 1.0], got {metallic}",
                mat_id,
            )

        # Roughness
        roughness = material_data.get("roughness")
        if not isinstance(roughness, (int, float)) or not math.isfinite(roughness) or roughness < 0.0 or roughness > 1.0:
            result.add_error(
                "MATERIAL_OUT_OF_RANGE_ROUGHNESS",
                f"Material '{mat_id}' roughness must be a finite number in [0.0, 1.0], got {roughness}",
                mat_id,
            )

        # Specular
        specular = material_data.get("specular")
        if specular is not None and (not isinstance(specular, (int, float)) or not math.isfinite(specular) or specular < 0.0 or specular > 1.0):
            result.add_error(
                "MATERIAL_OUT_OF_RANGE_SPECULAR",
                f"Material '{mat_id}' specular must be a finite number in [0.0, 1.0], got {specular}",
                mat_id,
            )

        # Textures map validation
        textures = material_data.get("textures")
        if textures is not None:
            if not isinstance(textures, dict):
                result.add_error(
                    "MATERIAL_INVALID_TEXTURES_MAP",
                    f"Material '{mat_id}' textures field must be a dictionary",
                    mat_id,
                )
            else:
                for channel, tex_ref in textures.items():
                    if tex_ref and not TEXTURE_ID_PATTERN.match(tex_ref):
                        result.add_error(
                            "MATERIAL_INVALID_TEXTURE_ID",
                            f"Material '{mat_id}' channel '{channel}' references invalid texture ID '{tex_ref}'",
                            mat_id,
                        )

    @classmethod
    def validate_texture(cls, texture_data: Dict[str, Any], result: ValidationResult) -> None:
        """Validates canonical texture metadata conforming to DATA_PROTOCOL.md §4.6."""
        tex_id = texture_data.get("id")
        if not tex_id or not TEXTURE_ID_PATTERN.match(tex_id):
            result.add_error(
                "TEXTURE_INVALID_ID_FORMAT",
                f"Texture ID '{tex_id}' must match format 'tex_<8+ hex chars>'",
                tex_id,
            )

        rel_path = texture_data.get("relative_path", "")
        if not rel_path or not rel_path.startswith("textures/"):
            result.add_error(
                "TEXTURE_INVALID_PATH",
                f"Texture '{tex_id}' relative_path must start with 'textures/', got '{rel_path}'",
                tex_id,
            )

        cs = texture_data.get("color_space")
        if cs not in ("sRGB", "Linear"):
            result.add_error(
                "TEXTURE_INVALID_COLOR_SPACE",
                f"Texture '{tex_id}' color_space must be 'sRGB' or 'Linear', got '{cs}'",
                tex_id,
            )

        dims = texture_data.get("dimensions")
        if not isinstance(dims, (list, tuple)) or len(dims) != 2 or not all(isinstance(d, int) and d > 0 for d in dims):
            result.add_error(
                "TEXTURE_INVALID_DIMENSIONS",
                f"Texture '{tex_id}' dimensions must be a 2-tuple of positive integers, got '{dims}'",
                tex_id,
            )

        channels = texture_data.get("channels")
        if not isinstance(channels, int) or channels < 1 or channels > 4:
            result.add_error(
                "TEXTURE_INVALID_CHANNELS",
                f"Texture '{tex_id}' channels must be an integer between 1 and 4, got '{channels}'",
                tex_id,
            )

    @classmethod
    def validate_animations(cls, animations_data: Dict[str, Any], result: ValidationResult) -> None:
        """Validates animations.json conforming to BUBRIDGE_ANIMATIONS v0.1.0."""
        if animations_data.get("format") != "BUBRIDGE_ANIMATIONS":
            result.add_error(
                "ANIMATIONS_INVALID_FORMAT",
                f"Expected format 'BUBRIDGE_ANIMATIONS', got '{animations_data.get('format')}'",
            )
        if animations_data.get("version") != "0.1.0":
            result.add_error(
                "ANIMATIONS_INVALID_VERSION",
                f"Expected version '0.1.0', got '{animations_data.get('version')}'",
            )

        skeletons = animations_data.get("skeletons", [])
        seen_skel_ids: Set[str] = set()
        skel_bone_ids: Dict[str, Set[str]] = {}

        for skel in skeletons:
            skel_id = skel.get("id", "")
            if not skel_id or not SKELETON_ID_PATTERN.match(skel_id):
                result.add_error("SKELETON_INVALID_ID_FORMAT", f"Invalid skeleton ID '{skel_id}'", skel_id)

            if skel_id in seen_skel_ids:
                result.add_error("SKELETON_DUPLICATE_ID", f"Duplicate skeleton ID '{skel_id}'", skel_id)
            seen_skel_ids.add(skel_id)

            bones = skel.get("bones", [])
            seen_bone_ids: Set[str] = set()
            seen_bone_names: Set[str] = set()
            bone_parent_map: Dict[str, Optional[str]] = {}

            for bone in bones:
                bone_id = bone.get("id", "")
                bone_name = bone.get("name", "")

                if not bone_id or not BONE_ID_PATTERN.match(bone_id):
                    result.add_error("BONE_INVALID_ID_FORMAT", f"Skeleton '{skel_id}' bone has invalid ID '{bone_id}'", bone_id)

                if bone_id in seen_bone_ids:
                    result.add_error("BONE_DUPLICATE_ID", f"Duplicate bone ID '{bone_id}' in skeleton '{skel_id}'", bone_id)
                seen_bone_ids.add(bone_id)

                if bone_name in seen_bone_names:
                    result.add_error("BONE_DUPLICATE_NAME", f"Duplicate bone name '{bone_name}' in skeleton '{skel_id}'", bone_id)
                seen_bone_names.add(bone_name)

                parent_id = bone.get("parent_id")
                bone_parent_map[bone_id] = parent_id

                xform = bone.get("transform", {})
                cls._validate_transform(xform, bone_id, bone_name, result)

            skel_bone_ids[skel_id] = seen_bone_ids

            # Bone parent integrity
            for b_id, p_id in bone_parent_map.items():
                if p_id:
                    if p_id == b_id:
                        result.add_error("BONE_SELF_PARENT", f"Bone '{b_id}' references itself as parent", b_id)
                    elif p_id not in seen_bone_ids:
                        result.add_error("BONE_BROKEN_PARENT_REF", f"Bone '{b_id}' references non-existent parent '{p_id}'", b_id)

            # Bone cycle detection
            for start_id in seen_bone_ids:
                visited = set()
                curr = start_id
                while curr:
                    if curr in visited:
                        result.add_error("BONE_HIERARCHY_CYCLE", f"Bone hierarchy cycle detected involving '{curr}' in skeleton '{skel_id}'", curr)
                        break
                    visited.add(curr)
                    curr = bone_parent_map.get(curr)

        # Animations validation
        animations = animations_data.get("animations", [])
        seen_anim_ids: Set[str] = set()

        for anim in animations:
            anim_id = anim.get("id", "")
            if not anim_id or not ANIMATION_ID_PATTERN.match(anim_id):
                result.add_error("ANIMATION_INVALID_ID_FORMAT", f"Invalid animation ID '{anim_id}'", anim_id)

            if anim_id in seen_anim_ids:
                result.add_error("ANIMATION_DUPLICATE_ID", f"Duplicate animation ID '{anim_id}'", anim_id)
            seen_anim_ids.add(anim_id)

            skel_ref = anim.get("skeleton_id", "")
            if skel_ref not in seen_skel_ids:
                result.add_error("ANIMATION_BROKEN_SKELETON_REF", f"Animation '{anim_id}' references non-existent skeleton '{skel_ref}'", anim_id)

            fr = anim.get("frame_range", [])
            if not isinstance(fr, (list, tuple)) or len(fr) != 2 or fr[0] > fr[1]:
                result.add_error("ANIMATION_INVALID_FRAME_RANGE", f"Animation '{anim_id}' has invalid frame range '{fr}'", anim_id)

            fps = anim.get("frame_rate", 0.0)
            if not isinstance(fps, (int, float)) or not math.isfinite(fps) or fps <= 0.0:
                result.add_error("ANIMATION_INVALID_FRAME_RATE", f"Animation '{anim_id}' has invalid frame rate '{fps}'", anim_id)

            dur = anim.get("duration", 0.0)
            if not isinstance(dur, (int, float)) or not math.isfinite(dur) or dur < 0.0:
                result.add_error("ANIMATION_INVALID_DURATION", f"Animation '{anim_id}' has invalid duration '{dur}'", anim_id)

            valid_bones_for_skel = skel_bone_ids.get(skel_ref, set())
            tracks = anim.get("tracks", [])
            for track in tracks:
                b_id = track.get("bone_id", "")
                if b_id and b_id not in valid_bones_for_skel:
                    result.add_error("ANIMATION_BROKEN_BONE_REF", f"Animation '{anim_id}' track references non-existent bone '{b_id}'", anim_id)

                channels = track.get("channels", {})
                for ch_name in ("location", "rotation", "scale"):
                    keys = channels.get(ch_name, [])
                    last_time = -1.0
                    expected_dim = 4 if ch_name == "rotation" else 3
                    for k in keys:
                        t = k.get("time")
                        if t is None or not isinstance(t, (int, float)) or not math.isfinite(t) or t < last_time:
                            result.add_error("ANIMATION_UNSORTED_KEYFRAMES", f"Animation '{anim_id}' bone '{b_id}' channel '{ch_name}' keyframes not strictly sorted", anim_id)
                            break
                        last_time = t

                        val = k.get("value")
                        if not isinstance(val, list) or len(val) != expected_dim or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in val):
                            result.add_error("ANIMATION_NON_FINITE_VALUE", f"Animation '{anim_id}' bone '{b_id}' channel '{ch_name}' has non-finite values", anim_id)
                            break

    @classmethod
    def validate_package(
        cls,
        manifest: Dict[str, Any],
        scene: Dict[str, Any],
        objects: Dict[str, Any],
        meshes: Optional[Dict[str, Dict[str, Any]]] = None,
        materials: Optional[Dict[str, Dict[str, Any]]] = None,
        textures: Optional[Dict[str, Dict[str, Any]]] = None,
        animations: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        """Runs full validation suite on package components including meshes, materials, textures, and animations."""
        result = ValidationResult()
        cls.validate_manifest(manifest, result)
        cls.validate_scene(scene, result)
        cls.validate_objects(objects, result)

        # Check object collection references
        valid_col_ids = {c.get("id") for c in scene.get("collections", []) if c.get("id")}
        for obj in objects.get("objects", []):
            col_ref = obj.get("collection_id")
            if col_ref and col_ref not in valid_col_ids:
                result.add_error(
                    "OBJECT_BROKEN_COLLECTION_REF",
                    f"Object '{obj.get('name')}' references non-existent collection '{col_ref}'",
                    obj.get("id"),
                )

        if meshes:
            for mesh_id, mesh_data in meshes.items():
                cls.validate_mesh(mesh_data, result)

            # Check that referenced meshes in objects actually exist in meshes
            mesh_set = set(meshes.keys())
            for obj in objects.get("objects", []):
                mesh_ref = obj.get("mesh_reference")
                if mesh_ref:
                    ref_id = mesh_ref.get("mesh_id")
                    if ref_id and ref_id not in mesh_set:
                        result.add_error(
                            "OBJECT_BROKEN_MESH_REF",
                            f"Object '{obj.get('name')}' references non-existent mesh '{ref_id}'",
                            obj.get("id"),
                        )

        if materials is not None:
            for mat_id, mat_data in materials.items():
                cls.validate_material(mat_data, result)

            # Check that referenced materials in mesh / object slots exist in materials
            mat_set = set(materials.keys())
            for obj in objects.get("objects", []):
                for slot in obj.get("material_slots", []):
                    slot_mat_id = slot.get("material_id")
                    if slot_mat_id and slot_mat_id not in mat_set:
                        result.add_error(
                            "OBJECT_BROKEN_MATERIAL_REF",
                            f"Object '{obj.get('name')}' slot '{slot.get('slot_name')}' references non-existent material '{slot_mat_id}'",
                            obj.get("id"),
                        )

            if meshes:
                for mesh_id, mesh_data in meshes.items():
                    for slot in mesh_data.get("material_slots", []):
                        slot_mat_id = slot.get("material_id")
                        if slot_mat_id and slot_mat_id not in mat_set:
                            result.add_error(
                                "MESH_BROKEN_MATERIAL_REF",
                                f"Mesh '{mesh_id}' slot '{slot.get('slot_name')}' references non-existent material '{slot_mat_id}'",
                                mesh_id,
                            )

        if textures is not None:
            for tex_id, tex_data in textures.items():
                cls.validate_texture(tex_data, result)

            tex_set = set(textures.keys())
            if materials is not None:
                for mat_id, mat_data in materials.items():
                    for channel, tex_ref in mat_data.get("textures", {}).items():
                        if tex_ref and tex_ref not in tex_set:
                            result.add_error(
                                "MATERIAL_BROKEN_TEXTURE_REF",
                                f"Material '{mat_id}' channel '{channel}' references non-existent texture '{tex_ref}'",
                                mat_id,
                            )

        if animations is not None:
            cls.validate_animations(animations, result)

            valid_skel_ids = {s["id"]: {b["id"] for b in s.get("bones", [])} for s in animations.get("skeletons", []) if "id" in s}

            # Check mesh skinning references
            if meshes:
                for mesh_id, mesh_data in meshes.items():
                    skinning = mesh_data.get("skinning")
                    if skinning:
                        skel_id = skinning.get("skeleton_id")
                        if not skel_id or skel_id not in valid_skel_ids:
                            result.add_error("SKIN_BROKEN_SKELETON_REF", f"Mesh '{mesh_id}' references non-existent skeleton '{skel_id}'", mesh_id)
                        else:
                            skel_bones = valid_skel_ids[skel_id]
                            for v_idx, infs in enumerate(skinning.get("influences", [])):
                                for inf in infs:
                                    b_id = inf.get("bone_id")
                                    if b_id and b_id not in skel_bones:
                                        result.add_error("SKIN_BROKEN_BONE_REF", f"Mesh '{mesh_id}' vertex {v_idx} references non-existent bone '{b_id}'", mesh_id)
                                        break

            # Check object skeleton references
            valid_skel_set = set(valid_skel_ids.keys())
            for obj in objects.get("objects", []):
                skel_ref = obj.get("skeleton_id")
                if skel_ref and skel_ref not in valid_skel_set:
                    result.add_error("OBJECT_BROKEN_SKELETON_REF", f"Object '{obj.get('name')}' references non-existent skeleton '{skel_ref}'", obj.get("id"))

        return result


