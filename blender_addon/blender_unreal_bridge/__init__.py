bl_info = {
    "name": "Blender Unreal Bridge",
    "author": "Blender Unreal Bridge Contributors",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > Blender Unreal Bridge",
    "description": "Bridge pipeline to transfer 3D scenes from Blender to Unreal Engine.",
    "warning": "",
    "doc_url": "",
    "category": "Import-Export",
}

import bpy
from .version import VERSION_STRING, FORMAT_NAME
from .collectors.scene_collector import collect_scene
from .serialization.package_writer import create_bridge_package


class BUBRIDGE_OT_check_status(bpy.types.Operator):
    """Check the status of the Blender Unreal Bridge add-on."""
    bl_idname = "bubridge.check_status"
    bl_label = "Check Status"
    bl_description = "Displays the current status of the Blender Unreal Bridge add-on"
    bl_options = {"REGISTER"}

    def execute(self, context):
        message = f"{FORMAT_NAME} Add-on v{VERSION_STRING} is active."
        self.report({"INFO"}, message)
        return {"FINISHED"}


class BUBRIDGE_OT_collect_scene(bpy.types.Operator):
    """Inspect the current Blender scene and collect object metadata."""
    bl_idname = "bubridge.collect_scene"
    bl_label = "Collect Scene"
    bl_description = (
        "Traverses the active scene, assigns stable Bridge IDs to all supported "
        "objects, and reports a summary of collected metadata"
    )
    bl_options = {"REGISTER"}

    def execute(self, context):
        result = collect_scene(context.scene)
        object_count = len(result.objects)
        self.report(
            {"INFO"},
            f"[BUBRIDGE] Scene '{result.scene_name}': {object_count} object(s) collected. "
            f"{len(result.warnings)} warning(s), {len(result.errors)} error(s).",
        )
        for msg in result.warnings:
            self.report({"WARNING"}, msg)
        for msg in result.errors:
            self.report({"ERROR"}, msg)
        return {"FINISHED"}


class BUBRIDGE_OT_export_package(bpy.types.Operator):
    """Export the current Blender scene to a .bubridge package."""
    bl_idname = "bubridge.export_package"
    bl_label = "Export Package"
    bl_description = (
        "Collects scene data and canonical transforms, validates the metadata, "
        "and generates a .bubridge package"
    )
    bl_options = {"REGISTER"}

    def execute(self, context):
        try:
            pkg_path = create_bridge_package(context.scene)
            self.report({"INFO"}, f"[BUBRIDGE] Package created: {pkg_path.name}")
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, f"[BUBRIDGE] Export failed: {exc}")
            return {"CANCELLED"}


class BUBRIDGE_PT_main_panel(bpy.types.Panel):
    """Main Sidebar Panel for Blender Unreal Bridge."""
    bl_label = "Blender ↔ Unreal Bridge"
    bl_idname = "BUBRIDGE_PT_main_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Blender Unreal Bridge"

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.label(text=f"Bridge Version: {VERSION_STRING}")
        col.label(text=f"Format: {FORMAT_NAME}")
        col.separator()
        col.operator("bubridge.check_status", icon="CHECKMARK")
        col.separator()
        col.label(text="Scene Inspection:", icon="SCENE_DATA")
        col.operator("bubridge.collect_scene", icon="VIEWZOOM")
        col.separator()
        col.label(text="Package Export:", icon="EXPORT")
        col.operator("bubridge.export_package", icon="PACKAGE")


classes = (
    BUBRIDGE_OT_check_status,
    BUBRIDGE_OT_collect_scene,
    BUBRIDGE_OT_export_package,
    BUBRIDGE_PT_main_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
