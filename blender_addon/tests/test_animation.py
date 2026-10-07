"""
Unit tests for Milestone 9 Animation Pipeline in Blender.
Tests armature and bone extraction, rest pose coordinate conversions,
vertex skinning weights extraction, animation clip keyframe sampling,
and complete package serialization and validation.
"""

import unittest
import math
import bpy
import mathutils

from blender_unreal_bridge.collectors.id_generator import (
    ensure_skeleton_id,
    get_skeleton_id,
    ensure_bone_id,
    get_bone_id,
    ensure_animation_id,
    get_animation_id,
)
from blender_unreal_bridge.animation.armature_extractor import extract_skeleton_data
from blender_unreal_bridge.animation.skinning_extractor import (
    find_associated_armature,
    extract_skinning_data,
)
from blender_unreal_bridge.animation.animation_extractor import extract_animations_for_armature
from blender_unreal_bridge.geometry.mesh_extractor import extract_mesh_data
from blender_unreal_bridge.serialization.package_writer import build_package_data
from blender_unreal_bridge.serialization.package_validator import PackageValidator


class TestAnimationPipeline(unittest.TestCase):
    """Test suite for Milestone 9 Animation Pipeline."""

    def setUp(self):
        # Clean existing scene objects
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def test_id_generators(self):
        """Test deterministic and stable ID generators for skeletons, bones, and animations."""
        # Armature object
        arm_data = bpy.data.armatures.new(name="TestArmatureData")
        arm_obj = bpy.data.objects.new("TestArmature", arm_data)
        bpy.context.collection.objects.link(arm_obj)

        skel_id1 = ensure_skeleton_id(arm_obj)
        self.assertTrue(skel_id1.startswith("skel_"))
        self.assertEqual(len(skel_id1), 13)
        self.assertEqual(get_skeleton_id(arm_obj), skel_id1)
        # Calling ensure again returns same ID
        self.assertEqual(ensure_skeleton_id(arm_obj), skel_id1)

        # Bone ID
        bpy.context.view_layer.objects.active = arm_obj
        bpy.ops.object.mode_set(mode="EDIT")
        edit_bone = arm_data.edit_bones.new("Bone1")
        edit_bone.head = (0, 0, 0)
        edit_bone.tail = (0, 0, 1)
        bpy.ops.object.mode_set(mode="OBJECT")

        pose_bone = arm_obj.pose.bones["Bone1"]
        bone_id1 = ensure_bone_id(pose_bone)
        self.assertTrue(bone_id1.startswith("bone_"))
        self.assertEqual(len(bone_id1), 13)
        self.assertEqual(get_bone_id(pose_bone), bone_id1)

        # Action / Animation ID
        action = bpy.data.actions.new(name="TestAction")
        anim_id1 = ensure_animation_id(action)
        self.assertTrue(anim_id1.startswith("anim_"))
        self.assertEqual(len(anim_id1), 13)
        self.assertEqual(get_animation_id(action), anim_id1)

    def test_armature_extraction(self):
        """Test extraction of bone hierarchy and rest pose transforms."""
        arm_data = bpy.data.armatures.new(name="BipedArmature")
        arm_obj = bpy.data.objects.new("Biped", arm_data)
        bpy.context.collection.objects.link(arm_obj)

        bpy.context.view_layer.objects.active = arm_obj
        bpy.ops.object.mode_set(mode="EDIT")

        root_bone = arm_data.edit_bones.new("Root")
        root_bone.head = (0.0, 0.0, 0.0)
        root_bone.tail = (0.0, 0.0, 1.0)

        child_bone = arm_data.edit_bones.new("Spine")
        child_bone.head = (0.0, 0.0, 1.0)
        child_bone.tail = (0.0, 0.0, 2.0)
        child_bone.parent = root_bone

        bpy.ops.object.mode_set(mode="OBJECT")

        skel_data = extract_skeleton_data(arm_obj)
        self.assertTrue(skel_data["id"].startswith("skel_"))
        self.assertEqual(skel_data["name"], "Biped")
        self.assertEqual(len(skel_data["bones"]), 2)

        # Root bone is first (topological sort)
        root = skel_data["bones"][0]
        self.assertEqual(root["name"], "Root")
        self.assertIsNone(root["parent_id"])

        # Spine bone is second and references root
        spine = skel_data["bones"][1]
        self.assertEqual(spine["name"], "Spine")
        self.assertEqual(spine["parent_id"], root["id"])
        # Spine local translation relative to root: head at (0, 0, 1) m along bone +Y -> (100, 0, 0) cm in canonical Bridge (+X forward)
        spine_loc = spine["transform"]["location"]
        self.assertAlmostEqual(spine_loc[0], 100.0, places=3)
        self.assertAlmostEqual(spine_loc[1], 0.0, places=3)
        self.assertAlmostEqual(spine_loc[2], 0.0, places=3)

    def test_skinning_extraction(self):
        """Test extraction of vertex skinning influences and normalization."""
        # Create Armature
        arm_data = bpy.data.armatures.new(name="SkinArmData")
        arm_obj = bpy.data.objects.new("SkinArm", arm_data)
        bpy.context.collection.objects.link(arm_obj)

        bpy.context.view_layer.objects.active = arm_obj
        bpy.ops.object.mode_set(mode="EDIT")
        b1 = arm_data.edit_bones.new("BoneA")
        b1.head = (0, 0, 0)
        b1.tail = (0, 0, 1)
        bpy.ops.object.mode_set(mode="OBJECT")

        # Create Mesh
        mesh = bpy.data.meshes.new(name="SkinMesh")
        mesh_obj = bpy.data.objects.new("SkinObject", mesh)
        bpy.context.collection.objects.link(mesh_obj)

        # 2 vertices
        mesh.from_pydata([(0, 0, 0), (0, 0, 1)], [], [])
        mesh.update()

        # Vertex group named after BoneA
        vg = mesh_obj.vertex_groups.new(name="BoneA")
        vg.add([0], 0.5, "REPLACE")
        vg.add([1], 1.0, "REPLACE")

        # Add Armature Modifier
        mod = mesh_obj.modifiers.new(name="ArmatureMod", type="ARMATURE")
        mod.object = arm_obj

        # Verify discovery
        found_arm = find_associated_armature(mesh_obj)
        self.assertEqual(found_arm, arm_obj)

        # Extract skinning
        mesh_data_mock = {"vertices": [[0, 0, 0], [0, 0, 100]]}
        skinning_data = extract_skinning_data(mesh_obj, arm_obj, mesh_data_mock)

        self.assertIsNotNone(skinning_data)
        self.assertTrue(skinning_data["skeleton_id"].startswith("skel_"))
        self.assertEqual(len(skinning_data["influences"]), 2)

        # Weights are normalized: v0 had only one bone at 0.5 -> normalized to 1.0
        v0_infs = skinning_data["influences"][0]
        self.assertEqual(len(v0_infs), 1)
        self.assertAlmostEqual(v0_infs[0]["weight"], 1.0, places=4)

    def test_animation_clip_extraction(self):
        """Test non-destructive evaluation and keyframe extraction of an Action."""
        arm_data = bpy.data.armatures.new(name="AnimArmData")
        arm_obj = bpy.data.objects.new("AnimArm", arm_data)
        bpy.context.collection.objects.link(arm_obj)

        bpy.context.view_layer.objects.active = arm_obj
        bpy.ops.object.mode_set(mode="EDIT")
        b1 = arm_data.edit_bones.new("Root")
        b1.head = (0, 0, 0)
        b1.tail = (0, 0, 1)
        bpy.ops.object.mode_set(mode="OBJECT")

        # Create Action with location keyframes on pose bone
        action = bpy.data.actions.new(name="WalkAction")
        arm_obj.animation_data_create()
        arm_obj.animation_data.action = action

        pbone = arm_obj.pose.bones["Root"]
        pbone.location = (0, 0, 0)
        pbone.keyframe_insert(data_path="location", frame=1)
        pbone.location = (1.0, 0, 0)
        pbone.keyframe_insert(data_path="location", frame=5)

        # Extract animations
        clips = extract_animations_for_armature(arm_obj, bpy.context.scene)
        self.assertEqual(len(clips), 1)
        clip = clips[0]
        self.assertEqual(clip["name"], "WalkAction")
        self.assertEqual(clip["frame_range"], [1.0, 5.0])
        self.assertEqual(len(clip["tracks"]), 1)

        track = clip["tracks"][0]
        loc_keys = track["channels"]["location"]
        self.assertEqual(len(loc_keys), 5)  # Frames 1, 2, 3, 4, 5 sampled
        # Frame 1: location (0, 0, 0)
        self.assertEqual(loc_keys[0]["frame"], 1.0)
        self.assertEqual(loc_keys[0]["value"], [0.0, 0.0, 0.0])
        # Frame 5: location (1, 0, 0) in Blender (+X Right) -> (+Y in LH centimeters: +100 cm)
        self.assertEqual(loc_keys[4]["frame"], 5.0)
        self.assertAlmostEqual(loc_keys[4]["value"][1], 100.0, places=2)

    def test_full_package_build_with_animation(self):
        """Test end-to-end package generation and validation for scene with armature and skeletal mesh."""
        # Armature
        arm_data = bpy.data.armatures.new(name="CharArmData")
        arm_obj = bpy.data.objects.new("CharArm", arm_data)
        bpy.context.collection.objects.link(arm_obj)

        bpy.context.view_layer.objects.active = arm_obj
        bpy.ops.object.mode_set(mode="EDIT")
        b1 = arm_data.edit_bones.new("Root")
        b1.head = (0, 0, 0)
        b1.tail = (0, 0, 1)
        bpy.ops.object.mode_set(mode="OBJECT")

        # Action
        action = bpy.data.actions.new(name="Idle")
        arm_obj.animation_data_create()
        arm_obj.animation_data.action = action
        pbone = arm_obj.pose.bones["Root"]
        pbone.keyframe_insert(data_path="location", frame=1)

        # Mesh
        mesh = bpy.data.meshes.new(name="CharMesh")
        mesh_obj = bpy.data.objects.new("CharObj", mesh)
        bpy.context.collection.objects.link(mesh_obj)
        mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
        mesh.update()

        vg = mesh_obj.vertex_groups.new(name="Root")
        vg.add([0, 1, 2], 1.0, "REPLACE")

        mod = mesh_obj.modifiers.new(name="Armature", type="ARMATURE")
        mod.object = arm_obj

        # Build package
        pkg_data = build_package_data(scene=bpy.context.scene)
        val_res = pkg_data["validation_result"]
        self.assertTrue(val_res.is_valid, f"Validation errors: {[m.message for m in val_res.messages if m.level == 'ERROR']}")

        manifest = pkg_data["manifest"]
        self.assertEqual(manifest["content_summary"]["skeleton_count"], 1)
        self.assertEqual(manifest["content_summary"]["animation_count"], 1)

        # Objects list has ARMATURE and SKELETAL_MESH
        objects = pkg_data["objects"]["objects"]
        types = {o["type"] for o in objects}
        self.assertIn("ARMATURE", types)
        self.assertIn("SKELETAL_MESH", types)

        # Animations document
        anim_doc = pkg_data["animations"]
        self.assertEqual(anim_doc["format"], "BUBRIDGE_ANIMATIONS")
        self.assertEqual(len(anim_doc["skeletons"]), 1)
        self.assertEqual(len(anim_doc["animations"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
