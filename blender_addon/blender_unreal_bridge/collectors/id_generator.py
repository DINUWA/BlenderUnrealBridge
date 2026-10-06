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

