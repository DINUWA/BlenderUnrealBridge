"""
bubridge_id Generator
---------------------
Single authoritative module responsible for generating and assigning stable
Bridge IDs to Blender objects.

Rules enforced here:
  - IDs are stored as Blender custom properties under the key BUBRIDGE_ID_KEY.
  - Once assigned, an ID must never be changed unless explicitly requested.
  - Object names are never used as unique identifiers.
  - ID format: "obj_<8 lowercase hex characters>"

This module must remain the ONLY location where bubridge_id values are
created or assigned. Never generate IDs elsewhere.
"""

import uuid

# The single canonical custom property key used across the entire add-on.
BUBRIDGE_ID_KEY = "bubridge_id"


def _generate_id() -> str:
    """Generate a new unique Bridge ID string in the format 'obj_XXXXXXXX'."""
    return "obj_" + uuid.uuid4().hex[:8]


def ensure_id(obj) -> str:
    """
    Return the existing bubridge_id for a Blender object, or generate and
    assign a new one if none exists.

    This function is idempotent: calling it multiple times on the same object
    will always return the same ID as long as the object retains its custom
    property (i.e. the Blender file has been saved).

    Args:
        obj: A bpy.types.Object instance.

    Returns:
        The stable string Bridge ID for this object.
    """
    existing = obj.get(BUBRIDGE_ID_KEY)
    if existing:
        return str(existing)

    new_id = _generate_id()
    obj[BUBRIDGE_ID_KEY] = new_id
    return new_id


def get_id(obj) -> str | None:
    """
    Return the existing bubridge_id for a Blender object without creating one.

    Args:
        obj: A bpy.types.Object instance.

    Returns:
        The existing ID string, or None if the object has no bubridge_id.
    """
    value = obj.get(BUBRIDGE_ID_KEY)
    return str(value) if value is not None else None


def has_id(obj) -> bool:
    """
    Return True if the object already has a bubridge_id assigned.

    Args:
        obj: A bpy.types.Object instance.

    Returns:
        True if the object has a bubridge_id custom property.
    """
    return BUBRIDGE_ID_KEY in obj


def _generate_mesh_id() -> str:
    """Generate a new unique Bridge Mesh ID string in the format 'mesh_XXXXXXXX'."""
    return "mesh_" + uuid.uuid4().hex[:8]


def ensure_mesh_id(mesh) -> str:
    """
    Return the existing bubridge_id for a Blender Mesh datablock, or generate and
    assign a new one if none exists.

    Args:
        mesh: A bpy.types.Mesh instance.

    Returns:
        The stable string Bridge Mesh ID for this mesh datablock.
    """
    existing = mesh.get(BUBRIDGE_ID_KEY)
    if existing:
        return str(existing)

    new_id = _generate_mesh_id()
    mesh[BUBRIDGE_ID_KEY] = new_id
    return new_id


def get_mesh_id(mesh) -> str | None:
    """
    Return the existing bubridge_id for a Blender Mesh datablock without creating one.

    Args:
        mesh: A bpy.types.Mesh instance.

    Returns:
        The existing Mesh ID string, or None if the mesh has no bubridge_id.
    """
    value = mesh.get(BUBRIDGE_ID_KEY)
    return str(value) if value is not None else None


def _generate_material_id() -> str:
    """Generate a new unique Bridge Material ID string in the format 'mat_XXXXXXXX'."""
    return "mat_" + uuid.uuid4().hex[:8]


def ensure_material_id(material) -> str:
    """
    Return the existing bubridge_id for a Blender Material datablock, or generate and
    assign a new one if none exists.

    Args:
        material: A bpy.types.Material instance.

    Returns:
        The stable string Bridge Material ID for this material datablock.
    """
    existing = material.get(BUBRIDGE_ID_KEY)
    if existing:
        return str(existing)

    new_id = _generate_material_id()
    material[BUBRIDGE_ID_KEY] = new_id
    return new_id


def get_material_id(material) -> str | None:
    """
    Return the existing bubridge_id for a Blender Material datablock without creating one.

    Args:
        material: A bpy.types.Material instance.

    Returns:
        The existing Material ID string, or None if the material has no bubridge_id.
    """
    value = material.get(BUBRIDGE_ID_KEY)
    return str(value) if value is not None else None


def has_material_id(material) -> bool:
    """
    Return True if the material already has a bubridge_id assigned.

    Args:
        material: A bpy.types.Material instance.

    Returns:
        True if the material has a bubridge_id custom property.
    """
    return BUBRIDGE_ID_KEY in material


def _generate_texture_id() -> str:
    """Generate a new unique Bridge Texture ID string in the format 'tex_XXXXXXXX'."""
    return "tex_" + uuid.uuid4().hex[:8]


def ensure_texture_id(image) -> str:
    """
    Return the existing bubridge_id for a Blender Image datablock, or generate and
    assign a new one if none exists.

    Args:
        image: A bpy.types.Image instance.

    Returns:
        The stable string Bridge Texture ID for this image datablock.
    """
    existing = image.get(BUBRIDGE_ID_KEY)
    if existing:
        return str(existing)

    new_id = _generate_texture_id()
    image[BUBRIDGE_ID_KEY] = new_id
    return new_id


def get_texture_id(image) -> str | None:
    """
    Return the existing bubridge_id for a Blender Image datablock without creating one.

    Args:
        image: A bpy.types.Image instance.

    Returns:
        The existing Texture ID string, or None if the image has no bubridge_id.
    """
    value = image.get(BUBRIDGE_ID_KEY)
    return str(value) if value is not None else None


def has_texture_id(image) -> bool:
    """
    Return True if the image already has a bubridge_id assigned.

    Args:
        image: A bpy.types.Image instance.

    Returns:
        True if the image has a bubridge_id custom property.
    """
    return BUBRIDGE_ID_KEY in image


# ---------------------------------------------------------------------------
# Skeletons, Bones, and Animations (Milestone 9)
# ---------------------------------------------------------------------------

def _generate_skeleton_id() -> str:
    """Generate a new unique Bridge Skeleton ID string in the format 'skel_XXXXXXXX'."""
    return "skel_" + uuid.uuid4().hex[:8]


def ensure_skeleton_id(armature) -> str:
    """
    Return the existing bubridge skeleton ID for a Blender Armature datablock or object,
    or generate and assign a new one if none exists.
    """
    data = getattr(armature, "data", armature)
    existing = data.get("bubridge_skeleton_id") or data.get(BUBRIDGE_ID_KEY)
    if existing and str(existing).startswith("skel_"):
        return str(existing)

    new_id = _generate_skeleton_id()
    data["bubridge_skeleton_id"] = new_id
    return new_id


def get_skeleton_id(armature) -> str | None:
    data = getattr(armature, "data", armature)
    val = data.get("bubridge_skeleton_id") or data.get(BUBRIDGE_ID_KEY)
    if val and str(val).startswith("skel_"):
        return str(val)
    return None


def _generate_bone_id() -> str:
    """Generate a new unique Bridge Bone ID string in the format 'bone_XXXXXXXX'."""
    return "bone_" + uuid.uuid4().hex[:8]


def ensure_bone_id(bone) -> str:
    """
    Return the existing bubridge bone ID for a Blender Bone, EditBone, or PoseBone,
    or generate and assign a new one if none exists.
    """
    target = getattr(bone, "bone", bone)
    existing = target.get("bubridge_bone_id") or target.get(BUBRIDGE_ID_KEY)
    if existing and str(existing).startswith("bone_"):
        return str(existing)

    new_id = _generate_bone_id()
    target["bubridge_bone_id"] = new_id
    return new_id


def get_bone_id(bone) -> str | None:
    target = getattr(bone, "bone", bone)
    val = target.get("bubridge_bone_id") or target.get(BUBRIDGE_ID_KEY)
    if val and str(val).startswith("bone_"):
        return str(val)
    return None


def _generate_animation_id() -> str:
    """Generate a new unique Bridge Animation ID string in the format 'anim_XXXXXXXX'."""
    return "anim_" + uuid.uuid4().hex[:8]


def ensure_animation_id(action) -> str:
    """
    Return the existing bubridge animation ID for a Blender Action,
    or generate and assign a new one if none exists.
    """
    existing = action.get("bubridge_animation_id") or action.get(BUBRIDGE_ID_KEY)
    if existing and str(existing).startswith("anim_"):
        return str(existing)

    new_id = _generate_animation_id()
    action["bubridge_animation_id"] = new_id
    return new_id


def get_animation_id(action) -> str | None:
    val = action.get("bubridge_animation_id") or action.get(BUBRIDGE_ID_KEY)
    if val and str(val).startswith("anim_"):
        return str(val)
    return None



