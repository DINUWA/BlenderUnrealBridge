"""
test_unreal_package_reader.py
==============================
Engine-independent test suite for the Milestone 4 Unreal Bridge Package Reader.
Tests:
  1. All 13 test fixtures against the reader's validation rules
  2. Malformed input detection and structured error diagnostics
  3. Transform conversion mathematics (location, rotation, scale, negative scale)
  4. Parent-relative transform composition (Unreal world transform computation)
  5. Full integration test consuming Milestone 3 DemoScene.bubridge package
"""

import json
import math
from pathlib import Path
import unittest

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "test_assets" / "fixtures"
DEMO_PACKAGE = Path(__file__).resolve().parent.parent.parent / "examples" / "basic_scene" / "DemoScene.bubridge"


class UnrealVector:
    """Mimics Unreal FVector."""
    __slots__ = ("x", "y", "z")

    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    def to_tuple(self):
        return (self.x, self.y, self.z)

    def __add__(self, other):
        return UnrealVector(self.x + other.x, self.y + other.y, self.z + other.z)

    def __eq__(self, other):
        return (math.isclose(self.x, other.x, abs_tol=1e-4) and
                math.isclose(self.y, other.y, abs_tol=1e-4) and
                math.isclose(self.z, other.z, abs_tol=1e-4))

    def __repr__(self):
        return f"FVector(X={self.x:.2f}, Y={self.y:.2f}, Z={self.z:.2f})"


class UnrealQuat:
    """Mimics Unreal FQuat."""
    __slots__ = ("x", "y", "z", "w")

    def __init__(self, x=0.0, y=0.0, z=0.0, w=1.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
        self.w = float(w)

    def size_squared(self):
        return self.x * self.x + self.y * self.y + self.z * self.z + self.w * self.w

    def rotate_vector(self, v: UnrealVector) -> UnrealVector:
        # Standard quaternion vector rotation: q * v * q^-1
        # For unit quaternion: v + 2*r x (r x v + w*v)
        rx, ry, rz = self.x, self.y, self.z
        rw = self.w
        # t = 2 * cross(r, v)
        tx = 2.0 * (ry * v.z - rz * v.y)
        ty = 2.0 * (rz * v.x - rx * v.z)
        tz = 2.0 * (rx * v.y - ry * v.x)
        # v' = v + w * t + cross(r, t)
        vx = v.x + rw * tx + (ry * tz - rz * ty)
        vy = v.y + rw * ty + (rz * tx - rx * tz)
        vz = v.z + rw * tz + (rx * ty - ry * tx)
        return UnrealVector(vx, vy, vz)

    def __mul__(self, other):
        # Quaternion multiplication: self * other
        return UnrealQuat(
            self.w * other.x + self.x * other.w + self.y * other.z - self.z * other.y,
            self.w * other.y - self.x * other.z + self.y * other.w + self.z * other.x,
            self.w * other.z + self.x * other.y - self.y * other.x + self.z * other.w,
            self.w * other.w - self.x * other.x - self.y * other.y - self.z * other.z,
        )


class UnrealTransform:
    """Mimics Unreal FTransform."""
    def __init__(self, rotation=None, translation=None, scale=None):
        self.rotation = rotation or UnrealQuat(0.0, 0.0, 0.0, 1.0)
        self.translation = translation or UnrealVector(0.0, 0.0, 0.0)
        self.scale = scale or UnrealVector(1.0, 1.0, 1.0)

    def transform_position(self, v: UnrealVector) -> UnrealVector:
        scaled = UnrealVector(v.x * self.scale.x, v.y * self.scale.y, v.z * self.scale.z)
        rotated = self.rotation.rotate_vector(scaled)
        return rotated + self.translation

    def __mul__(self, other):
        # In Unreal Engine: Child * Parent
        # Translation = Parent.TransformPosition(Child.Translation)
        # Rotation = Child.Rotation * Parent.Rotation
        # Scale = Child.Scale * Parent.Scale
        new_loc = other.transform_position(self.translation)
        new_rot = self.rotation * other.rotation
        new_scale = UnrealVector(self.scale.x * other.scale.x,
                                 self.scale.y * other.scale.y,
                                 self.scale.z * other.scale.z)
        return UnrealTransform(new_rot, new_loc, new_scale)


class BridgeTransformConverter:
    """Authoritative transform conversion matching BridgeTransformConverter.cpp."""
    @staticmethod
    def to_unreal_location(canonical_loc):
        return UnrealVector(canonical_loc[0], canonical_loc[1], canonical_loc[2])

    @staticmethod
    def to_unreal_rotation(canonical_quat):
        # [x, y, z, w]
        return UnrealQuat(canonical_quat[0], canonical_quat[1], canonical_quat[2], canonical_quat[3])

    @staticmethod
    def to_unreal_scale(canonical_scale):
        return UnrealVector(canonical_scale[0], canonical_scale[1], canonical_scale[2])

    @staticmethod
    def to_unreal_local_transform(transform_dict):
        loc = BridgeTransformConverter.to_unreal_location(transform_dict["location"])
        rot = BridgeTransformConverter.to_unreal_rotation(transform_dict["rotation_quaternion"])
        sc = BridgeTransformConverter.to_unreal_scale(transform_dict["scale"])
        return UnrealTransform(rot, loc, sc)


class BridgePackageValidator:
    """Validation logic matching BridgePackageValidator.cpp."""
    SUPPORTED_FORMAT = "BUBRIDGE"
    SUPPORTED_MAJOR = 0
    SUPPORTED_MINOR = 1

    @classmethod
    def validate_package(cls, manifest, scene, objects, meshes=None, materials=None, textures=None, pkg_dir=None):
        errors = []
        warnings = []

        # Manifest
        if manifest.get("format") != cls.SUPPORTED_FORMAT:
            errors.append(("MANIFEST_INVALID_FORMAT", f"Expected format {cls.SUPPORTED_FORMAT}"))

        version_parts = str(manifest.get("version", "")).split(".")
        if len(version_parts) < 2:
            errors.append(("MANIFEST_MALFORMED_VERSION", "Malformed version string"))
        else:
            try:
                major = int(version_parts[0])
                minor = int(version_parts[1])
                if major != cls.SUPPORTED_MAJOR:
                    errors.append(("MANIFEST_UNSUPPORTED_MAJOR_VERSION", f"Unsupported major version {major}"))
                elif minor > cls.SUPPORTED_MINOR:
                    warnings.append(("MANIFEST_NEWER_MINOR_VERSION", "Newer minor version"))
            except ValueError:
                errors.append(("MANIFEST_MALFORMED_VERSION", "Invalid version numbers"))

        coord = manifest.get("coordinate_system", {})
        if coord.get("up_axis") != "Z":
            errors.append(("MANIFEST_INVALID_UP_AXIS", "Expected up_axis Z"))
        if coord.get("forward_axis") != "X":
            errors.append(("MANIFEST_INVALID_FORWARD_AXIS", "Expected forward_axis X"))
        if coord.get("right_axis") != "Y":
            errors.append(("MANIFEST_INVALID_RIGHT_AXIS", "Expected right_axis Y"))
        if coord.get("handedness") != "left_handed":
            errors.append(("MANIFEST_INVALID_HANDEDNESS", "Expected handedness left_handed"))
        if coord.get("unit") != "centimeter":
            errors.append(("MANIFEST_INVALID_UNIT", "Expected unit centimeter"))

        # Objects
        seen_ids = set()
        parent_map = {}
        for obj in objects:
            obj_id = obj.get("id", "")
            if not obj_id.startswith("obj_") or len(obj_id) < 12:
                errors.append(("OBJECT_INVALID_ID_FORMAT", f"Invalid ID format {obj_id}"))

            if obj_id in seen_ids:
                errors.append(("OBJECT_DUPLICATE_ID", f"Duplicate ID {obj_id}"))
            seen_ids.add(obj_id)

            parent_id = obj.get("parent_id")
            parent_map[obj_id] = parent_id

            xform = obj.get("transform", {})
            loc = xform.get("location")
            if not isinstance(loc, list) or len(loc) != 3 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in loc):
                errors.append(("TRANSFORM_MALFORMED_LOCATION", "Invalid location"))

            quat = xform.get("rotation_quaternion")
            if not isinstance(quat, list) or len(quat) != 4 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in quat):
                errors.append(("TRANSFORM_MALFORMED_QUATERNION", "Invalid quaternion"))

            sc = xform.get("scale")
            if not isinstance(sc, list) or len(sc) != 3 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in sc):
                errors.append(("TRANSFORM_MALFORMED_SCALE", "Invalid scale"))

        for child_id, p_id in parent_map.items():
            if p_id:
                if p_id == child_id:
                    errors.append(("OBJECT_SELF_PARENT", "Self parent"))
                elif p_id not in seen_ids:
                    errors.append(("OBJECT_BROKEN_PARENT_REF", f"Parent {p_id} not found"))

        # Cycle detection
        for start_id in seen_ids:
            visited = set()
            curr = start_id
            while curr:
                if curr in visited:
                    errors.append(("OBJECT_HIERARCHY_CYCLE", f"Cycle involving {curr}"))
                    break
                visited.add(curr)
                curr = parent_map.get(curr)

        # Scene Collections (Milestone 8)
        col_seen_ids = set()
        col_parent_map = {}
        for col in scene.get("collections", []):
            col_id = col.get("id", "")
            if not col_id.startswith("col_") or len(col_id) < 12:
                errors.append(("COLLECTION_INVALID_ID_FORMAT", f"Invalid collection ID {col_id}"))

            if col_id in col_seen_ids:
                errors.append(("COLLECTION_DUPLICATE_ID", f"Duplicate collection ID {col_id}"))
            col_seen_ids.add(col_id)

            col_parent_id = col.get("parent_id")
            col_parent_map[col_id] = col_parent_id

        for col_id, p_id in col_parent_map.items():
            if p_id:
                if p_id == col_id:
                    errors.append(("COLLECTION_SELF_PARENT", f"Collection {col_id} references itself as parent"))
                elif p_id not in col_seen_ids:
                    errors.append(("COLLECTION_BROKEN_PARENT", f"Collection parent {p_id} not found"))

        # Collection Cycle detection
        for start_id in col_seen_ids:
            visited = set()
            curr = start_id
            while curr:
                if curr in visited:
                    errors.append(("COLLECTION_HIERARCHY_CYCLE", f"Collection cycle involving {curr}"))
                    break
                visited.add(curr)
                curr = col_parent_map.get(curr)

        # Cross-validation: Object collection references
        for obj in objects:
            c_id = obj.get("collection_id")
            if c_id and c_id not in col_seen_ids:
                errors.append(("OBJECT_BROKEN_COLLECTION_REF", f"Object references missing collection {c_id}"))
            for cid in obj.get("collection_ids", []):
                if cid and cid not in col_seen_ids:
                    errors.append(("OBJECT_BROKEN_COLLECTION_REF", f"Object references missing collection {cid}"))

        # Meshes validation (Milestone 5)
        if meshes is not None:
            for mesh_id, mesh in meshes.items():
                if mesh.get("format") != "BUBRIDGE_MESH":
                    errors.append(("MESH_INVALID_FORMAT", f"Expected BUBRIDGE_MESH, got {mesh.get('format')}"))
                if not mesh_id.startswith("mesh_") or len(mesh_id) < 13:
                    errors.append(("MESH_INVALID_ID_FORMAT", f"Invalid mesh ID {mesh_id}"))

                verts = mesh.get("vertices", [])
                for idx, v in enumerate(verts):
                    if not isinstance(v, list) or len(v) != 3 or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in v):
                        errors.append(("MESH_NON_FINITE_COORDINATE", f"Non-finite coordinate in vertex {idx}"))
                        break

                vert_count = len(verts)
                slot_count = len(mesh.get("material_slots", []))
                for t_idx, tri in enumerate(mesh.get("triangles", [])):
                    v_indices = tri.get("vertex_indices", [])
                    has_bad_idx = False
                    for c_idx in v_indices:
                        if c_idx < 0 or c_idx >= vert_count:
                            errors.append(("MESH_INDEX_OUT_OF_BOUNDS", f"Vertex index {c_idx} out of bounds (count {vert_count})"))
                            has_bad_idx = True
                            break
                    if has_bad_idx:
                        break

                    for n in tri.get("normals", []):
                        if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in n):
                            errors.append(("MESH_NON_FINITE_NORMAL", "Non-finite normal"))
                            break

                    for uv in tri.get("uvs", []):
                        if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in uv):
                            errors.append(("MESH_NON_FINITE_UV", "Non-finite UV"))
                            break

                    slot_idx = tri.get("material_slot_index", 0)
                    if slot_count > 0 and (slot_idx < 0 or slot_idx >= slot_count):
                        errors.append(("MESH_INVALID_MATERIAL_SLOT_INDEX", f"Invalid slot index {slot_idx}"))
                        break

            # Object mesh references
            for obj in objects:
                if obj.get("type") == "STATIC_MESH" and obj.get("mesh_reference"):
                    ref_id = obj["mesh_reference"].get("mesh_id")
                    if ref_id and ref_id not in meshes:
                        errors.append(("OBJECT_BROKEN_MESH_REF", f"Object references missing mesh {ref_id}"))

        # Materials validation (Milestone 6)
        if materials is not None:
            for mat_id, mat in materials.items():
                if mat.get("format") != "BUBRIDGE_MATERIAL":
                    errors.append(("MATERIAL_INVALID_FORMAT", f"Expected BUBRIDGE_MATERIAL, got {mat.get('format')}"))
                if not mat_id.startswith("mat_") or len(mat_id) < 12:
                    errors.append(("MATERIAL_INVALID_ID_FORMAT", f"Invalid material ID {mat_id}"))
                if mat.get("model") != "PBR_METALLIC_ROUGHNESS":
                    errors.append(("MATERIAL_INVALID_MODEL", f"Expected PBR_METALLIC_ROUGHNESS, got {mat.get('model')}"))

                props = mat.get("properties", {})
                bc = props.get("base_color", [])
                if not isinstance(bc, list) or len(bc) != 4 or not all(isinstance(c, (int, float)) and math.isfinite(c) and 0.0 <= c <= 1.0 for c in bc):
                    errors.append(("MATERIAL_OUT_OF_RANGE_BASE_COLOR", f"Material {mat_id} base_color out of range"))

                for prop_name, err_code in [
                    ("metallic", "MATERIAL_OUT_OF_RANGE_METALLIC"),
                    ("roughness", "MATERIAL_OUT_OF_RANGE_ROUGHNESS"),
                    ("specular", "MATERIAL_OUT_OF_RANGE_SPECULAR"),
                ]:
                    val = props.get(prop_name)
                    if val is None or not isinstance(val, (int, float)) or not math.isfinite(val) or val < 0.0 or val > 1.0:
                        errors.append((err_code, f"Material {mat_id} {prop_name} out of range"))

            # Check object material slot references
            for obj in objects:
                for slot in obj.get("material_slots", []):
                    slot_mat_id = slot.get("material_id")
                    if slot_mat_id and slot_mat_id not in materials:
                        errors.append(("OBJECT_BROKEN_MATERIAL_REF", f"Object references missing material {slot_mat_id}"))

            # Check mesh material slot references
            if meshes is not None:
                for m_id, mesh in meshes.items():
                    for slot in mesh.get("material_slots", []):
                        slot_mat_id = slot.get("material_id")
                        if slot_mat_id and slot_mat_id not in materials:
                            errors.append(("MESH_BROKEN_MATERIAL_REF", f"Mesh references missing material {slot_mat_id}"))

        # Textures validation (Milestone 7)
        if textures is not None:
            for tex in textures:
                tex_id = tex.get("id")
                if not tex_id or not tex_id.startswith("tex_") or len(tex_id) < 12:
                    errors.append(("TEXTURE_INVALID_ID_FORMAT", f"Invalid texture ID format '{tex_id}'"))

                rel_path = tex.get("relative_path", "")
                if not rel_path.startswith("textures/"):
                    errors.append(("TEXTURE_INVALID_PATH", f"Texture '{tex_id}' relative path must start with 'textures/', got '{rel_path}'"))

                cs = tex.get("color_space")
                if cs not in ("sRGB", "Linear"):
                    errors.append(("TEXTURE_INVALID_COLOR_SPACE", f"Texture '{tex_id}' invalid color space '{cs}'"))

                dims = tex.get("dimensions", [])
                if not isinstance(dims, (list, tuple)) or len(dims) != 2 or dims[0] <= 0 or dims[1] <= 0:
                    errors.append(("TEXTURE_INVALID_DIMENSIONS", f"Texture '{tex_id}' invalid dimensions '{dims}'"))

                channels = tex.get("channels")
                if not isinstance(channels, int) or channels < 1 or channels > 4:
                    errors.append(("TEXTURE_INVALID_CHANNELS", f"Texture '{tex_id}' invalid channels '{channels}'"))

                if pkg_dir and rel_path:
                    full_path = Path(pkg_dir) / rel_path
                    if not full_path.is_file():
                        errors.append(("TEX_FILE_NOT_FOUND", f"Texture file not found on disk: '{full_path}'"))

        # Materials -> Texture references validation (Milestone 7)
        if materials is not None:
            tex_set = {t["id"] for t in (textures or []) if isinstance(t, dict) and "id" in t}
            for mat_id, mat in materials.items():
                for channel, tex_id in mat.get("textures", {}).items():
                    if tex_id and tex_id not in tex_set:
                        errors.append(("MATERIAL_BROKEN_TEXTURE_REF", f"Material '{mat_id}' channel '{channel}' references missing texture '{tex_id}'"))

        return errors, warnings


class FixtureData:
    def __init__(self, manifest, scene, objects, meshes, materials, textures=None, pkg_dir=None):
        self.manifest = manifest
        self.scene = scene
        self.objects = objects
        self.meshes = meshes
        self.materials = materials
        self.textures = textures or []
        self.pkg_dir = pkg_dir

    def __iter__(self):
        return iter((self.manifest, self.scene, self.objects, self.meshes, self.materials))


class TestUnrealPackageReaderFixtures(unittest.TestCase):
    """Test validation of all 28 fixtures against the reader's validation rules."""

    def _load_fixture(self, name):
        pkg_dir = FIXTURES_DIR / f"{name}.bubridge"
        with open(pkg_dir / "manifest.json", "r", encoding="utf-8") as f:
            manifest = json.load(f)
        with open(pkg_dir / "scene.json", "r", encoding="utf-8") as f:
            scene = json.load(f)
        with open(pkg_dir / "objects.json", "r", encoding="utf-8") as f:
            objects_data = json.load(f)
        meshes = {}
        mesh_dir = pkg_dir / "meshes"
        if mesh_dir.exists():
            for m_file in mesh_dir.glob("*.json"):
                with open(m_file, "r", encoding="utf-8") as f:
                    m_data = json.load(f)
                    meshes[m_data.get("mesh_id", m_file.stem)] = m_data
        materials = {}
        mat_dir = pkg_dir / "materials"
        if mat_dir.exists():
            for mat_file in mat_dir.glob("*.json"):
                with open(mat_file, "r", encoding="utf-8") as f:
                    mat_data = json.load(f)
                    materials[mat_data.get("material_id", mat_file.stem)] = mat_data
        textures = []
        tex_file = pkg_dir / "textures.json"
        if tex_file.exists():
            with open(tex_file, "r", encoding="utf-8") as f:
                tex_data = json.load(f)
                textures = tex_data.get("textures", [])
        return FixtureData(manifest, scene, objects_data["objects"], meshes, materials, textures, pkg_dir)

    def test_fixture_01_identity_valid(self):
        m, s, o, meshes, mats = self._load_fixture("01_identity_scene")
        errors, _ = BridgePackageValidator.validate_package(m, s, o, meshes, mats)
        self.assertEqual(len(errors), 0)

    def test_fixture_02_translated_valid(self):
        m, s, o, meshes, mats = self._load_fixture("02_single_translated")
        errors, _ = BridgePackageValidator.validate_package(m, s, o, meshes, mats)
        self.assertEqual(len(errors), 0)
        xform = BridgeTransformConverter.to_unreal_local_transform(o[0]["transform"])
        self.assertEqual(xform.translation, UnrealVector(250.0, -100.0, 50.0))

    def test_fixture_03_rotated_valid(self):
        m, s, o, meshes, mats = self._load_fixture("03_rotated_object")
        errors, _ = BridgePackageValidator.validate_package(m, s, o, meshes, mats)
        self.assertEqual(len(errors), 0)
        quat = BridgeTransformConverter.to_unreal_rotation(o[0]["transform"]["rotation_quaternion"])
        self.assertAlmostEqual(quat.size_squared(), 1.0, delta=1e-3)

    def test_fixture_04_scaled_valid(self):
        m, s, o, meshes, mats = self._load_fixture("04_scaled_object")
        errors, _ = BridgePackageValidator.validate_package(m, s, o, meshes, mats)
        self.assertEqual(len(errors), 0)
        xform = BridgeTransformConverter.to_unreal_local_transform(o[0]["transform"])
        self.assertEqual(xform.scale, UnrealVector(2.0, 0.5, 3.0))

    def test_fixture_05_negative_scale_valid(self):
        m, s, o, meshes, mats = self._load_fixture("05_negative_scale")
        errors, _ = BridgePackageValidator.validate_package(m, s, o, meshes, mats)
        self.assertEqual(len(errors), 0)
        xform = BridgeTransformConverter.to_unreal_local_transform(o[0]["transform"])
        self.assertEqual(xform.scale, UnrealVector(-1.0, 1.0, 1.0))
        self.assertTrue(o[0]["transform"]["has_negative_scale"])

    def test_fixture_06_parent_child_valid(self):
        m, s, o, meshes, mats = self._load_fixture("06_parent_child")
        errors, _ = BridgePackageValidator.validate_package(m, s, o, meshes, mats)
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(o), 2)
        parent_xform = BridgeTransformConverter.to_unreal_local_transform(o[0]["transform"])
        child_xform = BridgeTransformConverter.to_unreal_local_transform(o[1]["transform"])
        # World transform = child * parent
        child_world = child_xform * parent_xform
        self.assertEqual(child_world.translation, UnrealVector(100.0, 50.0, 0.0))

    def test_fixture_07_deep_hierarchy_valid(self):
        m, s, o, meshes, mats = self._load_fixture("07_deep_hierarchy")
        errors, _ = BridgePackageValidator.validate_package(m, s, o, meshes, mats)
        self.assertEqual(len(errors), 0)
        gp_xform = BridgeTransformConverter.to_unreal_local_transform(o[0]["transform"])
        p_xform = BridgeTransformConverter.to_unreal_local_transform(o[1]["transform"])
        c_xform = BridgeTransformConverter.to_unreal_local_transform(o[2]["transform"])
        # Child world = c * p * gp
        child_world = c_xform * p_xform * gp_xform
        self.assertEqual(child_world.translation, UnrealVector(100.0, 50.0, 100.0))

    def test_fixture_08_invalid_manifest_detected(self):
        m, s, o, meshes, mats = self._load_fixture("08_invalid_manifest")
        errors, _ = BridgePackageValidator.validate_package(m, s, o, meshes, mats)
        self.assertTrue(any(code == "MANIFEST_INVALID_FORMAT" for code, _ in errors))

    def test_fixture_09_duplicate_id_detected(self):
        m, s, o, meshes, mats = self._load_fixture("09_duplicate_id")
        errors, _ = BridgePackageValidator.validate_package(m, s, o, meshes, mats)
        self.assertTrue(any(code == "OBJECT_DUPLICATE_ID" for code, _ in errors))

    def test_fixture_10_broken_parent_detected(self):
        m, s, o, meshes, mats = self._load_fixture("10_broken_parent")
        errors, _ = BridgePackageValidator.validate_package(m, s, o, meshes, mats)
        self.assertTrue(any(code == "OBJECT_BROKEN_PARENT_REF" for code, _ in errors))

    def test_fixture_11_hierarchy_cycle_detected(self):
        m, s, o, meshes, mats = self._load_fixture("11_hierarchy_cycle")
        errors, _ = BridgePackageValidator.validate_package(m, s, o, meshes, mats)
        self.assertTrue(any(code == "OBJECT_HIERARCHY_CYCLE" for code, _ in errors))

    def test_fixture_12_invalid_transform_detected(self):
        m, s, o, meshes, mats = self._load_fixture("12_invalid_transform")
        errors, _ = BridgePackageValidator.validate_package(m, s, o, meshes, mats)
        self.assertTrue(any("TRANSFORM" in code for code, _ in errors))

    def test_fixture_13_unsupported_version_detected(self):
        m, s, o, meshes, mats = self._load_fixture("13_unsupported_version")
        errors, _ = BridgePackageValidator.validate_package(m, s, o, meshes, mats)
        self.assertTrue(any(code == "MANIFEST_UNSUPPORTED_MAJOR_VERSION" for code, _ in errors))

    def test_fixture_14_mesh_payload_valid(self):
        m, s, o, meshes, mats = self._load_fixture("14_mesh_payload")
        errors, _ = BridgePackageValidator.validate_package(m, s, o, meshes, mats)
        self.assertEqual(len(errors), 0, f"Unexpected errors: {errors}")
        self.assertIn("mesh_00000001", meshes)
        mesh = meshes["mesh_00000001"]
        self.assertEqual(mesh["counts"]["vertex_count"], 4)
        self.assertEqual(mesh["counts"]["triangle_count"], 2)

    def test_fixture_15_broken_mesh_ref_detected(self):
        m, s, o, meshes, mats = self._load_fixture("15_broken_mesh_ref")
        errors, _ = BridgePackageValidator.validate_package(m, s, o, meshes, mats)
        self.assertTrue(any(code == "OBJECT_BROKEN_MESH_REF" for code, _ in errors))

    def test_fixture_16_mesh_index_out_of_bounds_detected(self):
        m, s, o, meshes, mats = self._load_fixture("16_mesh_index_out_of_bounds")
        errors, _ = BridgePackageValidator.validate_package(m, s, o, meshes, mats)
        self.assertTrue(any(code == "MESH_INDEX_OUT_OF_BOUNDS" for code, _ in errors))

    def test_fixture_17_material_payload_valid(self):
        m, s, o, meshes, mats = self._load_fixture("17_material_payload")
        errors, _ = BridgePackageValidator.validate_package(m, s, o, meshes, mats)
        self.assertEqual(len(errors), 0, f"Unexpected errors: {errors}")
        self.assertIn("mat_00000001", mats)
        mat = mats["mat_00000001"]
        self.assertEqual(mat["properties"]["base_color"], [0.8, 0.1, 0.1, 1.0])
        self.assertEqual(mat["properties"]["roughness"], 0.8)

    def test_fixture_18_multi_material_payload_valid(self):
        m, s, o, meshes, mats = self._load_fixture("18_multi_material_payload")
        errors, _ = BridgePackageValidator.validate_package(m, s, o, meshes, mats)
        self.assertEqual(len(errors), 0, f"Unexpected errors: {errors}")
        self.assertEqual(len(mats), 2)
        self.assertIn("mat_00000001", mats)
        self.assertIn("mat_00000002", mats)

    def test_fixture_19_broken_material_ref_detected(self):
        m, s, o, meshes, mats = self._load_fixture("19_broken_material_ref")
        errors, _ = BridgePackageValidator.validate_package(m, s, o, meshes, mats)
        self.assertTrue(any("BROKEN_MATERIAL_REF" in code for code, _ in errors))

    def test_fixture_20_invalid_pbr_value_detected(self):
        m, s, o, meshes, mats = self._load_fixture("20_invalid_pbr_value")
        errors, _ = BridgePackageValidator.validate_package(m, s, o, meshes, mats)
        self.assertTrue(any(code == "MATERIAL_OUT_OF_RANGE_METALLIC" for code, _ in errors))

    def test_fixture_21_invalid_material_schema_detected(self):
        m, s, o, meshes, mats = self._load_fixture("21_invalid_material_schema")
        errors, _ = BridgePackageValidator.validate_package(m, s, o, meshes, mats)
        self.assertTrue(any(code == "MATERIAL_INVALID_FORMAT" for code, _ in errors))

    def test_fixture_22_texture_payload_valid(self):
        fix = self._load_fixture("22_texture_payload")
        errors, _ = BridgePackageValidator.validate_package(
            fix.manifest, fix.scene, fix.objects, fix.meshes, fix.materials, fix.textures, fix.pkg_dir
        )
        self.assertEqual(len(errors), 0, f"Unexpected errors: {errors}")
        self.assertEqual(len(fix.textures), 1)
        self.assertEqual(fix.textures[0]["id"], "tex_00000001")

    def test_fixture_23_textured_material_payload_valid(self):
        fix = self._load_fixture("23_textured_material_payload")
        errors, _ = BridgePackageValidator.validate_package(
            fix.manifest, fix.scene, fix.objects, fix.meshes, fix.materials, fix.textures, fix.pkg_dir
        )
        self.assertEqual(len(errors), 0, f"Unexpected errors: {errors}")
        self.assertEqual(len(fix.materials), 1)
        mat = fix.materials["mat_00000005"]
        self.assertIn("base_color", mat.get("textures", {}))
        self.assertEqual(mat["textures"]["base_color"], "tex_00000002")

    def test_fixture_24_multi_texture_material_valid(self):
        fix = self._load_fixture("24_multi_texture_material")
        errors, _ = BridgePackageValidator.validate_package(
            fix.manifest, fix.scene, fix.objects, fix.meshes, fix.materials, fix.textures, fix.pkg_dir
        )
        self.assertEqual(len(errors), 0, f"Unexpected errors: {errors}")
        self.assertEqual(len(fix.textures), 3)
        mat = fix.materials["mat_00000006"]
        self.assertEqual(mat["textures"]["base_color"], "tex_00000003")
        self.assertEqual(mat["textures"]["roughness"], "tex_00000004")
        self.assertEqual(mat["textures"]["normal"], "tex_00000005")

    def test_fixture_25_missing_texture_ref_detected(self):
        fix = self._load_fixture("25_missing_texture_reference")
        errors, _ = BridgePackageValidator.validate_package(
            fix.manifest, fix.scene, fix.objects, fix.meshes, fix.materials, fix.textures, fix.pkg_dir
        )
        self.assertTrue(any(code == "MATERIAL_BROKEN_TEXTURE_REF" for code, _ in errors))

    def test_fixture_26_missing_texture_file_detected(self):
        fix = self._load_fixture("26_missing_texture_file")
        errors, _ = BridgePackageValidator.validate_package(
            fix.manifest, fix.scene, fix.objects, fix.meshes, fix.materials, fix.textures, fix.pkg_dir
        )
        self.assertTrue(any(code == "TEX_FILE_NOT_FOUND" for code, _ in errors))

    def test_fixture_27_invalid_texture_schema_detected(self):
        fix = self._load_fixture("27_invalid_texture_schema")
        errors, _ = BridgePackageValidator.validate_package(
            fix.manifest, fix.scene, fix.objects, fix.meshes, fix.materials, fix.textures, fix.pkg_dir
        )
        self.assertTrue(any(code in ("TEXTURE_INVALID_ID_FORMAT", "TEXTURE_INVALID_COLOR_SPACE") for code, _ in errors))

    def test_fixture_28_shared_texture_payload_valid(self):
        fix = self._load_fixture("28_shared_texture_payload")
        errors, _ = BridgePackageValidator.validate_package(
            fix.manifest, fix.scene, fix.objects, fix.meshes, fix.materials, fix.textures, fix.pkg_dir
        )
        self.assertEqual(len(errors), 0, f"Unexpected errors: {errors}")
        self.assertEqual(len(fix.textures), 1)
        self.assertEqual(len(fix.materials), 2)
        self.assertEqual(fix.materials["mat_0000000a"]["textures"]["base_color"], "tex_00000007")
        self.assertEqual(fix.materials["mat_0000000b"]["textures"]["base_color"], "tex_00000007")

    def test_fixture_29_deep_hierarchy_4_levels_valid(self):
        fix = self._load_fixture("29_deep_hierarchy_4_levels")
        errors, _ = BridgePackageValidator.validate_package(
            fix.manifest, fix.scene, fix.objects, fix.meshes, fix.materials, fix.textures, fix.pkg_dir
        )
        self.assertEqual(len(errors), 0, f"Unexpected errors: {errors}")
        self.assertEqual(len(fix.objects), 4)
        # Root -> Level1 -> Level2 -> Level3
        root_xform = BridgeTransformConverter.to_unreal_local_transform(fix.objects[0]["transform"])
        c1_xform = BridgeTransformConverter.to_unreal_local_transform(fix.objects[1]["transform"])
        c2_xform = BridgeTransformConverter.to_unreal_local_transform(fix.objects[2]["transform"])
        c3_xform = BridgeTransformConverter.to_unreal_local_transform(fix.objects[3]["transform"])
        # World transform = c3 * c2 * c1 * root
        great_grandchild_world = c3_xform * c2_xform * c1_xform * root_xform
        self.assertEqual(great_grandchild_world.translation, UnrealVector(50.0, 50.0, 150.0))

    def test_fixture_30_multiple_roots_valid(self):
        fix = self._load_fixture("30_multiple_roots")
        errors, _ = BridgePackageValidator.validate_package(
            fix.manifest, fix.scene, fix.objects, fix.meshes, fix.materials, fix.textures, fix.pkg_dir
        )
        self.assertEqual(len(errors), 0, f"Unexpected errors: {errors}")
        self.assertEqual(len(fix.objects), 5)
        # Verify roots have no parent
        roots = [obj for obj in fix.objects if not obj.get("parent_id")]
        self.assertEqual(len(roots), 3)

    def test_fixture_31_self_parent_object_detected(self):
        fix = self._load_fixture("31_self_parent_object")
        errors, _ = BridgePackageValidator.validate_package(
            fix.manifest, fix.scene, fix.objects, fix.meshes, fix.materials, fix.textures, fix.pkg_dir
        )
        self.assertTrue(any(code == "OBJECT_SELF_PARENT" for code, _ in errors))

    def test_fixture_32_three_node_cycle_detected(self):
        fix = self._load_fixture("32_three_node_cycle")
        errors, _ = BridgePackageValidator.validate_package(
            fix.manifest, fix.scene, fix.objects, fix.meshes, fix.materials, fix.textures, fix.pkg_dir
        )
        self.assertTrue(any(code == "OBJECT_HIERARCHY_CYCLE" for code, _ in errors))

    def test_fixture_33_nested_collections_valid(self):
        fix = self._load_fixture("33_nested_collections")
        errors, _ = BridgePackageValidator.validate_package(
            fix.manifest, fix.scene, fix.objects, fix.meshes, fix.materials, fix.textures, fix.pkg_dir
        )
        self.assertEqual(len(errors), 0, f"Unexpected errors: {errors}")
        self.assertEqual(len(fix.scene.get("collections", [])), 3)

    def test_fixture_34_invalid_collection_parent_detected(self):
        fix = self._load_fixture("34_invalid_collection_parent")
        errors, _ = BridgePackageValidator.validate_package(
            fix.manifest, fix.scene, fix.objects, fix.meshes, fix.materials, fix.textures, fix.pkg_dir
        )
        self.assertTrue(any(code == "COLLECTION_BROKEN_PARENT" for code, _ in errors))

    def test_fixture_35_collection_self_parent_detected(self):
        fix = self._load_fixture("35_collection_self_parent")
        errors, _ = BridgePackageValidator.validate_package(
            fix.manifest, fix.scene, fix.objects, fix.meshes, fix.materials, fix.textures, fix.pkg_dir
        )
        self.assertTrue(any(code == "COLLECTION_SELF_PARENT" for code, _ in errors))

    def test_fixture_36_collection_cycle_detected(self):
        fix = self._load_fixture("36_collection_cycle")
        errors, _ = BridgePackageValidator.validate_package(
            fix.manifest, fix.scene, fix.objects, fix.meshes, fix.materials, fix.textures, fix.pkg_dir
        )
        self.assertTrue(any(code == "COLLECTION_HIERARCHY_CYCLE" for code, _ in errors))


class TestMilestone3Integration(unittest.TestCase):
    """Integration test loading the real Milestone 3 generated package."""

    def test_load_and_reconstruct_demo_scene(self):
        self.assertTrue(DEMO_PACKAGE.exists(), f"Demo package missing at {DEMO_PACKAGE}")

        with open(DEMO_PACKAGE / "manifest.json", "r", encoding="utf-8") as f:
            manifest = json.load(f)
        with open(DEMO_PACKAGE / "scene.json", "r", encoding="utf-8") as f:
            scene = json.load(f)
        with open(DEMO_PACKAGE / "objects.json", "r", encoding="utf-8") as f:
            objects_data = json.load(f)
        objects = objects_data["objects"]

        # Validate package
        errors, warnings = BridgePackageValidator.validate_package(manifest, scene, objects)
        self.assertEqual(len(errors), 0, f"Validation errors: {errors}")

        # Verify object count & metadata
        self.assertEqual(len(objects), 2)
        locator = next(o for o in objects if o["name"] == "TableLocator")
        mesh = next(o for o in objects if o["name"] == "TableMesh")

        self.assertEqual(locator["type"], "EMPTY")
        self.assertEqual(mesh["type"], "STATIC_MESH")
        self.assertEqual(mesh["parent_id"], locator["id"])

        # Convert transforms
        loc_xform = BridgeTransformConverter.to_unreal_local_transform(locator["transform"])
        mesh_xform = BridgeTransformConverter.to_unreal_local_transform(mesh["transform"])

        # TableLocator was at Blender (1, 2, 3) -> Canonical (200, 100, 300) cm
        self.assertEqual(loc_xform.translation, UnrealVector(200.0, 100.0, 300.0))

        # TableMesh local was (0, 0, 100) cm relative to locator
        self.assertEqual(mesh_xform.translation, UnrealVector(0.0, 0.0, 100.0))

        # TableMesh world = mesh_local * locator_world
        mesh_world = mesh_xform * loc_xform
        self.assertEqual(mesh_world.translation, UnrealVector(200.0, 100.0, 400.0))


class TestMilestone5MeshValidation(unittest.TestCase):
    """Direct validation tests for Milestone 5 mesh payloads and attributes."""

    def setUp(self):
        self.base_manifest = {
            "format": "BUBRIDGE", "version": "0.1.0",
            "coordinate_system": {
                "up_axis": "Z", "forward_axis": "X", "right_axis": "Y",
                "handedness": "left_handed", "unit": "centimeter"
            }
        }
        self.base_scene = {"name": "TestScene", "collections": []}
        self.base_object = {
            "id": "obj_00000001", "name": "TestObj", "type": "STATIC_MESH",
            "transform": {
                "location": [0.0, 0.0, 0.0],
                "rotation_quaternion": [0.0, 0.0, 0.0, 1.0],
                "scale": [1.0, 1.0, 1.0]
            },
            "mesh_reference": {
                "mesh_id": "mesh_00000001",
                "file": "meshes/mesh_00000001.json",
                "submesh_index": 0
            }
        }
        self.valid_mesh = {
            "format": "BUBRIDGE_MESH", "version": "0.1.0",
            "mesh_id": "mesh_00000001", "name": "CubeMesh",
            "counts": {"vertex_count": 3, "triangle_count": 1},
            "vertices": [[0.0, 0.0, 0.0], [100.0, 0.0, 0.0], [0.0, 100.0, 0.0]],
            "triangles": [{
                "vertex_indices": [0, 1, 2],
                "normals": [[0.0, 0.0, 1.0], [0.0, 0.0, 1.0], [0.0, 0.0, 1.0]],
                "uvs": [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]],
                "material_slot_index": 0
            }],
            "material_slots": [{"slot_index": 0, "slot_name": "M_Default"}]
        }

    def test_valid_mesh(self):
        errs, _ = BridgePackageValidator.validate_package(
            self.base_manifest, self.base_scene, [self.base_object],
            {"mesh_00000001": self.valid_mesh}
        )
        self.assertEqual(len(errs), 0)

    def test_invalid_mesh_format(self):
        bad_mesh = dict(self.valid_mesh)
        bad_mesh["format"] = "INVALID_FORMAT"
        errs, _ = BridgePackageValidator.validate_package(
            self.base_manifest, self.base_scene, [self.base_object],
            {"mesh_00000001": bad_mesh}
        )
        self.assertTrue(any(code == "MESH_INVALID_FORMAT" for code, _ in errs))

    def test_invalid_mesh_id_format(self):
        errs, _ = BridgePackageValidator.validate_package(
            self.base_manifest, self.base_scene, [],
            {"invalid_id": self.valid_mesh}
        )
        self.assertTrue(any(code == "MESH_INVALID_ID_FORMAT" for code, _ in errs))

    def test_non_finite_vertex(self):
        bad_mesh = dict(self.valid_mesh)
        bad_mesh["vertices"] = [[float("nan"), 0.0, 0.0], [100.0, 0.0, 0.0], [0.0, 100.0, 0.0]]
        errs, _ = BridgePackageValidator.validate_package(
            self.base_manifest, self.base_scene, [self.base_object],
            {"mesh_00000001": bad_mesh}
        )
        self.assertTrue(any(code == "MESH_NON_FINITE_COORDINATE" for code, _ in errs))

    def test_non_finite_normal(self):
        bad_mesh = dict(self.valid_mesh)
        bad_mesh["triangles"] = [{
            "vertex_indices": [0, 1, 2],
            "normals": [[float("inf"), 0.0, 1.0], [0.0, 0.0, 1.0], [0.0, 0.0, 1.0]],
            "uvs": [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]],
            "material_slot_index": 0
        }]
        errs, _ = BridgePackageValidator.validate_package(
            self.base_manifest, self.base_scene, [self.base_object],
            {"mesh_00000001": bad_mesh}
        )
        self.assertTrue(any(code == "MESH_NON_FINITE_NORMAL" for code, _ in errs))

    def test_non_finite_uv(self):
        bad_mesh = dict(self.valid_mesh)
        bad_mesh["triangles"] = [{
            "vertex_indices": [0, 1, 2],
            "normals": [[0.0, 0.0, 1.0], [0.0, 0.0, 1.0], [0.0, 0.0, 1.0]],
            "uvs": [[float("nan"), 0.0], [1.0, 0.0], [0.0, 1.0]],
            "material_slot_index": 0
        }]
        errs, _ = BridgePackageValidator.validate_package(
            self.base_manifest, self.base_scene, [self.base_object],
            {"mesh_00000001": bad_mesh}
        )
        self.assertTrue(any(code == "MESH_NON_FINITE_UV" for code, _ in errs))

    def test_invalid_material_slot_index(self):
        bad_mesh = dict(self.valid_mesh)
        bad_mesh["triangles"] = [{
            "vertex_indices": [0, 1, 2],
            "normals": [[0.0, 0.0, 1.0], [0.0, 0.0, 1.0], [0.0, 0.0, 1.0]],
            "uvs": [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]],
            "material_slot_index": 99  # Slot 99 does not exist (count: 1)
        }]
        errs, _ = BridgePackageValidator.validate_package(
            self.base_manifest, self.base_scene, [self.base_object],
            {"mesh_00000001": bad_mesh}
        )
        self.assertTrue(any(code == "MESH_INVALID_MATERIAL_SLOT_INDEX" for code, _ in errs))


class TestMilestone6MaterialValidation(unittest.TestCase):
    """Direct validation tests for Milestone 6 material payloads and properties."""

    def setUp(self):
        self.base_manifest = {
            "format": "BUBRIDGE", "version": "0.1.0",
            "coordinate_system": {
                "up_axis": "Z", "forward_axis": "X", "right_axis": "Y",
                "handedness": "left_handed", "unit": "centimeter"
            }
        }
        self.base_scene = {"name": "TestScene", "collections": []}
        self.valid_material = {
            "format": "BUBRIDGE_MATERIAL",
            "version": "0.1.0",
            "material_id": "mat_12345678",
            "name": "M_TestPbr",
            "model": "PBR_METALLIC_ROUGHNESS",
            "properties": {
                "base_color": [0.5, 0.5, 0.5, 1.0],
                "metallic": 0.0,
                "roughness": 0.5,
                "specular": 0.5,
                "ior": 1.5,
                "opacity": 1.0,
                "blend_mode": "OPAQUE",
                "two_sided": False
            }
        }

    def test_valid_material(self):
        errs, _ = BridgePackageValidator.validate_package(
            self.base_manifest, self.base_scene, [],
            materials={"mat_12345678": self.valid_material}
        )
        self.assertEqual(len(errs), 0)

    def test_invalid_material_format(self):
        bad_mat = dict(self.valid_material)
        bad_mat["format"] = "INVALID_MATERIAL_FORMAT"
        errs, _ = BridgePackageValidator.validate_package(
            self.base_manifest, self.base_scene, [],
            materials={"mat_12345678": bad_mat}
        )
        self.assertTrue(any(code == "MATERIAL_INVALID_FORMAT" for code, _ in errs))

    def test_invalid_material_id_format(self):
        errs, _ = BridgePackageValidator.validate_package(
            self.base_manifest, self.base_scene, [],
            materials={"invalid_mat_id": self.valid_material}
        )
        self.assertTrue(any(code == "MATERIAL_INVALID_ID_FORMAT" for code, _ in errs))

    def test_invalid_material_model(self):
        bad_mat = dict(self.valid_material)
        bad_mat["model"] = "BLINN_PHONG"
        errs, _ = BridgePackageValidator.validate_package(
            self.base_manifest, self.base_scene, [],
            materials={"mat_12345678": bad_mat}
        )
        self.assertTrue(any(code == "MATERIAL_INVALID_MODEL" for code, _ in errs))

    def test_out_of_range_base_color(self):
        bad_mat = dict(self.valid_material)
        bad_mat["properties"] = dict(self.valid_material["properties"])
        bad_mat["properties"]["base_color"] = [1.5, 0.0, 0.0, 1.0]
        errs, _ = BridgePackageValidator.validate_package(
            self.base_manifest, self.base_scene, [],
            materials={"mat_12345678": bad_mat}
        )
        self.assertTrue(any(code == "MATERIAL_OUT_OF_RANGE_BASE_COLOR" for code, _ in errs))

    def test_out_of_range_metallic(self):
        bad_mat = dict(self.valid_material)
        bad_mat["properties"] = dict(self.valid_material["properties"])
        bad_mat["properties"]["metallic"] = -0.1
        errs, _ = BridgePackageValidator.validate_package(
            self.base_manifest, self.base_scene, [],
            materials={"mat_12345678": bad_mat}
        )
        self.assertTrue(any(code == "MATERIAL_OUT_OF_RANGE_METALLIC" for code, _ in errs))

    def test_out_of_range_roughness(self):
        bad_mat = dict(self.valid_material)
        bad_mat["properties"] = dict(self.valid_material["properties"])
        bad_mat["properties"]["roughness"] = 1.2
        errs, _ = BridgePackageValidator.validate_package(
            self.base_manifest, self.base_scene, [],
            materials={"mat_12345678": bad_mat}
        )
        self.assertTrue(any(code == "MATERIAL_OUT_OF_RANGE_ROUGHNESS" for code, _ in errs))

    def test_out_of_range_specular(self):
        bad_mat = dict(self.valid_material)
        bad_mat["properties"] = dict(self.valid_material["properties"])
        bad_mat["properties"]["specular"] = 2.0
        errs, _ = BridgePackageValidator.validate_package(
            self.base_manifest, self.base_scene, [],
            materials={"mat_12345678": bad_mat}
        )
        self.assertTrue(any(code == "MATERIAL_OUT_OF_RANGE_SPECULAR" for code, _ in errs))


class TestMilestone7TextureValidation(unittest.TestCase):
    """Direct validation tests for Milestone 7 texture payloads and attributes."""

    def setUp(self):
        self.base_manifest = {
            "format": "BUBRIDGE", "version": "0.1.0",
            "coordinate_system": {
                "up_axis": "Z", "forward_axis": "X", "right_axis": "Y",
                "handedness": "left_handed", "unit": "centimeter"
            }
        }
        self.base_scene = {"name": "TestScene", "collections": []}
        self.valid_texture = {
            "id": "tex_12345678",
            "name": "T_Valid",
            "relative_path": "textures/tex_12345678.png",
            "format": "PNG",
            "color_space": "sRGB",
            "dimensions": [512, 512],
            "channels": 4,
            "has_alpha": True,
            "compression_settings": "TC_Default"
        }
        self.valid_material = {
            "format": "BUBRIDGE_MATERIAL",
            "version": "0.1.0",
            "material_id": "mat_12345678",
            "name": "M_TestPbr",
            "model": "PBR_METALLIC_ROUGHNESS",
            "properties": {
                "base_color": [0.5, 0.5, 0.5, 1.0],
                "metallic": 0.0,
                "roughness": 0.5,
                "specular": 0.5,
                "ior": 1.5,
                "opacity": 1.0,
                "blend_mode": "OPAQUE",
                "two_sided": False
            },
            "textures": {
                "base_color": "tex_12345678"
            }
        }

    def test_valid_texture(self):
        errs, _ = BridgePackageValidator.validate_package(
            self.base_manifest, self.base_scene, [],
            materials={"mat_12345678": self.valid_material},
            textures=[self.valid_texture]
        )
        self.assertEqual(len(errs), 0)

    def test_invalid_texture_id_format(self):
        bad_tex = dict(self.valid_texture)
        bad_tex["id"] = "invalid_id"
        errs, _ = BridgePackageValidator.validate_package(
            self.base_manifest, self.base_scene, [],
            textures=[bad_tex]
        )
        self.assertTrue(any(code == "TEXTURE_INVALID_ID_FORMAT" for code, _ in errs))

    def test_invalid_texture_path(self):
        bad_tex = dict(self.valid_texture)
        bad_tex["relative_path"] = "images/tex_12345678.png"
        errs, _ = BridgePackageValidator.validate_package(
            self.base_manifest, self.base_scene, [],
            textures=[bad_tex]
        )
        self.assertTrue(any(code == "TEXTURE_INVALID_PATH" for code, _ in errs))

    def test_invalid_texture_colorspace(self):
        bad_tex = dict(self.valid_texture)
        bad_tex["color_space"] = "UNKNOWN_COLORSPACE"
        errs, _ = BridgePackageValidator.validate_package(
            self.base_manifest, self.base_scene, [],
            textures=[bad_tex]
        )
        self.assertTrue(any(code == "TEXTURE_INVALID_COLOR_SPACE" for code, _ in errs))

    def test_invalid_texture_dimensions(self):
        bad_tex = dict(self.valid_texture)
        bad_tex["dimensions"] = [0, -10]
        errs, _ = BridgePackageValidator.validate_package(
            self.base_manifest, self.base_scene, [],
            textures=[bad_tex]
        )
        self.assertTrue(any(code == "TEXTURE_INVALID_DIMENSIONS" for code, _ in errs))

    def test_invalid_texture_channels(self):
        bad_tex = dict(self.valid_texture)
        bad_tex["channels"] = 6
        errs, _ = BridgePackageValidator.validate_package(
            self.base_manifest, self.base_scene, [],
            textures=[bad_tex]
        )
        self.assertTrue(any(code == "TEXTURE_INVALID_CHANNELS" for code, _ in errs))

    def test_material_referencing_missing_texture(self):
        errs, _ = BridgePackageValidator.validate_package(
            self.base_manifest, self.base_scene, [],
            materials={"mat_12345678": self.valid_material},
            textures=[]  # empty textures, so tex_12345678 is missing
        )
        self.assertTrue(any(code == "MATERIAL_BROKEN_TEXTURE_REF" for code, _ in errs))


class BridgeHierarchyHelper:
    """Python mirror of hierarchy navigation logic in FBridgePackageReader / FBridgeSceneBuilder."""

    @staticmethod
    def get_root_objects(objects):
        obj_ids = {obj.get("id") for obj in objects if obj.get("id")}
        return [obj for obj in objects if not obj.get("parent_id") or obj.get("parent_id") not in obj_ids]

    @staticmethod
    def get_children_of(parent_id, objects):
        return [obj for obj in objects if obj.get("parent_id") == parent_id]

    @staticmethod
    def get_topological_object_order(objects):
        obj_map = {obj.get("id"): obj for obj in objects if obj.get("id")}
        children_map = {}
        for obj in objects:
            pid = obj.get("parent_id")
            if pid:
                children_map.setdefault(pid, []).append(obj)

        roots = BridgeHierarchyHelper.get_root_objects(objects)
        ordered = []
        queue = list(roots)
        visited = set()

        while queue:
            curr = queue.pop(0)
            cid = curr.get("id")
            if cid in visited:
                continue
            visited.add(cid)
            ordered.append(curr)
            for child in children_map.get(cid, []):
                queue.append(child)

        for obj in objects:
            if obj.get("id") not in visited:
                ordered.append(obj)
        return ordered

    @staticmethod
    def build_collection_folder_path(collection_id, collections):
        col_map = {c.get("id"): c for c in collections if c.get("id")}
        parts = []
        curr_id = collection_id
        visited = set()
        while curr_id and curr_id in col_map:
            if curr_id in visited:
                break
            visited.add(curr_id)
            c = col_map[curr_id]
            parts.append(c.get("name", curr_id))
            curr_id = c.get("parent_id")
        parts.reverse()
        return "/".join(parts)


class TestMilestone8HierarchyValidation(unittest.TestCase):
    """Milestone 8 unit tests for hierarchy navigation, collection trees, and diagnostics."""

    def setUp(self):
        self.base_manifest = {
            "format": "BUBRIDGE",
            "version": "0.1.0",
            "coordinate_system": {
                "up_axis": "Z",
                "forward_axis": "X",
                "right_axis": "Y",
                "handedness": "left_handed",
                "unit": "centimeter"
            }
        }
        self.base_scene = {
            "name": "HierarchyScene",
            "collections": [],
            "environment": {}
        }

    def test_topological_sort_roots_first(self):
        objects = [
            {"id": "obj_00000003", "name": "Level2", "parent_id": "obj_00000002"},
            {"id": "obj_00000001", "name": "Root", "parent_id": None},
            {"id": "obj_00000004", "name": "Level3", "parent_id": "obj_00000003"},
            {"id": "obj_00000002", "name": "Level1", "parent_id": "obj_00000001"},
        ]
        ordered = BridgeHierarchyHelper.get_topological_object_order(objects)
        ordered_ids = [o["id"] for o in ordered]
        self.assertEqual(ordered_ids, ["obj_00000001", "obj_00000002", "obj_00000003", "obj_00000004"])

    def test_root_objects_identification(self):
        objects = [
            {"id": "obj_00000001", "name": "Root1", "parent_id": None},
            {"id": "obj_00000002", "name": "Child1", "parent_id": "obj_00000001"},
            {"id": "obj_00000003", "name": "Root2", "parent_id": None},
            {"id": "obj_00000004", "name": "Child2", "parent_id": "obj_00000003"},
        ]
        roots = BridgeHierarchyHelper.get_root_objects(objects)
        root_ids = [r["id"] for r in roots]
        self.assertEqual(root_ids, ["obj_00000001", "obj_00000003"])

    def test_children_query(self):
        objects = [
            {"id": "obj_00000001", "name": "Root", "parent_id": None},
            {"id": "obj_00000002", "name": "ChildA", "parent_id": "obj_00000001"},
            {"id": "obj_00000003", "name": "ChildB", "parent_id": "obj_00000001"},
            {"id": "obj_00000004", "name": "Grandchild", "parent_id": "obj_00000002"},
        ]
        children = BridgeHierarchyHelper.get_children_of("obj_00000001", objects)
        child_ids = [c["id"] for c in children]
        self.assertEqual(child_ids, ["obj_00000002", "obj_00000003"])

    def test_collection_folder_path_generation(self):
        collections = [
            {"id": "col_00000001", "name": "Environment", "parent_id": None},
            {"id": "col_00000002", "name": "Buildings", "parent_id": "col_00000001"},
            {"id": "col_00000003", "name": "Props", "parent_id": "col_00000002"},
        ]
        path_root = BridgeHierarchyHelper.build_collection_folder_path("col_00000001", collections)
        path_mid = BridgeHierarchyHelper.build_collection_folder_path("col_00000002", collections)
        path_leaf = BridgeHierarchyHelper.build_collection_folder_path("col_00000003", collections)

        self.assertEqual(path_root, "Environment")
        self.assertEqual(path_mid, "Environment/Buildings")
        self.assertEqual(path_leaf, "Environment/Buildings/Props")

    def test_collection_self_parent_detection(self):
        scene = {
            "name": "Scene",
            "collections": [
                {"id": "col_00000001", "name": "SelfCol", "parent_id": "col_00000001"}
            ]
        }
        errs, _ = BridgePackageValidator.validate_package(self.base_manifest, scene, [])
        self.assertTrue(any(code == "COLLECTION_SELF_PARENT" for code, _ in errs))

    def test_collection_broken_parent_detection(self):
        scene = {
            "name": "Scene",
            "collections": [
                {"id": "col_00000001", "name": "OrphanCol", "parent_id": "col_missing"}
            ]
        }
        errs, _ = BridgePackageValidator.validate_package(self.base_manifest, scene, [])
        self.assertTrue(any(code == "COLLECTION_BROKEN_PARENT" for code, _ in errs))

    def test_collection_cycle_detection(self):
        scene = {
            "name": "Scene",
            "collections": [
                {"id": "col_00000001", "name": "ColA", "parent_id": "col_00000002"},
                {"id": "col_00000002", "name": "ColB", "parent_id": "col_00000001"},
            ]
        }
        errs, _ = BridgePackageValidator.validate_package(self.base_manifest, scene, [])
        self.assertTrue(any(code == "COLLECTION_HIERARCHY_CYCLE" for code, _ in errs))

    def test_broken_object_collection_ref_detection(self):
        scene = {
            "name": "Scene",
            "collections": [
                {"id": "col_00000001", "name": "ValidCol", "parent_id": None}
            ]
        }
        objects = [{
            "id": "obj_00000001",
            "name": "Obj",
            "type": "EMPTY",
            "collection_id": "col_nonexistent",
            "transform": {
                "location": [0.0, 0.0, 0.0],
                "rotation_quaternion": [0.0, 0.0, 0.0, 1.0],
                "scale": [1.0, 1.0, 1.0]
            }
        }]
        errs, _ = BridgePackageValidator.validate_package(self.base_manifest, scene, objects)
        self.assertTrue(any(code == "OBJECT_BROKEN_COLLECTION_REF" for code, _ in errs))


if __name__ == "__main__":
    unittest.main(verbosity=2)
