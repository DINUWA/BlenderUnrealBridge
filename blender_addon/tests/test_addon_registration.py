"""
Blender Add-on Registration Test

NOTE: This test is designed specifically to run inside Blender's embedded
Python runtime:
    blender --background --python blender_addon/tests/test_addon_registration.py

The host operating system's Python installation must NOT be assumed to be the
Blender runtime and must NOT be used to execute Blender add-on tests.
"""

import sys
import unittest

try:
    import bpy
except ImportError as exc:
    sys.stderr.write(
        "\n[ERROR] 'bpy' module not found.\n"
        "This test must be executed using Blender's embedded Python runtime via:\n"
        "  blender --background --python blender_addon/tests/test_addon_registration.py\n\n"
    )
    sys.exit(1)

# Ensure the addon directory is in sys.path
from pathlib import Path
addon_parent = Path(__file__).resolve().parent.parent
if str(addon_parent) not in sys.path:
    sys.path.insert(0, str(addon_parent))

import blender_unreal_bridge


class TestAddonRegistration(unittest.TestCase):
    """Verifies that the Blender Unreal Bridge add-on registers and unregisters cleanly."""

    def test_bl_info(self):
        """Verify bl_info metadata matches specification."""
        self.assertIn("name", blender_unreal_bridge.bl_info)
        self.assertEqual(blender_unreal_bridge.bl_info["name"], "Blender Unreal Bridge")
        self.assertEqual(blender_unreal_bridge.bl_info["version"], (0, 1, 0))
        self.assertEqual(blender_unreal_bridge.bl_info["category"], "Import-Export")

    def test_registration_lifecycle(self):
        """Verify that register() and unregister() lifecycle succeeds without leaking types."""
        # Clean state
        try:
            blender_unreal_bridge.unregister()
        except RuntimeError:
            pass  # Was not registered

        # Register
        blender_unreal_bridge.register()
        self.assertTrue(hasattr(bpy.types, "BUBRIDGE_OT_check_status"))
        self.assertTrue(hasattr(bpy.types, "BUBRIDGE_PT_main_panel"))

        # Unregister
        blender_unreal_bridge.unregister()
        self.assertFalse(hasattr(bpy.types, "BUBRIDGE_OT_check_status"))
        self.assertFalse(hasattr(bpy.types, "BUBRIDGE_PT_main_panel"))


def run():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestAddonRegistration)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    run()
