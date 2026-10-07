"""
test_texture_extractor.py
=========================
Unit and integration tests for Milestone 7 PBR Texture extraction,
path resolution, color space handling, deduplication, packaging, and validation.
"""

from pathlib import Path
import sys
import tempfile
import unittest
import bpy

addon_parent = Path(__file__).resolve().parent.parent
if str(addon_parent) not in sys.path:
    sys.path.insert(0, str(addon_parent))

from blender_unreal_bridge.collectors.id_generator import (
    ensure_texture_id,
    get_texture_id,
    has_texture_id,
)
from blender_unreal_bridge.materials.texture_extractor import (
    extract_texture_from_image,
    extract_material_textures,
)
from blender_unreal_bridge.materials.material_extractor import (
    extract_material_data,
)
from blender_unreal_bridge.serialization.package_writer import (
    build_package_data,
    write_bridge_package,
)
from blender_unreal_bridge.serialization.package_validator import (
    PackageValidator,
)


def _purge_scene():
    """Clear all objects, meshes, materials, and images from Blender."""
    for block in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.images):
        for item in list(block):
            block.remove(item, do_unlink=True)


class TestTextureExtractor(unittest.TestCase):
    """Unit tests for texture extraction from Blender materials."""

    def setUp(self):
        _purge_scene()
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()
        _purge_scene()

    def _create_dummy_image(self, name: str, width: int = 64, height: int = 64, write_file: bool = True) -> bpy.types.Image:
        """Helper to create a temporary test image with an on-disk file."""
        img = bpy.data.images.new(name, width=width, height=height)
        if write_file:
            file_path = Path(self.temp_dir.name) / f"{name}.png"
            img.filepath = str(file_path)
            img.file_format = "PNG"
            img.save()
        return img

    def test_stable_texture_id(self):
        """Texture IDs must be stable and start with 'tex_'."""
        img = self._create_dummy_image("T_Test_BaseColor")
        tex_id1 = ensure_texture_id(img)
        self.assertTrue(tex_id1.startswith("tex_"))
        self.assertEqual(len(tex_id1), 12)

        # Re-fetch ID
        tex_id2 = ensure_texture_id(img)
        self.assertEqual(tex_id1, tex_id2)
        self.assertTrue(has_texture_id(img))
        self.assertEqual(get_texture_id(img), tex_id1)

    def test_base_color_texture_discovery(self):
        """Principled BSDF Base Color image texture is extracted with sRGB color space."""
        img = self._create_dummy_image("T_Rock_BaseColor")
        mat = bpy.data.materials.new("M_Rock")
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        bsdf = nodes.get("Principled BSDF")
        tex_node = nodes.new("ShaderNodeTexImage")
        tex_node.image = img
        links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])

        tex_map, disc_textures, diags = extract_material_textures(mat)
        self.assertIn("base_color", tex_map)
        tex_id = tex_map["base_color"]
        self.assertIn(tex_id, disc_textures)

        meta = disc_textures[tex_id]
        self.assertEqual(meta["format"], "PNG")
        self.assertEqual(meta["color_space"], "sRGB")
        self.assertEqual(meta["compression_settings"], "TC_Default")
        self.assertEqual(meta["dimensions"], [64, 64])

    def test_roughness_and_metallic_textures(self):
        """Roughness and Metallic textures are extracted with Linear color space."""
        img_rough = self._create_dummy_image("T_Metal_Roughness")
        img_rough.colorspace_settings.name = "Non-Color"
        img_metal = self._create_dummy_image("T_Metal_Metallic")
        img_metal.colorspace_settings.name = "Non-Color"

        mat = bpy.data.materials.new("M_Metal")
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        bsdf = nodes.get("Principled BSDF")

        node_rough = nodes.new("ShaderNodeTexImage")
        node_rough.image = img_rough
        links.new(node_rough.outputs["Color"], bsdf.inputs["Roughness"])

        node_metal = nodes.new("ShaderNodeTexImage")
        node_metal.image = img_metal
        links.new(node_metal.outputs["Color"], bsdf.inputs["Metallic"])

        tex_map, disc_textures, diags = extract_material_textures(mat)
        self.assertIn("roughness", tex_map)
        self.assertIn("metallic", tex_map)
        self.assertEqual(disc_textures[tex_map["roughness"]]["color_space"], "Linear")
        self.assertEqual(disc_textures[tex_map["metallic"]]["color_space"], "Linear")

    def test_normal_map_node_connection(self):
        """Normal map connected via ShaderNodeNormalMap is extracted with TC_Normalmap."""
        img_norm = self._create_dummy_image("T_Rock_Normal")
        img_norm.colorspace_settings.name = "Non-Color"

        mat = bpy.data.materials.new("M_RockNormal")
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        bsdf = nodes.get("Principled BSDF")

        norm_map_node = nodes.new("ShaderNodeNormalMap")
        tex_node = nodes.new("ShaderNodeTexImage")
        tex_node.image = img_norm

        links.new(tex_node.outputs["Color"], norm_map_node.inputs["Color"])
        links.new(norm_map_node.outputs["Normal"], bsdf.inputs["Normal"])

        tex_map, disc_textures, diags = extract_material_textures(mat)
        self.assertIn("normal", tex_map)
        norm_meta = disc_textures[tex_map["normal"]]
        self.assertEqual(norm_meta["compression_settings"], "TC_Normalmap")
        self.assertEqual(norm_meta["color_space"], "Linear")

    def test_missing_texture_diagnostic(self):
        """Referencing a non-existent file on disk produces TEX_FILE_NOT_FOUND diagnostic."""
        img = bpy.data.images.new("T_Missing", width=32, height=32)
        img.filepath = "C:/non_existent_folder_xyz/missing_texture.png"

        mat = bpy.data.materials.new("M_MissingTex")
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        bsdf = nodes.get("Principled BSDF")

        tex_node = nodes.new("ShaderNodeTexImage")
        tex_node.image = img
        links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])

        tex_map, disc_textures, diags = extract_material_textures(mat)
        self.assertTrue(any(d["code"] == "TEX_FILE_NOT_FOUND" for d in diags))

    def test_colorspace_mismatch_warning(self):
        """Roughness texture with sRGB color space produces TEX_COLORSPACE_MISMATCH warning."""
        img = self._create_dummy_image("T_Bad_Roughness")
        img.colorspace_settings.name = "sRGB"  # Incorrect for roughness!

        mat = bpy.data.materials.new("M_BadColorspace")
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        bsdf = nodes.get("Principled BSDF")

        tex_node = nodes.new("ShaderNodeTexImage")
        tex_node.image = img
        links.new(tex_node.outputs["Color"], bsdf.inputs["Roughness"])

        tex_map, disc_textures, diags = extract_material_textures(mat)
        self.assertTrue(any(d["code"] == "TEX_COLORSPACE_MISMATCH" for d in diags))

    def test_texture_deduplication(self):
        """Multiple materials sharing the same Image datablock share the same texture ID."""
        img = self._create_dummy_image("T_Shared_BaseColor")

        mat1 = bpy.data.materials.new("M_Mat1")
        mat1.use_nodes = True
        node1 = mat1.node_tree.nodes.new("ShaderNodeTexImage")
        node1.image = img
        mat1.node_tree.links.new(node1.outputs["Color"], mat1.node_tree.nodes["Principled BSDF"].inputs["Base Color"])

        mat2 = bpy.data.materials.new("M_Mat2")
        mat2.use_nodes = True
        node2 = mat2.node_tree.nodes.new("ShaderNodeTexImage")
        node2.image = img
        mat2.node_tree.links.new(node2.outputs["Color"], mat2.node_tree.nodes["Principled BSDF"].inputs["Base Color"])

        tex_map1, disc1, _ = extract_material_textures(mat1)
        tex_map2, disc2, _ = extract_material_textures(mat2)

        self.assertEqual(tex_map1["base_color"], tex_map2["base_color"])

    def test_packed_image_handling(self):
        """Packed Blender images are recognized as packed and extracted without errors."""
        img = self._create_dummy_image("T_Packed")
        img.pack()
        self.assertIsNotNone(img.packed_file)

        mat = bpy.data.materials.new("M_Packed")
        mat.use_nodes = True
        node = mat.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = img
        mat.node_tree.links.new(node.outputs["Color"], mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"])

        tex_map, disc_textures, diags = extract_material_textures(mat)
        self.assertIn("base_color", tex_map)
        self.assertTrue(disc_textures[tex_map["base_color"]]["_is_packed"])
        self.assertFalse(any(d["code"] == "TEX_FILE_NOT_FOUND" for d in diags))

    def test_package_writer_with_textures(self):
        """Full end-to-end package serialization includes textures.json and copied image file."""
        img = self._create_dummy_image("T_Cube_Diff")
        mat = bpy.data.materials.new("M_CubeMat")
        mat.use_nodes = True
        node = mat.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = img
        mat.node_tree.links.new(node.outputs["Color"], mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"])

        # Create a mesh object assigned with this material
        mesh = bpy.data.meshes.new("CubeMesh")
        obj = bpy.data.objects.new("CubeObj", mesh)
        bpy.context.scene.collection.objects.link(obj)
        obj.data.materials.append(mat)

        pkg_data = build_package_data(scene=bpy.context.scene)
        self.assertEqual(pkg_data["manifest"]["content_summary"]["texture_count"], 1)
        self.assertEqual(len(pkg_data["textures"]), 1)

        pkg_dir = write_bridge_package(pkg_data, self.temp_dir.name, "TexturedScene")
        self.assertTrue(pkg_dir.exists())
        self.assertTrue((pkg_dir / "textures.json").exists())

        tex_id = list(pkg_data["textures"].keys())[0]
        tex_file = pkg_dir / f"textures/{tex_id}.png"
        self.assertTrue(tex_file.exists())
        self.assertGreater(tex_file.stat().st_size, 0)

    def test_m6_regression_constant_materials(self):
        """Materials without textures serialize cleanly with texture_count: 0 and valid schema."""
        mat = bpy.data.materials.new("M_Constant")
        mat.use_nodes = True
        mat_data = extract_material_data(mat)
        self.assertEqual(mat_data["textures"], {})

        mesh = bpy.data.meshes.new("PlainMesh")
        obj = bpy.data.objects.new("PlainObj", mesh)
        bpy.context.scene.collection.objects.link(obj)
        obj.data.materials.append(mat)

        pkg_data = build_package_data(scene=bpy.context.scene)
        self.assertEqual(pkg_data["manifest"]["content_summary"]["texture_count"], 0)
        self.assertTrue(pkg_data["validation_result"].is_valid)


if __name__ == "__main__":
    unittest.main(verbosity=2)
