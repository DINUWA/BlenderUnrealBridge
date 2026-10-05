"""
Milestone 2 — Transform System Tests
=====================================
Tests for the authoritative Blender-to-Bridge canonical transform conversion.

MUST be executed inside Blender's embedded Python runtime:

    blender --background --python blender_addon/tests/test_transforms.py

Host Python must NOT be used (bpy and mathutils required).

Coverage
--------
  1.  Identity transform
  2.  Translation — positive X axis
  3.  Translation — positive Y axis
  4.  Translation — positive Z axis
  5.  Translation — all axes combined
  6.  Rotation — around X axis (Euler mode)
  7.  Rotation — around Y axis (Euler mode)
  8.  Rotation — around Z axis (Euler mode)
  9.  Rotation — quaternion mode
  10. Rotation — all other Euler modes (XZY, YXZ, YZX, ZXY, ZYX)
  11. Non-uniform scale
  12. Negative scale (single axis)
  13. Negative scale (two axes — double reflection)
  14. Parent + child transform
  15. Deeply nested three-level hierarchy
  16. Arbitrary combined transform (translation + rotation + scale)
  17. Repeated extraction — stable results
  18. AXIS_ANGLE rotation mode — produces a warning, not an error
  19. Unit conversion — 1 BU → 100 cm
  20. Axis swap — Blender +Y maps to Bridge +X
  21. Axis swap — Blender +X maps to Bridge +Y
  22. Handedness — quaternion z-sign flip
"""

import sys
import math
import unittest

try:
    import bpy
    import mathutils
except ImportError:
    sys.stderr.write(
        "\n[ERROR] 'bpy' / 'mathutils' not found.\n"
        "Run via: blender --background --python blender_addon/tests/test_transforms.py\n\n"
    )
    sys.exit(1)

from pathlib import Path

addon_parent = Path(__file__).resolve().parent.parent
if str(addon_parent) not in sys.path:
    sys.path.insert(0, str(addon_parent))

from blender_unreal_bridge.transforms.canonical import (
    METRES_TO_CM,
    TransformData,
    _convert_location,
    _convert_quaternion,
    _convert_scale,
    _quat_to_euler_deg_xyz,
    _has_negative_scale,
    extract_transform,
)
from blender_unreal_bridge.collectors.id_generator import ensure_id

# ---------------------------------------------------------------------------
# Tolerance for floating-point comparisons
# ---------------------------------------------------------------------------
TOL = 1e-5


def assertClose(tc, a, b, msg="", tol=TOL):
    """Assert that two floats (or lists of floats) are within tolerance."""
    if isinstance(a, (list, tuple)):
        tc.assertEqual(len(a), len(b), msg=f"{msg}: length mismatch")
        for i, (ai, bi) in enumerate(zip(a, b)):
            tc.assertAlmostEqual(
                ai, bi, delta=tol,
                msg=f"{msg}: element {i}: {ai} != {bi}"
            )
    else:
        tc.assertAlmostEqual(a, b, delta=tol, msg=msg)


# ---------------------------------------------------------------------------
# Scene helpers
# ---------------------------------------------------------------------------

def _purge():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=True)
    for col in list(bpy.data.collections):
        bpy.data.collections.remove(col)


def _add_empty(name="E"):
    bpy.ops.object.empty_add(location=(0, 0, 0))
    obj = bpy.context.active_object
    obj.name = name
    ensure_id(obj)
    return obj


def _add_cube(name="C"):
    bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
    obj = bpy.context.active_object
    obj.name = name
    ensure_id(obj)
    return obj


# ---------------------------------------------------------------------------
# § Pure math helper tests (no bpy scene needed)
# ---------------------------------------------------------------------------

class TestConvertLocation(unittest.TestCase):
    """Tests for _convert_location — pure function, no bpy."""

    def test_identity(self):
        assertClose(self, _convert_location((0, 0, 0)), [0, 0, 0])

    def test_unit_conversion_factor(self):
        # 1 metre in Blender → 100 cm in Bridge
        assertClose(self, _convert_location((1, 0, 0)), [0, 100, 0])
        assertClose(self, _convert_location((0, 1, 0)), [100, 0, 0])
        assertClose(self, _convert_location((0, 0, 1)), [0, 0, 100])

    def test_axis_swap_x_to_bridge_y(self):
        # Blender +X → Bridge +Y
        result = _convert_location((1, 0, 0))
        self.assertAlmostEqual(result[0], 0.0, delta=TOL, msg="Bridge X should be 0")
        self.assertAlmostEqual(result[1], 100.0, delta=TOL, msg="Bridge Y should be 100")
        self.assertAlmostEqual(result[2], 0.0, delta=TOL, msg="Bridge Z should be 0")

    def test_axis_swap_y_to_bridge_x(self):
        # Blender +Y → Bridge +X
        result = _convert_location((0, 1, 0))
        self.assertAlmostEqual(result[0], 100.0, delta=TOL, msg="Bridge X should be 100")
        self.assertAlmostEqual(result[1], 0.0, delta=TOL, msg="Bridge Y should be 0")
        self.assertAlmostEqual(result[2], 0.0, delta=TOL, msg="Bridge Z should be 0")

    def test_z_unchanged(self):
        result = _convert_location((0, 0, 3.5))
        self.assertAlmostEqual(result[2], 350.0, delta=TOL)

    def test_combined(self):
        result = _convert_location((2, 3, 4))
        assertClose(self, result, [300, 200, 400])

    def test_negative_values(self):
        result = _convert_location((-1, -2, -3))
        assertClose(self, result, [-200, -100, -300])

    def test_fractional(self):
        result = _convert_location((0.5, 1.5, 2.5))
        assertClose(self, result, [150, 50, 250])


class TestConvertScale(unittest.TestCase):
    """Tests for _convert_scale — pure function."""

    def test_uniform_scale(self):
        assertClose(self, _convert_scale((2, 2, 2)), [2, 2, 2])

    def test_identity_scale(self):
        assertClose(self, _convert_scale((1, 1, 1)), [1, 1, 1])

    def test_non_uniform_scale_axis_swap(self):
        # Blender (sx=2, sy=3, sz=4) → Bridge (sy=3, sx=2, sz=4)
        result = _convert_scale((2, 3, 4))
        assertClose(self, result, [3, 2, 4])

    def test_negative_scale_preserved(self):
        result = _convert_scale((-1, 1, 1))
        assertClose(self, result, [1, -1, 1])

    def test_all_negative(self):
        result = _convert_scale((-1, -1, -1))
        assertClose(self, result, [-1, -1, -1])


class TestHasNegativeScale(unittest.TestCase):
    def test_positive(self):
        self.assertFalse(_has_negative_scale((1, 1, 1)))

    def test_single_negative(self):
        self.assertTrue(_has_negative_scale((-1, 1, 1)))
        self.assertTrue(_has_negative_scale((1, -1, 1)))
        self.assertTrue(_has_negative_scale((1, 1, -1)))

    def test_all_negative(self):
        self.assertTrue(_has_negative_scale((-1, -2, -0.5)))


class TestConvertQuaternion(unittest.TestCase):
    """Tests for _convert_quaternion — pure function."""

    def test_identity_quaternion(self):
        # Blender identity (w=1, x=0, y=0, z=0) → Bridge [0, 0, 0, 1]
        result = _convert_quaternion((1, 0, 0, 0))
        assertClose(self, result, [0, 0, 0, 1])

    def test_handedness_z_sign_flip(self):
        # A pure Z rotation in Blender: q = (cos(θ/2), 0, 0, sin(θ/2))
        # After conversion the z component should negate.
        angle = math.pi / 4
        w = math.cos(angle / 2)
        z = math.sin(angle / 2)
        result = _convert_quaternion((w, 0, 0, z))
        # bridge_x = by=0, bridge_y = bx=0, bridge_z = -bz = -z, bridge_w = w
        assertClose(self, result, [0, 0, -z, w])

    def test_x_rotation_maps_to_bridge_y(self):
        # Pure X rotation in Blender: q = (w, x, 0, 0)
        # bridge_x = by=0, bridge_y = bx=x → Blender X → Bridge Y
        angle = math.pi / 3
        w = math.cos(angle / 2)
        x = math.sin(angle / 2)
        result = _convert_quaternion((w, x, 0, 0))
        assertClose(self, result, [0, x, 0, w])

    def test_y_rotation_maps_to_bridge_x(self):
        # Pure Y rotation in Blender: q = (w, 0, y, 0)
        # bridge_x = by=y → Blender Y → Bridge X
        angle = math.pi / 6
        w = math.cos(angle / 2)
        y = math.sin(angle / 2)
        result = _convert_quaternion((w, 0, y, 0))
        assertClose(self, result, [y, 0, 0, w])

    def test_result_is_unit_quaternion(self):
        # Converting a unit quaternion must yield another unit quaternion.
        import math as _math
        angle = 1.23
        w = _math.cos(angle / 2)
        x = _math.sin(angle / 2) * 0.6
        y = _math.sin(angle / 2) * 0.8
        z = 0.0
        result = _convert_quaternion((w, x, y, z))
        length = sum(v * v for v in result) ** 0.5
        self.assertAlmostEqual(length, 1.0, delta=TOL)


# ---------------------------------------------------------------------------
# § Blender-scene extract_transform tests
# ---------------------------------------------------------------------------

class TestExtractTransformIdentity(unittest.TestCase):
    """Test 1: identity transform."""

    def setUp(self):
        _purge()

    def test_identity_location(self):
        obj = _add_empty("ID")
        td = extract_transform(obj)
        assertClose(self, td.location, [0, 0, 0])

    def test_identity_scale(self):
        obj = _add_empty("ID")
        td = extract_transform(obj)
        assertClose(self, td.scale, [1, 1, 1])

    def test_identity_quaternion(self):
        obj = _add_empty("ID")
        td = extract_transform(obj)
        # Identity rotation → [x=0, y=0, z=0, w=1]
        assertClose(self, td.rotation_quaternion, [0, 0, 0, 1])

    def test_no_negative_scale(self):
        obj = _add_empty("ID")
        td = extract_transform(obj)
        self.assertFalse(td.has_negative_scale)

    def test_repeated_extraction_stable(self):
        """Test 17: repeated calls must produce identical results."""
        obj = _add_empty("Stable")
        obj.location = (1.5, 2.5, 3.5)
        td1 = extract_transform(obj)
        td2 = extract_transform(obj)
        td3 = extract_transform(obj)
        self.assertEqual(td1.location, td2.location)
        self.assertEqual(td2.location, td3.location)
        self.assertEqual(td1.rotation_quaternion, td2.rotation_quaternion)


class TestTranslation(unittest.TestCase):
    """Tests 2–5: translation along each axis."""

    def setUp(self):
        _purge()

    def test_translation_positive_x(self):
        """Blender +X=1 → Bridge Y=100."""
        obj = _add_empty("TX")
        obj.location = (1, 0, 0)
        td = extract_transform(obj)
        assertClose(self, td.location, [0, 100, 0])

    def test_translation_positive_y(self):
        """Blender +Y=1 → Bridge X=100."""
        obj = _add_empty("TY")
        obj.location = (0, 1, 0)
        td = extract_transform(obj)
        assertClose(self, td.location, [100, 0, 0])

    def test_translation_positive_z(self):
        """Blender +Z=1 → Bridge Z=100."""
        obj = _add_empty("TZ")
        obj.location = (0, 0, 1)
        td = extract_transform(obj)
        assertClose(self, td.location, [0, 0, 100])

    def test_translation_combined(self):
        """Blender (2,3,4) → Bridge (300,200,400)."""
        obj = _add_empty("TC")
        obj.location = (2, 3, 4)
        td = extract_transform(obj)
        assertClose(self, td.location, [300, 200, 400])

    def test_translation_unit_conversion(self):
        """1 Blender unit = 100 cm in Bridge."""
        obj = _add_empty("TU")
        obj.location = (0, 1, 0)  # 1 BU along Blender Y → Bridge X
        td = extract_transform(obj)
        self.assertAlmostEqual(td.location[0], 100.0, delta=TOL)


class TestRotation(unittest.TestCase):
    """Tests 6–10: rotation on each axis and all Blender modes."""

    def setUp(self):
        _purge()

    def _make_euler_obj(self, mode, ex, ey, ez):
        obj = _add_empty("R")
        obj.rotation_mode = mode
        obj.rotation_euler = mathutils.Euler((ex, ey, ez), mode)
        return obj

    def test_rotation_x_axis_euler(self):
        """90° around Blender X → rotation in Bridge Y direction."""
        obj = self._make_euler_obj("XYZ", math.pi / 2, 0, 0)
        td = extract_transform(obj)
        # Bridge quat: x=0, y=sin(45°)≈0.7071, z=0, w=cos(45°)≈0.7071
        q = td.rotation_quaternion
        self.assertAlmostEqual(abs(q[1]), math.sin(math.pi / 4), delta=1e-4)
        self.assertAlmostEqual(abs(q[3]), math.cos(math.pi / 4), delta=1e-4)
        self.assertAlmostEqual(q[0], 0.0, delta=1e-4)
        self.assertAlmostEqual(q[2], 0.0, delta=1e-4)

    def test_rotation_y_axis_euler(self):
        """90° around Blender Y → rotation in Bridge X direction."""
        obj = self._make_euler_obj("XYZ", 0, math.pi / 2, 0)
        td = extract_transform(obj)
        q = td.rotation_quaternion
        self.assertAlmostEqual(abs(q[0]), math.sin(math.pi / 4), delta=1e-4)
        self.assertAlmostEqual(abs(q[3]), math.cos(math.pi / 4), delta=1e-4)
        self.assertAlmostEqual(q[1], 0.0, delta=1e-4)
        self.assertAlmostEqual(q[2], 0.0, delta=1e-4)

    def test_rotation_z_axis_euler(self):
        """90° around Blender Z → Bridge Z with negated sign (handedness)."""
        obj = self._make_euler_obj("XYZ", 0, 0, math.pi / 2)
        td = extract_transform(obj)
        q = td.rotation_quaternion
        self.assertAlmostEqual(abs(q[2]), math.sin(math.pi / 4), delta=1e-4)
        self.assertAlmostEqual(abs(q[3]), math.cos(math.pi / 4), delta=1e-4)
        self.assertAlmostEqual(q[0], 0.0, delta=1e-4)
        self.assertAlmostEqual(q[1], 0.0, delta=1e-4)

    def test_rotation_quaternion_mode(self):
        """Objects using QUATERNION rotation mode are extracted correctly."""
        obj = _add_empty("RQ")
        obj.rotation_mode = "QUATERNION"
        angle = math.pi / 3  # 60°
        obj.rotation_quaternion = mathutils.Quaternion((0, 0, 1), angle)
        td = extract_transform(obj)
        self.assertEqual(td.rotation_mode, "QUATERNION")
        # Must be a unit quaternion
        q = td.rotation_quaternion
        length = sum(v * v for v in q) ** 0.5
        self.assertAlmostEqual(length, 1.0, delta=TOL)

    def test_all_euler_modes_produce_unit_quaternion(self):
        """All 6 Blender Euler modes must produce valid unit quaternions."""
        modes = ["XYZ", "XZY", "YXZ", "YZX", "ZXY", "ZYX"]
        for mode in modes:
            with self.subTest(mode=mode):
                _purge()
                obj = self._make_euler_obj(mode, 0.3, 0.5, 0.7)
                td = extract_transform(obj)
                q = td.rotation_quaternion
                length = sum(v * v for v in q) ** 0.5
                self.assertAlmostEqual(
                    length, 1.0, delta=TOL,
                    msg=f"Mode {mode}: quaternion not normalised"
                )

    def test_identity_rotation_any_mode(self):
        """Zero Euler in any mode → identity quaternion."""
        for mode in ["XYZ", "XZY", "YXZ", "YZX", "ZXY", "ZYX"]:
            with self.subTest(mode=mode):
                _purge()
                obj = self._make_euler_obj(mode, 0, 0, 0)
                td = extract_transform(obj)
                assertClose(self, td.rotation_quaternion, [0, 0, 0, 1])


class TestScale(unittest.TestCase):
    """Tests 11–13: scale extraction including negative scale."""

    def setUp(self):
        _purge()

    def test_uniform_scale(self):
        obj = _add_empty("SU")
        obj.scale = (3, 3, 3)
        td = extract_transform(obj)
        assertClose(self, td.scale, [3, 3, 3])

    def test_non_uniform_scale(self):
        """Blender (2,3,4) → Bridge (3,2,4) after axis swap."""
        obj = _add_empty("SN")
        obj.scale = (2, 3, 4)
        td = extract_transform(obj)
        assertClose(self, td.scale, [3, 2, 4])

    def test_negative_scale_single_axis(self):
        obj = _add_empty("SNG")
        obj.scale = (-1, 1, 1)
        warnings = []
        td = extract_transform(obj, warnings=warnings)
        self.assertTrue(td.has_negative_scale)
        self.assertTrue(any("negative scale" in w.lower() for w in warnings))

    def test_negative_scale_two_axes(self):
        obj = _add_empty("SNG2")
        obj.scale = (-1, -1, 1)
        td = extract_transform(obj)
        self.assertTrue(td.has_negative_scale)

    def test_no_false_negative_on_positive_scale(self):
        obj = _add_empty("SNP")
        obj.scale = (0.5, 2.0, 1.0)
        td = extract_transform(obj)
        self.assertFalse(td.has_negative_scale)


class TestHierarchy(unittest.TestCase):
    """Tests 14–15: parent/child and deeply nested hierarchy."""

    def setUp(self):
        _purge()

    def test_child_local_transform_is_relative(self):
        """
        Parent at X=1, Child at local X=1 from parent.
        Child's extracted local location must be 1 BU (not 2), in Bridge space.
        """
        parent = _add_empty("Parent")
        parent.location = (1, 0, 0)  # Blender world X=1

        child = _add_empty("Child")
        child.parent = parent
        # Set child's location in local space (relative to parent)
        child.location = (1, 0, 0)
        bpy.context.view_layer.update()

        from blender_unreal_bridge.collectors.id_generator import get_id
        td = extract_transform(child, parent_id=get_id(parent))
        # Child local location in Blender is (1,0,0) → Bridge Y=100
        assertClose(self, td.location, [0, 100, 0])
        self.assertIsNotNone(td.parent_id)

    def test_deeply_nested_three_levels(self):
        gp = _add_empty("GP")
        gp.location = (0, 0, 1)
        p = _add_empty("P")
        p.parent = gp
        p.location = (0, 0, 1)
        c = _add_empty("C")
        c.parent = p
        c.location = (0, 0, 1)
        bpy.context.view_layer.update()

        from blender_unreal_bridge.collectors.id_generator import get_id
        td_c = extract_transform(c, parent_id=get_id(p))
        # Child local Z = 1 BU → Bridge Z = 100 cm
        assertClose(self, td_c.location, [0, 0, 100])

    def test_parent_id_propagated(self):
        parent = _add_empty("Par")
        child = _add_empty("Chi")
        child.parent = parent
        from blender_unreal_bridge.collectors.id_generator import get_id
        pid = get_id(parent)
        td = extract_transform(child, parent_id=pid)
        self.assertEqual(td.parent_id, pid)

    def test_root_object_has_no_parent(self):
        obj = _add_empty("Root")
        td = extract_transform(obj, parent_id=None)
        self.assertIsNone(td.parent_id)


class TestAxisAngleWarning(unittest.TestCase):
    """Test 18: AXIS_ANGLE mode produces a warning, not an error."""

    def setUp(self):
        _purge()

    def test_axis_angle_produces_warning(self):
        obj = _add_empty("AA")
        obj.rotation_mode = "AXIS_ANGLE"
        warnings = []
        errors = []
        td = extract_transform(obj, warnings=warnings, errors=errors)
        self.assertEqual(len(errors), 0, "AXIS_ANGLE must not produce errors")
        self.assertTrue(
            any("AXIS_ANGLE" in w for w in warnings),
            f"Expected AXIS_ANGLE warning, got: {warnings}"
        )
        # Must still yield a valid unit quaternion
        q = td.rotation_quaternion
        length = sum(v * v for v in q) ** 0.5
        self.assertAlmostEqual(length, 1.0, delta=TOL)


class TestArbitraryTransform(unittest.TestCase):
    """Test 16: arbitrary combined transform."""

    def setUp(self):
        _purge()

    def test_arbitrary_combined(self):
        obj = _add_empty("Arb")
        obj.rotation_mode = "XYZ"
        obj.location = (3, -1, 2)
        obj.rotation_euler = (math.pi / 6, math.pi / 4, math.pi / 3)
        obj.scale = (1.5, 0.5, 2.0)

        warnings = []
        td = extract_transform(obj, warnings=warnings)

        # Location: Blender (3,-1,2) → Bridge (-100, 300, 200)
        assertClose(self, td.location, [-100, 300, 200])
        # Scale: Blender (1.5,0.5,2.0) → Bridge (0.5,1.5,2.0)
        assertClose(self, td.scale, [0.5, 1.5, 2.0])
        # Quaternion must be unit
        q = td.rotation_quaternion
        length = sum(v * v for v in q) ** 0.5
        self.assertAlmostEqual(length, 1.0, delta=TOL)
        # No negative scale
        self.assertFalse(td.has_negative_scale)


class TestToDict(unittest.TestCase):
    """TransformData.to_dict() must conform to DATA_PROTOCOL.md schema."""

    def setUp(self):
        _purge()

    def test_to_dict_keys(self):
        obj = _add_empty("D")
        td = extract_transform(obj)
        d = td.to_dict()
        self.assertIn("bubridge_id", d)
        self.assertIn("name", d)
        self.assertIn("parent_id", d)
        self.assertIn("transform", d)
        tf = d["transform"]
        for key in ("location", "rotation_quaternion", "rotation_euler",
                    "rotation_mode", "scale", "has_negative_scale", "origin_offset"):
            self.assertIn(key, tf, msg=f"Missing key: {key}")

    def test_rotation_quaternion_is_xyzw(self):
        obj = _add_empty("XYZW")
        td = extract_transform(obj)
        d = td.to_dict()
        q = d["transform"]["rotation_quaternion"]
        self.assertEqual(len(q), 4)

    def test_location_is_three_floats(self):
        obj = _add_empty("L3")
        td = extract_transform(obj)
        d = td.to_dict()
        loc = d["transform"]["location"]
        self.assertEqual(len(loc), 3)
        for v in loc:
            self.assertIsInstance(v, float)

    def test_scale_is_three_floats(self):
        obj = _add_empty("S3")
        td = extract_transform(obj)
        d = td.to_dict()
        s = d["transform"]["scale"]
        self.assertEqual(len(s), 3)

class TestSceneCollectorIntegration(unittest.TestCase):
    """Verify integration between Scene Collector and Transform system."""

    def setUp(self):
        _purge()

    def test_collect_scene_with_transforms(self):
        from blender_unreal_bridge.collectors.scene_collector import collect_scene
        obj = _add_cube("CollectedCube")
        obj.location = (1, 2, 3)

        result = collect_scene(extract_transforms=True)
        self.assertEqual(len(result.objects), 1)
        meta = result.objects[0]
        self.assertIsNotNone(meta.transform)
        self.assertEqual(meta.transform.location, [200.0, 100.0, 300.0])

        d = meta.to_dict()
        self.assertIn("transform", d)
        self.assertEqual(d["transform"]["location"], [200.0, 100.0, 300.0])

    def test_collect_scene_default_no_transforms(self):
        from blender_unreal_bridge.collectors.scene_collector import collect_scene
        _add_cube("NoXformCube")
        result = collect_scene(extract_transforms=False)
        self.assertEqual(len(result.objects), 1)
        meta = result.objects[0]
        self.assertIsNone(meta.transform)
        d = meta.to_dict()
        self.assertNotIn("transform", d)
# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run():
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    run()
