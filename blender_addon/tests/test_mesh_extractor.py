"""
test_mesh_extractor.py
======================
Unit tests for Milestone 5 Blender mesh geometry extraction:
  - Canonical coordinate conversion (cm, left-handed)
  - Left-handed winding order flip (v0, v2, v1)
  - Corner normals and UV extraction
  - Material slot mappings
  - Shared mesh datablock deduplication
  - Non-destructive evaluation
  - Deterministic repeatable extraction
"""

from pathlib import Path
import sys
import unittest
import bpy
import bmesh

addon_parent = Path(__file__).resolve().parent.parent
if str(addon_parent) not in sys.path:
    sys.path.insert(0, str(addon_parent))

from blender_unreal_bridge.geometry.mesh_extractor import extract_mesh_data
from blender_unreal_bridge.collectors.id_generator import ensure_mesh_id, get_mesh_id
from blender_unreal_bridge.serialization.package_writer import build_package_data



def _purge_scene():
    bpy.ops.wm.read_homefile(use_empty=True)
    for block in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.collections):
        for item in list(block):
            block.remove(item, do_unlink=True)


class TestMeshExtractor(unittest.TestCase):
    """Test suite for geometry extraction."""

    def setUp(self):
        _purge_scene()

    def tearDown(self):
        _purge_scene()

    def test_single_cube_extraction(self):
        """Extract a standard 2x2x2m cube and verify vertices, triangles, and bounds."""
        bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, 0.0, 0.0))
        cube = bpy.context.active_object

        data = extract_mesh_data(cube)

        self.assertEqual(data["format"], "BUBRIDGE_MESH")
        self.assertEqual(data["version"], "0.1.0")
        self.assertTrue(data["mesh_id"].startswith("mesh_"))
        self.assertEqual(data["counts"]["vertex_count"], 8)
        self.assertEqual(data["counts"]["triangle_count"], 12)

        # 2m cube centered at (0,0,0) in Blender: x, y, z in [-1, 1] meters.
        # In canonical cm: [-100, 100] cm.
        bounds = data["bounds"]
        self.assertAlmostEqual(bounds["min"][0], -100.0, delta=1e-3)
        self.assertAlmostEqual(bounds["min"][1], -100.0, delta=1e-3)
        self.assertAlmostEqual(bounds["min"][2], -100.0, delta=1e-3)
        self.assertAlmostEqual(bounds["max"][0], 100.0, delta=1e-3)
        self.assertAlmostEqual(bounds["max"][1], 100.0, delta=1e-3)
        self.assertAlmostEqual(bounds["max"][2], 100.0, delta=1e-3)

    def test_coordinate_conversion(self):
        """Verify Blender (X=1, Y=2, Z=3) m maps to Canonical (X=200, Y=100, Z=300) cm."""
        mesh = bpy.data.meshes.new("TestCoordMesh")
        mesh.from_pydata([[1.0, 2.0, 3.0], [0.0, 0.0, 0.0], [0.0, 1.0, 0.0]], [], [[0, 1, 2]])
        mesh.update()
        obj = bpy.data.objects.new("TestCoordObj", mesh)
        bpy.context.scene.collection.objects.link(obj)

        data = extract_mesh_data(obj)
        v0 = data["vertices"][0]
        # Blender (1, 2, 3) -> Canon (Y*100, X*100, Z*100) = (200, 100, 300)
        self.assertEqual(v0, [200.0, 100.0, 300.0])

    def test_winding_order_flip(self):
        """Verify triangle winding is flipped for Left-Handed space: (0, 1, 2) -> (0, 2, 1)."""
        mesh = bpy.data.meshes.new("WindingMesh")
        mesh.from_pydata([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], [], [[0, 1, 2]])
        mesh.update()
        obj = bpy.data.objects.new("WindingObj", mesh)
        bpy.context.scene.collection.objects.link(obj)

        data = extract_mesh_data(obj)
        tri = data["triangles"][0]
        # In Blender, vertices were [0, 1, 2].
        # In Canonical Left-Handed, indices must be [0, 2, 1].
        self.assertEqual(tri["vertex_indices"], [0, 2, 1])

    def test_normals_are_unit_length(self):
        """Verify all extracted normals are unit length finite vectors."""
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1.0)
        sphere = bpy.context.active_object

        data = extract_mesh_data(sphere)
        for tri in data["triangles"]:
            for n in tri["normals"]:
                length_sq = n[0] * n[0] + n[1] * n[1] + n[2] * n[2]
                self.assertAlmostEqual(length_sq, 1.0, delta=1e-3)

    def test_uv_extraction(self):
        """Verify UV layer extraction from a primitive cube."""
        bpy.ops.mesh.primitive_cube_add(size=2.0)
        cube = bpy.context.active_object

        data = extract_mesh_data(cube)
        self.assertEqual(data["counts"]["uv_layer_count"], 1)

        # Check that UVs are not all (0, 0)
        all_zero = True
        for tri in data["triangles"]:
            for uv in tri["uvs"]:
                if uv != [0.0, 0.0]:
                    all_zero = False
                    break
        self.assertFalse(all_zero, "Expected UV coordinates from default cube")

    def test_material_slots_mapping(self):
        """Verify multi-material slot mapping on mesh triangles."""
        bpy.ops.mesh.primitive_cube_add(size=2.0)
        cube = bpy.context.active_object

        mat1 = bpy.data.materials.new("Mat_Red")
        mat2 = bpy.data.materials.new("Mat_Blue")
        cube.data.materials.append(mat1)
        cube.data.materials.append(mat2)

        # Assign second material to half of polygons
        for i, poly in enumerate(cube.data.polygons):
            poly.material_index = 0 if i < 3 else 1

        data = extract_mesh_data(cube)
        self.assertEqual(data["counts"]["material_slot_count"], 2)
        self.assertEqual(data["material_slots"][0]["slot_name"], "Mat_Red")
        self.assertEqual(data["material_slots"][1]["slot_name"], "Mat_Blue")

        slot_indices = {tri["material_slot_index"] for tri in data["triangles"]}
        self.assertEqual(slot_indices, {0, 1})

    def test_shared_mesh_deduplication(self):
        """Two objects sharing the same mesh datablock must share the same mesh_id."""
        bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 0, 0))
        cube1 = bpy.context.active_object

        # Create second object sharing cube1's mesh datablock
        cube2 = bpy.data.objects.new("Cube_Instance_2", cube1.data)
        bpy.context.scene.collection.objects.link(cube2)

        data1 = extract_mesh_data(cube1)
        data2 = extract_mesh_data(cube2)

        self.assertEqual(data1["mesh_id"], data2["mesh_id"])

        # When packaging the whole scene:
        pkg = build_package_data()
        self.assertEqual(len(pkg["meshes"]), 1)
        self.assertEqual(pkg["manifest"]["content_summary"]["mesh_count"], 1)

        # But there are two objects in objects.json referencing the same mesh
        objs = pkg["objects"]["objects"]
        self.assertEqual(len(objs), 2)
        self.assertEqual(objs[0]["mesh_reference"]["mesh_id"], data1["mesh_id"])
        self.assertEqual(objs[1]["mesh_reference"]["mesh_id"], data1["mesh_id"])

    def test_non_destructive_extraction(self):
        """Ensure original Blender mesh vertices, faces, and names are unchanged."""
        bpy.ops.mesh.primitive_cube_add(size=2.0)
        cube = bpy.context.active_object

        orig_vert_count = len(cube.data.vertices)
        orig_poly_count = len(cube.data.polygons)

        extract_mesh_data(cube)

        self.assertEqual(len(cube.data.vertices), orig_vert_count)
        self.assertEqual(len(cube.data.polygons), orig_poly_count)

    def test_extraction_determinism(self):
        """Extracting the same mesh twice must produce identical dictionaries."""
        bpy.ops.mesh.primitive_cylinder_add(radius=1.0, depth=2.0)
        cyl = bpy.context.active_object

        data_a = extract_mesh_data(cyl)
        data_b = extract_mesh_data(cyl)

        self.assertEqual(data_a, data_b)


if __name__ == "__main__":
    unittest.main()
