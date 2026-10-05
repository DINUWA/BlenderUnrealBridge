"""
Milestone 1 — Scene Collector & ID Generator Tests
----------------------------------------------------
Tests for:
  1. Empty scene — no objects.
  2. Single object.
  3. Multiple objects.
  4. Objects in different collections.
  5. Parent/child hierarchy.
  6. Existing bubridge_id persistence (re-running must not replace IDs).
  7. Newly discovered objects receiving IDs.
  8. Re-running the collector does not generate a new ID.

NOTE: This test suite requires Blender's embedded Python runtime (bpy).
It must be executed with:

    blender --background --python blender_addon/tests/test_scene_collector.py

The host operating system's Python installation must NOT be assumed to be the
Blender runtime and must NOT be used to execute this test.
"""

import sys
import unittest

try:
    import bpy
except ImportError:
    sys.stderr.write(
        "\n[ERROR] 'bpy' module not found.\n"
        "This test must be executed using Blender's embedded Python runtime via:\n"
        "  blender --background --python blender_addon/tests/test_scene_collector.py\n\n"
    )
    sys.exit(1)

from pathlib import Path

addon_parent = Path(__file__).resolve().parent.parent
if str(addon_parent) not in sys.path:
    sys.path.insert(0, str(addon_parent))

from blender_unreal_bridge.collectors.id_generator import (
    BUBRIDGE_ID_KEY,
    ensure_id,
    get_id,
    has_id,
)
from blender_unreal_bridge.collectors.scene_collector import (
    collect_scene,
    SUPPORTED_OBJECT_TYPES,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _purge_scene():
    """Remove all objects and non-root collections from the current scene."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=True)
    # Remove any user-created collections (keep Scene Collection / root)
    for col in list(bpy.data.collections):
        bpy.data.collections.remove(col)


def _add_mesh_cube(name="TestCube", collection=None):
    """Add a primitive mesh cube and return the object."""
    bpy.ops.mesh.primitive_cube_add()
    obj = bpy.context.active_object
    obj.name = name
    if collection is not None:
        # Unlink from current collection and link to target
        for col in list(obj.users_collection):
            col.objects.unlink(obj)
        collection.objects.link(obj)
    return obj


def _add_empty(name="TestEmpty", collection=None):
    """Add an Empty object and return it."""
    bpy.ops.object.empty_add()
    obj = bpy.context.active_object
    obj.name = name
    if collection is not None:
        for col in list(obj.users_collection):
            col.objects.unlink(obj)
        collection.objects.link(obj)
    return obj


def _make_collection(name="TestCollection"):
    """Create a new Blender collection and link it to the scene root."""
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    return col


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

class TestEmptyScene(unittest.TestCase):
    """Test 1: Empty scene produces an empty result with no errors."""

    def setUp(self):
        _purge_scene()

    def test_empty_scene_returns_no_objects(self):
        result = collect_scene()
        self.assertEqual(len(result.objects), 0)
        self.assertEqual(len(result.errors), 0)

    def test_empty_scene_has_correct_scene_name(self):
        result = collect_scene()
        self.assertEqual(result.scene_name, bpy.context.scene.name)


class TestSingleObject(unittest.TestCase):
    """Test 2: Single mesh object receives a bubridge_id."""

    def setUp(self):
        _purge_scene()

    def test_single_object_collected(self):
        _add_mesh_cube("SingleCube")
        result = collect_scene()
        self.assertEqual(len(result.objects), 1)
        self.assertEqual(result.objects[0].name, "SingleCube")

    def test_single_object_receives_id(self):
        cube = _add_mesh_cube("SingleCube")
        collect_scene()
        self.assertTrue(has_id(cube))
        bridge_id = get_id(cube)
        self.assertIsNotNone(bridge_id)
        self.assertTrue(bridge_id.startswith("obj_"))

    def test_single_object_id_in_result(self):
        cube = _add_mesh_cube("SingleCube")
        result = collect_scene()
        expected_id = get_id(cube)
        self.assertEqual(result.objects[0].bubridge_id, expected_id)

    def test_single_object_has_no_parent(self):
        _add_mesh_cube("SingleCube")
        result = collect_scene()
        self.assertIsNone(result.objects[0].parent_id)


class TestMultipleObjects(unittest.TestCase):
    """Test 3: Multiple objects all receive unique bubridge_ids."""

    def setUp(self):
        _purge_scene()

    def test_multiple_objects_collected(self):
        _add_mesh_cube("Cube1")
        _add_mesh_cube("Cube2")
        _add_mesh_cube("Cube3")
        result = collect_scene()
        self.assertEqual(len(result.objects), 3)

    def test_multiple_objects_have_unique_ids(self):
        _add_mesh_cube("Cube1")
        _add_mesh_cube("Cube2")
        _add_mesh_cube("Cube3")
        result = collect_scene()
        ids = [o.bubridge_id for o in result.objects]
        # All IDs must be unique
        self.assertEqual(len(ids), len(set(ids)))

    def test_object_names_do_not_affect_ids(self):
        """Renaming an object must not change its ID."""
        cube = _add_mesh_cube("OriginalName")
        collect_scene()
        original_id = get_id(cube)
        cube.name = "RenamedObject"
        collect_scene()
        renamed_id = get_id(cube)
        self.assertEqual(original_id, renamed_id)


class TestCollectionMembership(unittest.TestCase):
    """Test 4: Objects in different collections report correct membership."""

    def setUp(self):
        _purge_scene()

    def test_object_in_named_collection(self):
        col = _make_collection("Props")
        obj = _add_mesh_cube("PropCube", collection=col)
        result = collect_scene()
        meta = next(o for o in result.objects if o.name == obj.name)
        self.assertIn("Props", meta.collections)

    def test_object_in_multiple_collections(self):
        col_a = _make_collection("Environment")
        col_b = _make_collection("Static")
        obj = _add_mesh_cube("SharedMesh")
        # Link to both extra collections
        col_a.objects.link(obj)
        col_b.objects.link(obj)
        # Unlink from root so only user collections apply
        for col in list(obj.users_collection):
            if col.name not in ("Environment", "Static"):
                col.objects.unlink(obj)
        result = collect_scene()
        meta = next((o for o in result.objects if o.name == obj.name), None)
        self.assertIsNotNone(meta)
        self.assertIn("Environment", meta.collections)
        self.assertIn("Static", meta.collections)

    def test_object_in_root_only_has_empty_collections(self):
        """Object in only the root Scene Collection should have no named collections."""
        _add_mesh_cube("RootObject")
        result = collect_scene()
        meta = next(o for o in result.objects if o.name == "RootObject")
        self.assertEqual(meta.collections, [])


class TestParentChildHierarchy(unittest.TestCase):
    """Test 5: Parent/child relationships are correctly captured."""

    def setUp(self):
        _purge_scene()

    def test_parent_id_recorded_on_child(self):
        parent_empty = _add_empty("ParentEmpty")
        child_cube = _add_mesh_cube("ChildCube")
        child_cube.parent = parent_empty
        result = collect_scene()

        parent_meta = next(o for o in result.objects if o.name == "ParentEmpty")
        child_meta = next(o for o in result.objects if o.name == "ChildCube")

        self.assertIsNotNone(child_meta.parent_id)
        self.assertEqual(child_meta.parent_id, parent_meta.bubridge_id)

    def test_parent_object_has_no_parent(self):
        parent_empty = _add_empty("ParentEmpty")
        child_cube = _add_mesh_cube("ChildCube")
        child_cube.parent = parent_empty
        result = collect_scene()
        parent_meta = next(o for o in result.objects if o.name == "ParentEmpty")
        self.assertIsNone(parent_meta.parent_id)

    def test_deeply_nested_hierarchy(self):
        grandparent = _add_empty("Grandparent")
        parent = _add_empty("Parent")
        child = _add_mesh_cube("Child")
        parent.parent = grandparent
        child.parent = parent
        result = collect_scene()

        gp_meta = next(o for o in result.objects if o.name == "Grandparent")
        p_meta = next(o for o in result.objects if o.name == "Parent")
        c_meta = next(o for o in result.objects if o.name == "Child")

        self.assertIsNone(gp_meta.parent_id)
        self.assertEqual(p_meta.parent_id, gp_meta.bubridge_id)
        self.assertEqual(c_meta.parent_id, p_meta.bubridge_id)


class TestIdPersistence(unittest.TestCase):
    """Test 6 + 8: bubridge_id must persist and must not be regenerated on re-runs."""

    def setUp(self):
        _purge_scene()

    def test_existing_id_not_overwritten_on_rerun(self):
        cube = _add_mesh_cube("PersistentCube")
        # First collection pass — assigns ID
        collect_scene()
        first_id = get_id(cube)
        self.assertIsNotNone(first_id)
        # Second collection pass — must return same ID
        collect_scene()
        second_id = get_id(cube)
        self.assertEqual(first_id, second_id)

    def test_preassigned_id_is_respected(self):
        """If a custom property was set externally, ensure_id must not overwrite it."""
        cube = _add_mesh_cube("PreAssigned")
        predetermined = "obj_deadbeef"
        cube[BUBRIDGE_ID_KEY] = predetermined
        collect_scene()
        self.assertEqual(get_id(cube), predetermined)

    def test_many_reruns_keep_same_ids(self):
        cubes = [_add_mesh_cube(f"StableCube{i}") for i in range(5)]
        collect_scene()
        ids_first = [get_id(c) for c in cubes]
        for _ in range(3):
            collect_scene()
        ids_after = [get_id(c) for c in cubes]
        self.assertEqual(ids_first, ids_after)


class TestNewObjectsReceiveIds(unittest.TestCase):
    """Test 7: Objects added after the first pass receive IDs on the next run."""

    def setUp(self):
        _purge_scene()

    def test_new_object_added_after_first_pass_gets_id(self):
        cube1 = _add_mesh_cube("FirstCube")
        collect_scene()
        self.assertTrue(has_id(cube1))

        cube2 = _add_mesh_cube("NewCube")
        self.assertFalse(has_id(cube2))  # No ID yet

        collect_scene()
        self.assertTrue(has_id(cube2))
        self.assertIsNotNone(get_id(cube2))

    def test_new_object_id_does_not_duplicate_existing(self):
        cube1 = _add_mesh_cube("Cube1")
        collect_scene()
        id1 = get_id(cube1)

        cube2 = _add_mesh_cube("Cube2")
        collect_scene()
        id2 = get_id(cube2)

        self.assertNotEqual(id1, id2)


class TestUnsupportedObjectTypes(unittest.TestCase):
    """Unsupported types are not collected but must produce informational warnings."""

    def setUp(self):
        _purge_scene()

    def test_light_object_not_collected(self):
        bpy.ops.object.light_add(type="POINT")
        light = bpy.context.active_object
        light.name = "TestLight"
        result = collect_scene()
        names = [o.name for o in result.objects]
        self.assertNotIn("TestLight", names)

    def test_unsupported_type_produces_warning(self):
        bpy.ops.object.light_add(type="POINT")
        result = collect_scene()
        # At minimum one warning/info message about the skipped type
        self.assertGreater(len(result.warnings), 0)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run():
    suite = unittest.defaultTestLoader.loadTestsFromModule(
        sys.modules[__name__]
    )
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    run()
