"""
Milestone 8 — Hierarchy & Collection Validation Tests
------------------------------------------------------
Tests for:
  1. Deep parent-child hierarchy extraction (Root -> Child -> Grandchild -> GreatGrandchild).
  2. Multiple independent roots with children.
  3. Nested collection hierarchy extraction (parent_id tracking).
  4. Multi-collection membership (collection_ids list).
  5. Object self-parent and hierarchy cycle detection.
  6. Collection self-parent and collection cycle detection.
  7. Object referencing broken collection detection.
  8. Non-destructive export (scene hierarchy and matrices unchanged).

NOTE: This test suite requires Blender's embedded Python runtime (bpy).
Execute with:
    blender --background --python blender_addon/tests/test_hierarchy.py
"""

import sys
import unittest
from pathlib import Path

try:
    import bpy
    import mathutils
except ImportError:
    sys.stderr.write(
        "\n[ERROR] 'bpy' module not found.\n"
        "This test must be executed using Blender's embedded Python runtime via:\n"
        "  blender --background --python blender_addon/tests/test_hierarchy.py\n\n"
    )
    sys.exit(1)

addon_parent = Path(__file__).resolve().parent.parent
if str(addon_parent) not in sys.path:
    sys.path.insert(0, str(addon_parent))

from blender_unreal_bridge.collectors.id_generator import ensure_id, get_id
from blender_unreal_bridge.serialization.package_validator import (
    PackageValidator,
    ValidationResult,
)
from blender_unreal_bridge.serialization.package_writer import build_package_data


def _purge_scene():
    """Remove all objects and user collections."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=True)
    for col in list(bpy.data.collections):
        bpy.data.collections.remove(col)


def _add_empty(name="Empty", parent=None, location=(0, 0, 0)):
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=location)
    obj = bpy.context.active_object
    obj.name = name
    if parent is not None:
        obj.parent = parent
    return obj


def _add_cube(name="Cube", parent=None, location=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.active_object
    obj.name = name
    if parent is not None:
        obj.parent = parent
    return obj


class TestMilestone8Hierarchy(unittest.TestCase):

    def setUp(self):
        _purge_scene()

    def tearDown(self):
        _purge_scene()

    def test_deep_hierarchy_extraction(self):
        """Test extraction of a 4-level deep hierarchy: Root -> Child -> Grandchild -> GreatGrandchild."""
        root = _add_empty("Root", location=(0, 0, 1))
        child = _add_empty("Child", parent=root, location=(0.5, 0, 0))
        grandchild = _add_empty("Grandchild", parent=child, location=(0, 0.5, 0))
        great_grandchild = _add_cube("GreatGrandchild", parent=grandchild, location=(0, 0, 0.5))

        data = build_package_data(bpy.context.scene)
        objects = data["objects"]["objects"]
        self.assertEqual(len(objects), 4)

        obj_by_name = {o["name"]: o for o in objects}
        self.assertIsNone(obj_by_name["Root"]["parent_id"])
        self.assertEqual(obj_by_name["Child"]["parent_id"], obj_by_name["Root"]["id"])
        self.assertEqual(obj_by_name["Grandchild"]["parent_id"], obj_by_name["Child"]["id"])
        self.assertEqual(obj_by_name["GreatGrandchild"]["parent_id"], obj_by_name["Grandchild"]["id"])

        # Check local transform preservation (child locations relative to parent)
        # Blender (0.5, 0, 0) -> Left-handed cm: Canon_Y = Blender_X * 100 = 50.0
        c_loc = obj_by_name["Child"]["transform"]["location"]
        self.assertAlmostEqual(c_loc[1], 50.0, places=3)

    def test_multiple_independent_roots(self):
        """Test extraction of multiple independent root objects with children."""
        root_a = _add_empty("RootA", location=(1, 0, 0))
        child_a = _add_cube("ChildA", parent=root_a, location=(0.1, 0, 0))

        root_b = _add_empty("RootB", location=(-1, 0, 0))
        child_b = _add_cube("ChildB", parent=root_b, location=(0, 0.1, 0))

        root_c = _add_cube("RootC", location=(0, 1, 0))

        data = build_package_data(bpy.context.scene)
        objects = data["objects"]["objects"]
        self.assertEqual(len(objects), 5)

        obj_by_name = {o["name"]: o for o in objects}
        self.assertIsNone(obj_by_name["RootA"]["parent_id"])
        self.assertIsNone(obj_by_name["RootB"]["parent_id"])
        self.assertIsNone(obj_by_name["RootC"]["parent_id"])

        self.assertEqual(obj_by_name["ChildA"]["parent_id"], obj_by_name["RootA"]["id"])
        self.assertEqual(obj_by_name["ChildB"]["parent_id"], obj_by_name["RootB"]["id"])

    def test_nested_collection_hierarchy(self):
        """Test extraction of nested collection hierarchy."""
        col_env = bpy.data.collections.new("Environment")
        bpy.context.scene.collection.children.link(col_env)

        col_bld = bpy.data.collections.new("Buildings")
        col_env.children.link(col_bld)

        col_props = bpy.data.collections.new("Props")
        col_bld.children.link(col_props)

        # Add object to Props
        obj = _add_cube("PropCube")
        # Remove from scene collection and link to Props
        bpy.context.scene.collection.objects.unlink(obj)
        col_props.objects.link(obj)

        data = build_package_data(bpy.context.scene)
        collections = data["scene"]["collections"]
        self.assertEqual(len(collections), 3)

        col_by_name = {c["name"]: c for c in collections}
        self.assertIsNone(col_by_name["Environment"]["parent_id"])
        self.assertEqual(col_by_name["Buildings"]["parent_id"], col_by_name["Environment"]["id"])
        self.assertEqual(col_by_name["Props"]["parent_id"], col_by_name["Buildings"]["id"])

        # Check object collection assignment
        obj_data = data["objects"]["objects"][0]
        self.assertEqual(obj_data["collection_id"], col_by_name["Props"]["id"])
        self.assertIn(col_by_name["Props"]["id"], obj_data["collection_ids"])

    def test_object_self_parent_validation(self):
        """Test that an object referencing itself as parent is detected by validator."""
        objects = [{
            "id": "obj_00000001",
            "name": "SelfParent",
            "type": "EMPTY",
            "parent_id": "obj_00000001",
            "transform": {
                "location": [0.0, 0.0, 0.0],
                "rotation_quaternion": [0.0, 0.0, 0.0, 1.0],
                "scale": [1.0, 1.0, 1.0]
            }
        }]
        res = ValidationResult()
        PackageValidator.validate_objects({"objects": objects}, res)
        self.assertFalse(res.is_valid)
        err_codes = [m.code for m in res.messages if m.level == "ERROR"]
        self.assertIn("OBJECT_SELF_PARENT", err_codes)

    def test_collection_self_parent_validation(self):
        """Test that a collection referencing itself as parent is detected by validator."""
        scene = {
            "name": "Scene",
            "collections": [
                {
                    "id": "col_00000001",
                    "name": "SelfCol",
                    "parent_id": "col_00000001"
                }
            ],
            "environment": {}
        }
        res = ValidationResult()
        PackageValidator.validate_scene(scene, res)
        self.assertFalse(res.is_valid)
        err_codes = [m.code for m in res.messages if m.level == "ERROR"]
        self.assertIn("COLLECTION_SELF_PARENT", err_codes)

    def test_collection_cycle_validation(self):
        """Test that cyclic collection parent references are detected by validator."""
        scene = {
            "name": "Scene",
            "collections": [
                {
                    "id": "col_00000001",
                    "name": "ColA",
                    "parent_id": "col_00000002"
                },
                {
                    "id": "col_00000002",
                    "name": "ColB",
                    "parent_id": "col_00000001"
                }
            ],
            "environment": {}
        }
        res = ValidationResult()
        PackageValidator.validate_scene(scene, res)
        self.assertFalse(res.is_valid)
        err_codes = [m.code for m in res.messages if m.level == "ERROR"]
        self.assertIn("COLLECTION_HIERARCHY_CYCLE", err_codes)

    def test_object_broken_collection_ref_validation(self):
        """Test cross-validation detecting object referencing missing collection."""
        manifest = {
            "format": "BUBRIDGE",
            "version": "0.1.0",
            "coordinate_system": {
                "up_axis": "Z",
                "forward_axis": "X",
                "right_axis": "Y",
                "handedness": "left_handed",
                "unit": "centimeter"
            },
            "source": {
                "application": "Blender",
                "version": "4.5.3 LTS"
            }
        }
        scene = {
            "name": "Scene",
            "collections": [
                {"id": "col_00000001", "name": "ValidCol", "parent_id": None}
            ],
            "environment": {}
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
        res = PackageValidator.validate_package(manifest, scene, {"objects": objects}, {})
        self.assertFalse(res.is_valid)
        err_codes = [m.code for m in res.messages if m.level == "ERROR"]
        self.assertIn("OBJECT_BROKEN_COLLECTION_REF", err_codes)

    def test_non_destructive_export(self):
        """Verify that extracting/exporting a hierarchy does not alter scene objects or transforms."""
        root = _add_empty("Root", location=(1, 2, 3))
        child = _add_cube("Child", parent=root, location=(4, 5, 6))

        orig_root_matrix = root.matrix_world.copy()
        orig_child_matrix = child.matrix_world.copy()

        # Run extraction
        data = build_package_data(bpy.context.scene)

        # Check matrices are untouched
        self.assertEqual(root.matrix_world, orig_root_matrix)
        self.assertEqual(child.matrix_world, orig_child_matrix)
        self.assertEqual(child.parent, root)


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMilestone8Hierarchy)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
