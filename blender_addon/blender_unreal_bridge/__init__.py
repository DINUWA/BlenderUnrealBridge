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
        col.separator()
        col.label(text="Live Sync:", icon="LINKED")

        from .live_sync.session import get_session
        session = get_session()
        if session is not None and session.is_connected:
            col.label(text=f"\u25cf Connected (session: {session.session_id})", icon="CHECKMARK")
            col.operator("bubridge.live_disconnect", icon="UNLINKED")
        else:
            col.label(text="\u25cb Disconnected", icon="X")
            col.operator("bubridge.live_connect", icon="LINKED")


class BUBRIDGE_OT_live_connect(bpy.types.Operator):
    """Connect to Unreal Engine for live synchronisation."""
    bl_idname = "bubridge.live_connect"
    bl_label = "Connect to Unreal"
    bl_description = (
        "Establish a live-sync connection to Unreal Engine on localhost:27284. "
        "Unreal must be running with the BlenderUnrealBridge plugin and the "
        "live-sync server started."
    )
    bl_options = {"REGISTER"}

    def execute(self, context):
        from .live_sync.session import ensure_session
        from .live_sync.change_detector import register_handler, prime_transform_cache
        from .live_sync.protocol import DEFAULT_HOST, DEFAULT_PORT

        session = ensure_session(DEFAULT_HOST, DEFAULT_PORT, VERSION_STRING)
        ok, msg = session.connect()
        if ok:
            prime_transform_cache(context.scene)
            register_handler()
            self.report({"INFO"}, msg)
        else:
            self.report({"WARNING"}, msg)
        return {"FINISHED"}


class BUBRIDGE_OT_live_disconnect(bpy.types.Operator):
    """Disconnect the live synchronisation session."""
    bl_idname = "bubridge.live_disconnect"
    bl_label = "Disconnect"
    bl_description = "Close the live-sync connection to Unreal Engine"
    bl_options = {"REGISTER"}

    def execute(self, context):
        from .live_sync.session import get_session, clear_session
        from .live_sync.change_detector import unregister_handler, clear_transform_cache

        session = get_session()
        if session is not None and session.is_connected:
            unregister_handler()
            clear_transform_cache()
            clear_session()
            self.report({"INFO"}, "[BUBRIDGE] Live-sync disconnected.")
        else:
            self.report({"INFO"}, "[BUBRIDGE] No active live-sync session.")
        return {"FINISHED"}


classes = (
    BUBRIDGE_OT_check_status,
    BUBRIDGE_OT_collect_scene,
    BUBRIDGE_OT_export_package,
    BUBRIDGE_OT_live_connect,
    BUBRIDGE_OT_live_disconnect,
    BUBRIDGE_PT_main_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    # Ensure live-sync is cleaned up on unregister
    try:
        from .live_sync.session import get_session, clear_session
        from .live_sync.change_detector import unregister_handler, clear_transform_cache
        session = get_session()
        if session is not None and session.is_connected:
            unregister_handler()
            clear_transform_cache()
            clear_session()
    except Exception:
        pass

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
