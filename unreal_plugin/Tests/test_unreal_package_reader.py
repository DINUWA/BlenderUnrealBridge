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
    def validate_package(cls, manifest, scene, objects):
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

        return errors, warnings


class TestUnrealPackageReaderFixtures(unittest.TestCase):
    """Test validation of all 13 fixtures against the reader's validation rules."""

    def _load_fixture(self, name):
        pkg_dir = FIXTURES_DIR / f"{name}.bubridge"
        with open(pkg_dir / "manifest.json", "r", encoding="utf-8") as f:
            manifest = json.load(f)
        with open(pkg_dir / "scene.json", "r", encoding="utf-8") as f:
            scene = json.load(f)
        with open(pkg_dir / "objects.json", "r", encoding="utf-8") as f:
            objects_data = json.load(f)
        return manifest, scene, objects_data["objects"]

    def test_fixture_01_identity_valid(self):
        m, s, o = self._load_fixture("01_identity_scene")
        errors, _ = BridgePackageValidator.validate_package(m, s, o)
        self.assertEqual(len(errors), 0)

    def test_fixture_02_translated_valid(self):
        m, s, o = self._load_fixture("02_single_translated")
        errors, _ = BridgePackageValidator.validate_package(m, s, o)
        self.assertEqual(len(errors), 0)
        xform = BridgeTransformConverter.to_unreal_local_transform(o[0]["transform"])
        self.assertEqual(xform.translation, UnrealVector(250.0, -100.0, 50.0))

    def test_fixture_03_rotated_valid(self):
        m, s, o = self._load_fixture("03_rotated_object")
        errors, _ = BridgePackageValidator.validate_package(m, s, o)
        self.assertEqual(len(errors), 0)
        quat = BridgeTransformConverter.to_unreal_rotation(o[0]["transform"]["rotation_quaternion"])
        self.assertAlmostEqual(quat.size_squared(), 1.0, delta=1e-3)

    def test_fixture_04_scaled_valid(self):
        m, s, o = self._load_fixture("04_scaled_object")
        errors, _ = BridgePackageValidator.validate_package(m, s, o)
        self.assertEqual(len(errors), 0)
        xform = BridgeTransformConverter.to_unreal_local_transform(o[0]["transform"])
        self.assertEqual(xform.scale, UnrealVector(2.0, 0.5, 3.0))

    def test_fixture_05_negative_scale_valid(self):
        m, s, o = self._load_fixture("05_negative_scale")
        errors, _ = BridgePackageValidator.validate_package(m, s, o)
        self.assertEqual(len(errors), 0)
        xform = BridgeTransformConverter.to_unreal_local_transform(o[0]["transform"])
        self.assertEqual(xform.scale, UnrealVector(-1.0, 1.0, 1.0))
        self.assertTrue(o[0]["transform"]["has_negative_scale"])

    def test_fixture_06_parent_child_valid(self):
        m, s, o = self._load_fixture("06_parent_child")
        errors, _ = BridgePackageValidator.validate_package(m, s, o)
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(o), 2)
        parent_xform = BridgeTransformConverter.to_unreal_local_transform(o[0]["transform"])
        child_xform = BridgeTransformConverter.to_unreal_local_transform(o[1]["transform"])
        # World transform = child * parent
        child_world = child_xform * parent_xform
        self.assertEqual(child_world.translation, UnrealVector(100.0, 50.0, 0.0))

    def test_fixture_07_deep_hierarchy_valid(self):
        m, s, o = self._load_fixture("07_deep_hierarchy")
        errors, _ = BridgePackageValidator.validate_package(m, s, o)
        self.assertEqual(len(errors), 0)
        gp_xform = BridgeTransformConverter.to_unreal_local_transform(o[0]["transform"])
        p_xform = BridgeTransformConverter.to_unreal_local_transform(o[1]["transform"])
        c_xform = BridgeTransformConverter.to_unreal_local_transform(o[2]["transform"])
        # Child world = c * p * gp
        child_world = c_xform * p_xform * gp_xform
        self.assertEqual(child_world.translation, UnrealVector(100.0, 50.0, 100.0))

    def test_fixture_08_invalid_manifest_detected(self):
        m, s, o = self._load_fixture("08_invalid_manifest")
        errors, _ = BridgePackageValidator.validate_package(m, s, o)
        self.assertTrue(any(code == "MANIFEST_INVALID_FORMAT" for code, _ in errors))

    def test_fixture_09_duplicate_id_detected(self):
        m, s, o = self._load_fixture("09_duplicate_id")
        errors, _ = BridgePackageValidator.validate_package(m, s, o)
        self.assertTrue(any(code == "OBJECT_DUPLICATE_ID" for code, _ in errors))

    def test_fixture_10_broken_parent_detected(self):
        m, s, o = self._load_fixture("10_broken_parent")
        errors, _ = BridgePackageValidator.validate_package(m, s, o)
        self.assertTrue(any(code == "OBJECT_BROKEN_PARENT_REF" for code, _ in errors))

    def test_fixture_11_hierarchy_cycle_detected(self):
        m, s, o = self._load_fixture("11_hierarchy_cycle")
        errors, _ = BridgePackageValidator.validate_package(m, s, o)
        self.assertTrue(any(code == "OBJECT_HIERARCHY_CYCLE" for code, _ in errors))

    def test_fixture_12_invalid_transform_detected(self):
        m, s, o = self._load_fixture("12_invalid_transform")
        errors, _ = BridgePackageValidator.validate_package(m, s, o)
        self.assertTrue(any("TRANSFORM" in code for code, _ in errors))

    def test_fixture_13_unsupported_version_detected(self):
        m, s, o = self._load_fixture("13_unsupported_version")
        errors, _ = BridgePackageValidator.validate_package(m, s, o)
        self.assertTrue(any(code == "MANIFEST_UNSUPPORTED_MAJOR_VERSION" for code, _ in errors))


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
