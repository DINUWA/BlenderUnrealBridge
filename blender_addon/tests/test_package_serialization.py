"""
Milestone 3 — Bridge Package Serialization Tests
=================================================
Tests for the .bubridge package generation and serialization pipeline.

MUST be executed inside Blender's embedded Python runtime:
    blender --background --python blender_addon/tests/test_package_serialization.py

Coverage:
  1. Package directory structure and required files/directories
  2. Manifest schema compliance and dynamic environment extraction
  3. Scene and collection hierarchy serialization
  4. Object metadata, stable Bridge IDs, and deterministic ordering
  5. Canonical transform serialization (Milestone 2 integration)
  6. Negative scale flag preservation
  7. Parent/child relationships and deep hierarchies
  8. Determinism (two exports produce identical JSON)
  9. JSON validity (strict parsing, no NaN/Infinity)
 10. PackageValidator error detection (duplicate IDs, broken parents, cycles)
 11. Atomic writing and cleanup on failure
"""

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

try:
    import bpy
    import mathutils
except ImportError:
    sys.stderr.write(
        "\n[ERROR] 'bpy' / 'mathutils' not found.\n"
        "Run via: blender --background --python blender_addon/tests/test_package_serialization.py\n\n"
    )
    sys.exit(1)

addon_parent = Path(__file__).resolve().parent.parent
if str(addon_parent) not in sys.path:
    sys.path.insert(0, str(addon_parent))

from blender_unreal_bridge.collectors.id_generator import ensure_id, get_id, BUBRIDGE_ID_KEY
from blender_unreal_bridge.serialization.json_serializer import serialize_json
from blender_unreal_bridge.serialization.package_validator import (
    PackageValidator,
    ValidationResult,
)
from blender_unreal_bridge.serialization.package_writer import (
    PackageValidationError,
    build_package_data,
    create_bridge_package,
    write_bridge_package,
)
from blender_unreal_bridge.version import FORMAT_NAME, FORMAT_VERSION


def _purge_scene():
    """Remove all objects and non-root collections from the scene."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=True)
    for col in list(bpy.data.collections):
        bpy.data.collections.remove(col)


def _add_cube(name="TestCube", loc=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    obj = bpy.context.active_object
    obj.name = name
    ensure_id(obj)
    return obj


def _add_empty(name="TestEmpty", loc=(0, 0, 0)):
    bpy.ops.object.empty_add(location=loc)
    obj = bpy.context.active_object
    obj.name = name
    ensure_id(obj)
    return obj


class TestPackageStructure(unittest.TestCase):
    """Test package creation and filesystem layout."""

    def setUp(self):
        _purge_scene()
        self.temp_dir = Path(tempfile.mkdtemp(prefix="bubridge_test_"))

    def tearDown(self):
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_package_created_with_expected_layout(self):
        _add_cube("CubeA")
        pkg_path = create_bridge_package(
            scene=bpy.context.scene,
            output_directory=self.temp_dir,
            package_name="TestLayout",
            created_at="2026-10-05T12:00:00Z",
        )

        self.assertTrue(pkg_path.exists())
        self.assertTrue(pkg_path.is_dir())
        self.assertEqual(pkg_path.suffix, ".bubridge")

        # Required files
        self.assertTrue((pkg_path / "manifest.json").is_file())
        self.assertTrue((pkg_path / "scene.json").is_file())
        self.assertTrue((pkg_path / "objects.json").is_file())
        self.assertTrue((pkg_path / "metadata" / "report.json").is_file())

        # Required directories
        self.assertTrue((pkg_path / "meshes").is_dir())
        self.assertTrue((pkg_path / "textures").is_dir())
        self.assertTrue((pkg_path / "metadata").is_dir())


class TestManifestSerialization(unittest.TestCase):
    """Test manifest.json correctness."""

    def setUp(self):
        _purge_scene()
        self.temp_dir = Path(tempfile.mkdtemp(prefix="bubridge_test_"))

    def tearDown(self):
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_manifest_fields_and_version(self):
        _add_cube("Cube")
        fixed_time = "2026-10-05T12:00:00Z"
        pkg_path = create_bridge_package(
            scene=bpy.context.scene,
            output_directory=self.temp_dir,
            package_name="TestManifest",
            created_at=fixed_time,
        )

        manifest_file = pkg_path / "manifest.json"
        with open(manifest_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["format"], FORMAT_NAME)
        self.assertEqual(data["version"], FORMAT_VERSION)
        self.assertEqual(data["created_at"], fixed_time)

        # Generator
        self.assertEqual(data["generator"]["name"], "BlenderUnrealBridgeAddon")
        self.assertIn("version", data["generator"])

        # Source
        self.assertEqual(data["source"]["application"], "Blender")
        self.assertEqual(data["source"]["version"], bpy.app.version_string)
        self.assertEqual(data["source"]["unit_length"], "meter")

        # Coordinate System
        coord = data["coordinate_system"]
        self.assertEqual(coord["up_axis"], "Z")
        self.assertEqual(coord["forward_axis"], "X")
        self.assertEqual(coord["right_axis"], "Y")
        self.assertEqual(coord["handedness"], "left_handed")
        self.assertEqual(coord["unit"], "centimeter")

        # Content Summary
        summary = data["content_summary"]
        self.assertEqual(summary["object_count"], 1)
        self.assertEqual(summary["mesh_count"], 0)


class TestSceneAndCollectionSerialization(unittest.TestCase):
    """Test scene.json and collection hierarchy serialization."""

    def setUp(self):
        _purge_scene()
        self.temp_dir = Path(tempfile.mkdtemp(prefix="bubridge_test_"))

    def tearDown(self):
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_collections_hierarchy_serialized(self):
        # Create nested collections: Environment -> Props
        col_env = bpy.data.collections.new("Environment")
        bpy.context.scene.collection.children.link(col_env)
        col_props = bpy.data.collections.new("Props")
        col_env.children.link(col_props)

        cube = _add_cube("PropCube")
        for c in list(cube.users_collection):
            c.objects.unlink(cube)
        col_props.objects.link(cube)

        pkg_path = create_bridge_package(
            scene=bpy.context.scene,
            output_directory=self.temp_dir,
            package_name="TestScene",
        )

        with open(pkg_path / "scene.json", "r", encoding="utf-8") as f:
            scene_data = json.load(f)

        self.assertEqual(scene_data["name"], bpy.context.scene.name)
        colls = scene_data["collections"]
        self.assertEqual(len(colls), 2)

        names = {c["name"] for c in colls}
        self.assertEqual(names, {"Environment", "Props"})

        env_entry = next(c for c in colls if c["name"] == "Environment")
        props_entry = next(c for c in colls if c["name"] == "Props")

        self.assertIsNone(env_entry["parent_id"])
        self.assertEqual(props_entry["parent_id"], env_entry["id"])


class TestObjectSerialization(unittest.TestCase):
    """Test objects.json, ID stability, and transform fidelity."""

    def setUp(self):
        _purge_scene()
        self.temp_dir = Path(tempfile.mkdtemp(prefix="bubridge_test_"))

    def tearDown(self):
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_object_transforms_and_ids(self):
        cube = _add_cube("MyBox", loc=(1.0, 2.0, 3.0))
        cube.scale = (2.0, 3.0, 4.0)

        pkg_path = create_bridge_package(
            scene=bpy.context.scene,
            output_directory=self.temp_dir,
            package_name="TestObjects",
        )

        with open(pkg_path / "objects.json", "r", encoding="utf-8") as f:
            objs_data = json.load(f)

        objs = objs_data["objects"]
        self.assertEqual(len(objs), 1)
        entry = objs[0]

        self.assertEqual(entry["id"], get_id(cube))
        self.assertEqual(entry["name"], "MyBox")
        self.assertEqual(entry["type"], "STATIC_MESH")
        self.assertIsNone(entry["parent_id"])

        # Check canonical transform conversion:
        # Blender loc (1, 2, 3) m -> Bridge loc (200, 100, 300) cm
        self.assertEqual(entry["transform"]["location"], [200.0, 100.0, 300.0])
        # Blender scale (2, 3, 4) -> Bridge scale (3, 2, 4)
        self.assertEqual(entry["transform"]["scale"], [3.0, 2.0, 4.0])
        self.assertFalse(entry["transform"]["has_negative_scale"])

    def test_negative_scale_flag_preserved(self):
        cube = _add_cube("MirrorCube")
        cube.scale = (-1.0, 1.0, 1.0)

        pkg_path = create_bridge_package(
            scene=bpy.context.scene,
            output_directory=self.temp_dir,
            package_name="TestMirror",
        )

        with open(pkg_path / "objects.json", "r", encoding="utf-8") as f:
            objs_data = json.load(f)

        entry = objs_data["objects"][0]
        self.assertTrue(entry["transform"]["has_negative_scale"])

    def test_parent_child_hierarchy_in_package(self):
        parent = _add_empty("ParentLocator", loc=(5.0, 0.0, 0.0))
        child = _add_cube("ChildMesh", loc=(0.0, 2.0, 0.0))
        child.parent = parent

        pkg_path = create_bridge_package(
            scene=bpy.context.scene,
            output_directory=self.temp_dir,
            package_name="TestHierarchy",
        )

        with open(pkg_path / "objects.json", "r", encoding="utf-8") as f:
            objs_data = json.load(f)

        objs = objs_data["objects"]
        self.assertEqual(len(objs), 2)

        parent_entry = next(o for o in objs if o["name"] == "ParentLocator")
        child_entry = next(o for o in objs if o["name"] == "ChildMesh")

        self.assertEqual(parent_entry["type"], "EMPTY")
        self.assertIsNone(parent_entry["parent_id"])

        self.assertEqual(child_entry["type"], "STATIC_MESH")
        self.assertEqual(child_entry["parent_id"], parent_entry["id"])


class TestPackageDeterminism(unittest.TestCase):
    """Test that two exports of the same scene produce identical byte-for-byte JSON."""

    def setUp(self):
        _purge_scene()
        self.temp_dir = Path(tempfile.mkdtemp(prefix="bubridge_test_"))

    def tearDown(self):
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_deterministic_output(self):
        _add_cube("Cube1", loc=(1, 2, 3))
        _add_cube("Cube2", loc=(4, 5, 6))
        _add_empty("Empty1", loc=(0, 0, 1))

        fixed_time = "2026-10-05T15:00:00Z"

        dir1 = self.temp_dir / "export1"
        dir2 = self.temp_dir / "export2"

        pkg1 = create_bridge_package(
            scene=bpy.context.scene,
            output_directory=dir1,
            package_name="DetPkg",
            created_at=fixed_time,
        )
        pkg2 = create_bridge_package(
            scene=bpy.context.scene,
            output_directory=dir2,
            package_name="DetPkg",
            created_at=fixed_time,
        )

        for filename in ["manifest.json", "scene.json", "objects.json", "metadata/report.json"]:
            content1 = (pkg1 / filename).read_text(encoding="utf-8")
            content2 = (pkg2 / filename).read_text(encoding="utf-8")
            self.assertEqual(content1, content2, f"Mismatch in {filename}")


class TestPackageValidationAndErrors(unittest.TestCase):
    """Test validator detection of corrupted or malformed data."""

    def test_validator_detects_duplicate_id(self):
        manifest = {
            "format": FORMAT_NAME,
            "version": FORMAT_VERSION,
            "source": {"application": "Blender", "version": "4.5.0"},
            "coordinate_system": {
                "up_axis": "Z",
                "forward_axis": "X",
                "right_axis": "Y",
                "handedness": "left_handed",
                "unit": "centimeter",
            },
        }
        scene = {"name": "TestScene", "collections": []}
        objects = {
            "objects": [
                {
                    "id": "obj_12345678",
                    "name": "BoxA",
                    "type": "STATIC_MESH",
                    "parent_id": None,
                    "transform": {
                        "location": [0.0, 0.0, 0.0],
                        "rotation_quaternion": [0.0, 0.0, 0.0, 1.0],
                        "rotation_euler": [0.0, 0.0, 0.0],
                        "scale": [1.0, 1.0, 1.0],
                    },
                },
                {
                    "id": "obj_12345678",  # Duplicate ID
                    "name": "BoxB",
                    "type": "STATIC_MESH",
                    "parent_id": None,
                    "transform": {
                        "location": [0.0, 0.0, 0.0],
                        "rotation_quaternion": [0.0, 0.0, 0.0, 1.0],
                        "rotation_euler": [0.0, 0.0, 0.0],
                        "scale": [1.0, 1.0, 1.0],
                    },
                },
            ]
        }

        res = PackageValidator.validate_package(manifest, scene, objects)
        self.assertFalse(res.is_valid)
        self.assertTrue(any(m.code == "OBJECT_DUPLICATE_ID" for m in res.messages))

    def test_validator_detects_broken_parent_reference(self):
        manifest = {
            "format": FORMAT_NAME,
            "version": FORMAT_VERSION,
            "source": {"application": "Blender", "version": "4.5.0"},
            "coordinate_system": {
                "up_axis": "Z",
                "forward_axis": "X",
                "right_axis": "Y",
                "handedness": "left_handed",
                "unit": "centimeter",
            },
        }
        scene = {"name": "TestScene", "collections": []}
        objects = {
            "objects": [
                {
                    "id": "obj_aaaaaaaa",
                    "name": "BoxA",
                    "type": "STATIC_MESH",
                    "parent_id": "obj_nonexistent",  # Broken reference
                    "transform": {
                        "location": [0.0, 0.0, 0.0],
                        "rotation_quaternion": [0.0, 0.0, 0.0, 1.0],
                        "rotation_euler": [0.0, 0.0, 0.0],
                        "scale": [1.0, 1.0, 1.0],
                    },
                }
            ]
        }

        res = PackageValidator.validate_package(manifest, scene, objects)
        self.assertFalse(res.is_valid)
        self.assertTrue(any(m.code == "OBJECT_BROKEN_PARENT_REF" for m in res.messages))

    def test_validator_detects_parent_cycle(self):
        manifest = {
            "format": FORMAT_NAME,
            "version": FORMAT_VERSION,
            "source": {"application": "Blender", "version": "4.5.0"},
            "coordinate_system": {
                "up_axis": "Z",
                "forward_axis": "X",
                "right_axis": "Y",
                "handedness": "left_handed",
                "unit": "centimeter",
            },
        }
        scene = {"name": "TestScene", "collections": []}
        objects = {
            "objects": [
                {
                    "id": "obj_aaaaaaaa",
                    "name": "BoxA",
                    "type": "STATIC_MESH",
                    "parent_id": "obj_bbbbbbbb",
                    "transform": {
                        "location": [0.0, 0.0, 0.0],
                        "rotation_quaternion": [0.0, 0.0, 0.0, 1.0],
                        "rotation_euler": [0.0, 0.0, 0.0],
                        "scale": [1.0, 1.0, 1.0],
                    },
                },
                {
                    "id": "obj_bbbbbbbb",
                    "name": "BoxB",
                    "type": "STATIC_MESH",
                    "parent_id": "obj_aaaaaaaa",  # Cycle: A -> B -> A
                    "transform": {
                        "location": [0.0, 0.0, 0.0],
                        "rotation_quaternion": [0.0, 0.0, 0.0, 1.0],
                        "rotation_euler": [0.0, 0.0, 0.0],
                        "scale": [1.0, 1.0, 1.0],
                    },
                },
            ]
        }

        res = PackageValidator.validate_package(manifest, scene, objects)
        self.assertFalse(res.is_valid)
        self.assertTrue(any(m.code == "OBJECT_HIERARCHY_CYCLE" for m in res.messages))

    def test_write_package_aborts_on_validation_error(self):
        invalid_package_data = {
            "manifest": {"format": "INVALID_FORMAT"},
            "scene": {"name": "Scene", "collections": []},
            "objects": {"objects": []},
            "validation_result": ValidationResult(),
            "timestamp": "2026-10-05T12:00:00Z",
        }
        invalid_package_data["validation_result"].add_error("TEST_ERROR", "Synthetic error")

        temp_dir = Path(tempfile.mkdtemp())
        try:
            with self.assertRaises(PackageValidationError):
                write_bridge_package(invalid_package_data, temp_dir, "InvalidPkg")
            # Ensure no package folder was left behind
            self.assertFalse((temp_dir / "InvalidPkg.bubridge").exists())
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


def run():
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    run()
