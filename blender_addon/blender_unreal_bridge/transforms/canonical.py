"""
transforms/canonical.py — Authoritative Blender-to-Bridge Transform Conversion
===============================================================================

This is the ONLY location where coordinate and unit conversions are performed.
Do not copy, replicate, or reimport these formulas elsewhere in the add-on.

Canonical Bridge Coordinate System (from DATA_PROTOCOL.md §3)
--------------------------------------------------------------
  Up Axis    : +Z
  Forward    : +X   (Blender source: +Y)
  Right      : +Y   (Blender source: +X)
  Handedness : Left-Handed
  Unit       : Centimeter (1 Blender Unit = 1 Metre = 100 cm)

Blender Coordinate System
--------------------------
  Up Axis    : +Z
  Forward    : +Y
  Right      : +X
  Handedness : Right-Handed
  Unit       : Metre (default)

Axis Conversion (location/translation)
---------------------------------------
  Canon_X =  Blender_Y * 100     (Blender forward → Bridge forward)
  Canon_Y =  Blender_X * 100     (Blender right   → Bridge right)
  Canon_Z =  Blender_Z * 100     (Up shared)

  Authority: DATA_PROTOCOL.md §3 table + ARCHITECTURE.md §4.2 first formula.
  The parenthetical "alternatively" in ARCHITECTURE.md is NOT used; it
  contradicts the axis table in DATA_PROTOCOL.md (it would keep Blender_X as
  X instead of remapping it to Y, breaking the Forward/Right mapping).

Rotation Conversion
--------------------
  Blender stores object rotation in one of several modes:
    QUATERNION  — preferred; stored as (w, x, y, z) in Blender's API
    XYZ/XZY/YXZ/YZX/ZXY/ZYX — Euler angle sets in radians
    AXIS_ANGLE  — (angle, axis_x, axis_y, axis_z)

  Strategy:
    1. Always evaluate the final rotation as a quaternion via
       obj.matrix_local decomposition (mathutils handles all mode conversions
       internally and avoids gimbal-lock concerns).
    2. Apply the same axis swap to the rotation quaternion as for locations.
    3. Store result as [x, y, z, w] in the Bridge representation.

  Quaternion axis-swap for handedness change (Right → Left handed, Y↔X swap):
    q_blender = (w,  x,  y,  z)
    q_bridge  = (w,  y,  x, -z)

  Derivation: The basis-change matrix M (Blender→Bridge) for locations is:
      | 0  1  0 |        Canon = M * Blender
      | 1  0  0 |
      | 0  0  1 |
  For a rotation quaternion q = (w, xi, yj, zk), applying basis M gives:
      q_bridge = conjugate(M_as_quat) * q_blender * M_as_quat
  After expansion this reduces to (w, y, x, -z).

  The sign flip on z encodes the handedness change from right- to left-handed.

Scale Conversion
-----------------
  Scale values are dimensionless ratios — no unit conversion needed.
  Axis labels change to match the new coordinate frame:
    Canon_ScaleX = Blender_ScaleY   (scale along Bridge forward = Blender forward)
    Canon_ScaleY = Blender_ScaleX   (scale along Bridge right   = Blender right)
    Canon_ScaleZ = Blender_ScaleZ   (scale along shared Up)

  Negative scale is permitted and faithfully preserved. Negative scale on any
  axis indicates a reflection. The IMPORTER is responsible for inverting polygon
  winding order when negative scale is detected (flagged via has_negative_scale).

Rotation storage in the Bridge representation
---------------------------------------------
  The Bridge always stores:
    rotation_quaternion : [x, y, z, w]  — canonical Bridge-space quaternion
    rotation_euler      : [pitch, yaw, roll] in degrees, XYZ order
                          (converted from the canonical quaternion — for
                           human-readability only; the quaternion is authoritative)
    rotation_mode       : original Blender rotation mode string (informational)

World vs. Local Transforms
---------------------------
  The Bridge stores LOCAL transforms (relative to the parent object) in
  Bridge canonical space. This matches DATA_PROTOCOL.md objects.json schema
  which shows a flat "transform" block without a separate world_transform key.

  ARCHITECTURE.md §2.1 says "Extract world and local matrices" but
  DATA_PROTOCOL.md (authoritative schema) uses only local transforms.
  We store both internally in TransformData for completeness, but only
  the local canonical transform is serialised into the Bridge package.
"""

import math
from mathutils import Matrix, Quaternion, Vector, Euler


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

METRES_TO_CM: float = 100.0

# ---------------------------------------------------------------------------
# Public data structure
# ---------------------------------------------------------------------------

class TransformData:
    """
    The canonical Bridge-space transform for one Blender object.

    All numeric values are already in Bridge canonical space:
      - location in centimetres
      - rotation as unit quaternion [x, y, z, w]
      - scale as dimensionless ratio (axis-swapped to Bridge frame)
      - rotation_mode is the original Blender mode string (informational)

    Attributes
    ----------
    bubridge_id : str
    name : str
    parent_id : str | None
    location : list[float]         [x, y, z] in cm, Bridge canonical
    rotation_quaternion : list[float] [x, y, z, w] Bridge canonical
    rotation_euler_deg : list[float]  [pitch°, yaw°, roll°] XYZ, Bridge canon
    rotation_mode : str            original Blender rotation mode
    scale : list[float]            [sx, sy, sz] Bridge canonical
    has_negative_scale : bool      True if any scale component < 0
    """

    __slots__ = (
        "bubridge_id",
        "name",
        "parent_id",
        "location",
        "rotation_quaternion",
        "rotation_euler_deg",
        "rotation_mode",
        "scale",
        "has_negative_scale",
    )

    def __init__(
        self,
        bubridge_id: str,
        name: str,
        parent_id,
        location: list,
        rotation_quaternion: list,
        rotation_euler_deg: list,
        rotation_mode: str,
        scale: list,
        has_negative_scale: bool,
    ):
        self.bubridge_id = bubridge_id
        self.name = name
        self.parent_id = parent_id
        self.location = location
        self.rotation_quaternion = rotation_quaternion
        self.rotation_euler_deg = rotation_euler_deg
        self.rotation_mode = rotation_mode
        self.scale = scale
        self.has_negative_scale = has_negative_scale

    def to_dict(self) -> dict:
        """Serialise to the DATA_PROTOCOL.md transform schema."""
        return {
            "bubridge_id": self.bubridge_id,
            "name": self.name,
            "parent_id": self.parent_id,
            "transform": {
                "location": self.location,
                "rotation_quaternion": self.rotation_quaternion,
                "rotation_euler": self.rotation_euler_deg,
                "rotation_mode": self.rotation_mode,
                "scale": self.scale,
                "has_negative_scale": self.has_negative_scale,
                "origin_offset": [0.0, 0.0, 0.0],
            },
        }


# ---------------------------------------------------------------------------
# Low-level math helpers (pure functions, no bpy dependency)
# ---------------------------------------------------------------------------

def _convert_location(blender_xyz: tuple) -> list:
    """
    Convert a Blender-space location (x, y, z) in metres to Bridge canonical
    space in centimetres.

    Canon_X =  Blender_Y * 100
    Canon_Y =  Blender_X * 100
    Canon_Z =  Blender_Z * 100

    Args:
        blender_xyz: A 3-tuple of floats (Blender x, y, z) in metres.

    Returns:
        [canon_x, canon_y, canon_z] in centimetres.
    """
    bx, by, bz = blender_xyz
    return [by * METRES_TO_CM, bx * METRES_TO_CM, bz * METRES_TO_CM]


def _convert_quaternion(blender_wxyz: tuple) -> list:
    """
    Convert a Blender-space quaternion (w, x, y, z) to Bridge canonical
    left-handed space.

    Blender quaternion : (w,  x,  y,  z)
    Bridge quaternion  : (y,  x, -z,  w)  stored as [x, y, z, w]
    i.e. bridge stored = [y_bl, x_bl, -z_bl, w_bl]

    Derivation: applying the axis-swap basis change M = [[0,1,0],[1,0,0],[0,0,1]]
    to the rotation quaternion gives:
        w' =  w
        x' =  y   (bridge X ← blender Y axis)
        y' =  x   (bridge Y ← blender X axis)
        z' = -z   (handedness flip)

    Args:
        blender_wxyz: 4-tuple (w, x, y, z) from Blender (mathutils convention).

    Returns:
        [x, y, z, w] in Bridge convention (DATA_PROTOCOL.md stores xyzw).
    """
    w, bx, by, bz = blender_wxyz
    bridge_x = by
    bridge_y = bx
    bridge_z = -bz
    bridge_w = w
    return [bridge_x, bridge_y, bridge_z, bridge_w]


def _convert_scale(blender_sxyz: tuple) -> list:
    """
    Convert a Blender-space scale (sx, sy, sz) to Bridge canonical space
    by applying the same axis swap as for locations (no unit factor for scale).

    Canon_SX = Blender_SY
    Canon_SY = Blender_SX
    Canon_SZ = Blender_SZ

    Args:
        blender_sxyz: 3-tuple (sx, sy, sz).

    Returns:
        [canon_sx, canon_sy, canon_sz].
    """
    sx, sy, sz = blender_sxyz
    return [sy, sx, sz]


def _quat_to_euler_deg_xyz(xyzw: list) -> list:
    """
    Convert a Bridge-canonical quaternion [x, y, z, w] to Euler angles
    in degrees with XYZ intrinsic order.

    This is stored for human-readability only — the quaternion is authoritative.

    Args:
        xyzw: 4-element list [x, y, z, w] in Bridge space.

    Returns:
        [pitch_deg, yaw_deg, roll_deg] in degrees.
    """
    x, y, z, w = xyzw
    q = Quaternion((w, x, y, z))
    e = q.to_euler("XYZ")
    return [math.degrees(e.x), math.degrees(e.y), math.degrees(e.z)]


def _has_negative_scale(scale_xyz: tuple) -> bool:
    """Return True if any component of the scale 3-tuple is negative."""
    return any(s < 0.0 for s in scale_xyz)


# ---------------------------------------------------------------------------
# Object-level extraction (requires bpy)
# ---------------------------------------------------------------------------

def _extract_raw_local_transform(obj):
    """
    Extract raw local translation (in meters), local rotation (as mathutils.Quaternion (w,x,y,z)),
    and local scale from a Blender object.

    Handles:
      - Direct TRS channels for root or un-offset objects (preserving exact precision and negative scale)
      - matrix_local decomposition when parent inverse is present (e.g. parented with keep_transform)
      - All rotation modes: QUATERNION, AXIS_ANGLE, XYZ, XZY, YXZ, YZX, ZXY, ZYX
    """
    has_parent_offset = obj.parent is not None and not obj.matrix_parent_inverse.is_identity

    if not has_parent_offset:
        loc = obj.location.copy()
        scale = obj.scale.copy()
        mode = obj.rotation_mode

        if mode == "QUATERNION":
            rot_q = obj.rotation_quaternion.normalized()
        elif mode == "AXIS_ANGLE":
            axis = Vector((obj.rotation_axis_angle[1], obj.rotation_axis_angle[2], obj.rotation_axis_angle[3]))
            if axis.length_squared > 0:
                rot_q = Quaternion(axis, obj.rotation_axis_angle[0])
            else:
                rot_q = Quaternion((1.0, 0.0, 0.0, 0.0))
        else:
            rot_q = obj.rotation_euler.to_quaternion()

        return loc, rot_q, scale
    else:
        if bpy.context and hasattr(bpy.context, "view_layer") and bpy.context.view_layer:
            bpy.context.view_layer.update()
        loc, rot_q, scale = obj.matrix_local.decompose()
        if any(s < 0 for s in obj.scale):
            scale = Vector((
                -abs(scale.x) if obj.scale.x < 0 else abs(scale.x),
                -abs(scale.y) if obj.scale.y < 0 else abs(scale.y),
                -abs(scale.z) if obj.scale.z < 0 else abs(scale.z),
            ))
        return loc, rot_q, scale


def extract_transform(obj, parent_id=None, warnings=None, errors=None) -> TransformData:
    """
    Extract the local transform of a Blender object and convert it to
    Bridge canonical space.

    Args:
        obj       : bpy.types.Object
        parent_id : str | None — Bridge ID of the parent object.
        warnings  : list to append warning strings to (may be None).
        errors    : list to append error strings to (may be None).

    Returns:
        TransformData in Bridge canonical space.
    """
    if warnings is None:
        warnings = []
    if errors is None:
        errors = []

    # Retrieve the Bridge ID (must already exist — scene_collector assigns it).
    from ..collectors.id_generator import get_id
    bubridge_id = get_id(obj)
    if bubridge_id is None:
        errors.append(
            f"[ERROR] XFORM: Object '{obj.name}' has no bubridge_id. "
            f"Run scene collection before transform extraction."
        )
        bubridge_id = "obj_MISSING"

    # -- Extract raw local transform -------------------------------------
    loc, rot_q, scale = _extract_raw_local_transform(obj)

    # -- Warn on AXIS_ANGLE mode -----------------------------------------
    if obj.rotation_mode == "AXIS_ANGLE":
        warnings.append(
            f"[WARNING] XFORM: Object '{obj.name}' uses AXIS_ANGLE rotation mode. "
            f"The Bridge converts it to a quaternion via axis-angle conversion. "
            f"Verify the result if the object has unusual gimbal configurations."
        )

    # -- Convert to Bridge canonical space --------------------------------
    bridge_loc = _convert_location((loc.x, loc.y, loc.z))
    bridge_quat = _convert_quaternion((rot_q.w, rot_q.x, rot_q.y, rot_q.z))
    bridge_scale = _convert_scale((scale.x, scale.y, scale.z))
    neg_scale = _has_negative_scale((scale.x, scale.y, scale.z))

    if neg_scale:
        warnings.append(
            f"[WARNING] XFORM: Object '{obj.name}' has negative scale "
            f"({scale.x:.4f}, {scale.y:.4f}, {scale.z:.4f}). "
            f"Polygon winding must be inverted on import. "
            f"'has_negative_scale' flag is set in the transform data."
        )

    bridge_euler = _quat_to_euler_deg_xyz(bridge_quat)

    return TransformData(
        bubridge_id=bubridge_id,
        name=obj.name,
        parent_id=parent_id,
        location=bridge_loc,
        rotation_quaternion=bridge_quat,
        rotation_euler_deg=bridge_euler,
        rotation_mode=obj.rotation_mode,
        scale=bridge_scale,
        has_negative_scale=neg_scale,
    )
