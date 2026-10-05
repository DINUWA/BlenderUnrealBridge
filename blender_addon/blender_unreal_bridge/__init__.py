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


classes = (
    BUBRIDGE_OT_check_status,
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
