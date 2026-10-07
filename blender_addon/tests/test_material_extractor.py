"""
test_material_extractor.py
==========================
Unit and integration tests for Milestone 6 PBR Material extraction,
stable IDs, package serialization, and validation.
"""

import json
from pathlib import Path
import sys
import tempfile
import unittest
import bpy

addon_parent = Path(__file__).resolve().parent.parent
if str(addon_parent) not in sys.path:
    sys.path.insert(0, str(addon_parent))

from blender_unreal_bridge.collectors.id_generator import (
    ensure_material_id,
    get_material_id,
    has_material_id,
)
from blender_unreal_bridge.materials.material_extractor import (
    extract_material_data,
    MATERIAL_FORMAT,
    MATERIAL_VERSION,
)
from blender_unreal_bridge.serialization.package_writer import (
    build_package_data,
    write_bridge_package,
)
from blender_unreal_bridge.serialization.package_validator import (
    PackageValidator,
    ValidationResult,
)


def _purge_scene():
    """Clear all objects, meshes, and materials from the current Blender file."""
    for block in (bpy.data.objects, bpy.data.meshes, bpy.data.materials):
        for item in list(block):
            block.remove(item, do_unlink=True)


class TestMaterialExtractor(unittest.TestCase):
    """Test extract_material_data across different material configurations."""

    def setUp(self):
        _purge_scene()

    def tearDown(self):
        _purge_scene()

    def test_default_principled_bsdf(self):
        """Default Principled BSDF should extract expected default PBR values."""
        mat = bpy.data.materials.new("DefaultPrincipled")
        mat.use_nodes = True
        data = extract_material_data(mat)

        self.assertEqual(data["format"], MATERIAL_FORMAT)
        self.assertEqual(data["version"], MATERIAL_VERSION)
        self.assertEqual(data["name"], "DefaultPrincipled")
        self.assertTrue(data["material_id"].startswith("mat_"))
        self.assertEqual(data["model"], "PBR_METALLIC_ROUGHNESS")
        self.assertEqual(len(data["base_color"]), 4)
        self.assertAlmostEqual(data["metallic"], 0.0, places=4)
        self.assertAlmostEqual(data["roughness"], 0.5, places=4)
        self.assertAlmostEqual(data["specular"], 0.5, places=4)
        self.assertEqual(data["blend_mode"], "OPAQUE")
        self.assertFalse(data["two_sided"])

    def test_custom_pbr_properties(self):
        """Custom PBR scalar and color properties should be accurately extracted."""
        mat = bpy.data.materials.new("CustomPBR")
        mat.use_nodes = True
        node = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")

        node.inputs["Base Color"].default_value = (0.8, 0.2, 0.1, 1.0)
        node.inputs["Metallic"].default_value = 0.75
        node.inputs["Roughness"].default_value = 0.3
        if "Specular IOR Level" in node.inputs:
            node.inputs["Specular IOR Level"].default_value = 0.25
        elif "Specular" in node.inputs:
            node.inputs["Specular"].default_value = 0.25

        data = extract_material_data(mat)
        self.assertAlmostEqual(data["base_color"][0], 0.8, places=4)
        self.assertAlmostEqual(data["base_color"][1], 0.2, places=4)
        self.assertAlmostEqual(data["base_color"][2], 0.1, places=4)
        self.assertAlmostEqual(data["base_color"][3], 1.0, places=4)
        self.assertAlmostEqual(data["metallic"], 0.75, places=4)
        self.assertAlmostEqual(data["roughness"], 0.3, places=4)
        self.assertAlmostEqual(data["specular"], 0.25, places=4)

    def test_material_without_node_tree(self):
        """Materials with use_nodes=False should fallback to diffuse_color."""
        mat = bpy.data.materials.new("NoNodesMat")
        mat.use_nodes = False
        mat.diffuse_color = (0.3, 0.6, 0.9, 1.0)

        data = extract_material_data(mat)
        self.assertEqual(data["format"], MATERIAL_FORMAT)
        self.assertAlmostEqual(data["base_color"][0], 0.3, places=4)
        self.assertAlmostEqual(data["base_color"][1], 0.6, places=4)
        self.assertAlmostEqual(data["base_color"][2], 0.9, places=4)

    def test_material_fallback_when_none(self):
        """Calling extract_material_data(None) returns a valid default material."""
        data = extract_material_data(None)
        self.assertEqual(data["format"], MATERIAL_FORMAT)
        self.assertEqual(data["material_id"], "mat_default")
        self.assertEqual(data["model"], "PBR_METALLIC_ROUGHNESS")

    def test_material_with_unsupported_texture_node(self):
        """Texture nodes connected to inputs should not crash M6 extractor."""
        mat = bpy.data.materials.new("TexturedMat")
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        principled = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
        principled.inputs["Base Color"].default_value = (0.5, 0.5, 0.5, 1.0)

        # Add image texture node and link to Base Color
        tex_node = nodes.new("ShaderNodeTexImage")
        links.new(tex_node.outputs["Color"], principled.inputs["Base Color"])

        # In M6, texture nodes are ignored and socket default_value is extracted
        data = extract_material_data(mat)
        self.assertEqual(data["format"], MATERIAL_FORMAT)
        self.assertEqual(len(data["base_color"]), 4)


class TestMaterialIdentity(unittest.TestCase):
    """Test stable material ID generation and idempotence."""

    def setUp(self):
        _purge_scene()

    def tearDown(self):
        _purge_scene()

    def test_stable_material_id_idempotent(self):
        """Calling ensure_material_id multiple times on same material returns same ID."""
        mat = bpy.data.materials.new("StableMat")
        id1 = ensure_material_id(mat)
        id2 = ensure_material_id(mat)
        self.assertEqual(id1, id2)
        self.assertTrue(id1.startswith("mat_"))
        self.assertEqual(len(id1), 12)
        self.assertEqual(get_material_id(mat), id1)
        self.assertTrue(has_material_id(mat))

    def test_different_materials_have_different_ids(self):
        """Distinct material datablocks must have distinct IDs."""
        mat1 = bpy.data.materials.new("MatA")
        mat2 = bpy.data.materials.new("MatB")
        id1 = ensure_material_id(mat1)
        id2 = ensure_material_id(mat2)
        self.assertNotEqual(id1, id2)

    def test_material_datablock_reuse(self):
        """Multiple objects sharing the same material datablock reference identical material ID."""
        mat = bpy.data.materials.new("SharedMat")
        bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
        cube1 = bpy.context.active_object
        cube1.data.materials.append(mat)

        bpy.ops.mesh.primitive_cube_add(location=(5, 0, 0))
        cube2 = bpy.context.active_object
        cube2.data.materials.append(mat)

        pkg = build_package_data()
        self.assertEqual(len(pkg["materials"]), 1)
        mat_id = list(pkg["materials"].keys())[0]

        # Both objects reference the same material ID
        obj1 = next(o for o in pkg["objects"]["objects"] if o["name"] == cube1.name)
        obj2 = next(o for o in pkg["objects"]["objects"] if o["name"] == cube2.name)
        self.assertEqual(obj1["material_slots"][0]["material_id"], mat_id)
        self.assertEqual(obj2["material_slots"][0]["material_id"], mat_id)


class TestMaterialPackageSerialization(unittest.TestCase):
    """Test package building and serialization of materials into .bubridge."""

    def setUp(self):
        _purge_scene()
        self.temp_dir = Path(tempfile.mkdtemp(prefix="bubridge_mat_test_"))

    def tearDown(self):
        _purge_scene()
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_materials_serialized_to_package(self):
        """Exporting a scene with materials writes materials/<material_id>.json."""
        mat = bpy.data.materials.new("GoldMat")
        mat.use_nodes = True
        node = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        node.inputs["Base Color"].default_value = (1.0, 0.76, 0.33, 1.0)
        node.inputs["Metallic"].default_value = 1.0
        node.inputs["Roughness"].default_value = 0.1

        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.active_object
        cube.data.materials.append(mat)

        pkg_data = build_package_data()
        self.assertEqual(pkg_data["manifest"]["content_summary"]["material_count"], 1)
        self.assertEqual(len(pkg_data["materials"]), 1)

        pkg_dir = write_bridge_package(pkg_data, self.temp_dir, "MatTestScene")
        self.assertTrue((pkg_dir / "materials").exists())

        mat_id = list(pkg_data["materials"].keys())[0]
        mat_file = pkg_dir / "materials" / f"{mat_id}.json"
        self.assertTrue(mat_file.exists())

        with open(mat_file, "r", encoding="utf-8") as f:
            written_mat = json.load(f)

        self.assertEqual(written_mat["format"], MATERIAL_FORMAT)
        self.assertEqual(written_mat["material_id"], mat_id)
        self.assertAlmostEqual(written_mat["metallic"], 1.0, places=4)
        self.assertAlmostEqual(written_mat["roughness"], 0.1, places=4)


class TestMaterialValidation(unittest.TestCase):
    """Test PackageValidator material checks and referential integrity."""

    def setUp(self):
        self.valid_material = {
            "format": "BUBRIDGE_MATERIAL",
            "version": "0.1.0",
            "material_id": "mat_12345678",
            "name": "ValidMaterial",
            "model": "PBR_METALLIC_ROUGHNESS",
            "base_color": [0.8, 0.2, 0.1, 1.0],
            "metallic": 0.5,
            "roughness": 0.5,
            "specular": 0.5,
        }

    def test_valid_material_passes(self):
        result = ValidationResult()
        PackageValidator.validate_material(self.valid_material, result)
        self.assertTrue(result.is_valid)

    def test_invalid_material_format(self):
        bad = dict(self.valid_material, format="WRONG_FORMAT")
        result = ValidationResult()
        PackageValidator.validate_material(bad, result)
        self.assertFalse(result.is_valid)
        self.assertTrue(any(m.code == "MATERIAL_INVALID_FORMAT" for m in result.messages))

    def test_invalid_material_id(self):
        bad = dict(self.valid_material, material_id="invalid_id")
        result = ValidationResult()
        PackageValidator.validate_material(bad, result)
        self.assertFalse(result.is_valid)
        self.assertTrue(any(m.code == "MATERIAL_INVALID_ID_FORMAT" for m in result.messages))

    def test_out_of_range_metallic(self):
        bad = dict(self.valid_material, metallic=1.5)
        result = ValidationResult()
        PackageValidator.validate_material(bad, result)
        self.assertFalse(result.is_valid)
        self.assertTrue(any(m.code == "MATERIAL_OUT_OF_RANGE_METALLIC" for m in result.messages))

    def test_out_of_range_roughness(self):
        bad = dict(self.valid_material, roughness=-0.1)
        result = ValidationResult()
        PackageValidator.validate_material(bad, result)
        self.assertFalse(result.is_valid)
        self.assertTrue(any(m.code == "MATERIAL_OUT_OF_RANGE_ROUGHNESS" for m in result.messages))

    def test_broken_material_reference(self):
        """Object slot referencing non-existent material ID must produce error."""
        manifest = {
            "format": "BUBRIDGE", "version": "0.1.0",
            "coordinate_system": {
                "up_axis": "Z", "forward_axis": "X", "right_axis": "Y",
                "handedness": "left_handed", "unit": "centimeter"
            }
        }
        scene = {"name": "TestScene", "collections": []}
        objects = {
            "objects": [{
                "id": "obj_00000001", "name": "CubeObj", "type": "STATIC_MESH",
                "transform": {"location": [0,0,0], "rotation_quaternion": [0,0,0,1], "scale": [1,1,1]},
                "material_slots": [{"slot_index": 0, "slot_name": "M_Slot", "material_id": "mat_nonexistent"}]
            }]
        }
        materials = {"mat_12345678": self.valid_material}

        res = PackageValidator.validate_package(manifest, scene, objects, materials=materials)
        self.assertFalse(res.is_valid)
        self.assertTrue(any(m.code == "OBJECT_BROKEN_MATERIAL_REF" for m in res.messages))


if __name__ == "__main__":
    unittest.main(verbosity=2)
