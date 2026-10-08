"""
live_sync/change_detector.py — Blender Transform Change Detector (Milestone 10)
================================================================================

Monitors the active Blender scene for supported object transform changes and
dispatches live-sync updates via the active session.

Design
------
* Uses `bpy.app.handlers.depsgraph_update_post` to receive depsgraph
  notifications after Blender resolves changes.
* Maintains a cache of the last transmitted canonical transform per object_id.
* Sends an OBJECT_TRANSFORM_UPDATE only when the new canonical transform
  differs meaningfully from the cached value (epsilon guard prevents
  flooding on floating-point noise).
* Guard flag prevents recursive handler calls from a send triggering
  another depsgraph update.
* The handler is registered when the session connects and unregistered when
  it disconnects.
* All Blender API calls happen on the main thread (inside the handler).
* The handler never blocks; failed sends transition the session to
  DISCONNECTED but do not raise.

Epsilon
-------
Transform changes smaller than LOCATION_EPSILON_CM (0.001 cm = 0.01 mm) and
ROTATION_EPSILON / SCALE_EPSILON are considered unchanged and are NOT sent.
This prevents flooding on floating-point noise.
"""

import math
import bpy

from ..collectors.id_generator import get_id
from ..transforms.canonical import extract_transform
from .session import get_session

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LOCATION_EPSILON_CM: float = 0.001   # 0.01 mm
ROTATION_EPSILON: float = 1e-5       # ~0.001 degree
SCALE_EPSILON: float = 1e-5

# ---------------------------------------------------------------------------
# Module state
# ---------------------------------------------------------------------------

# Cache: object_id -> {"location": [...], "rotation": [...], "scale": [...]}
_last_sent: dict = {}

# Re-entry guard: prevents the send itself from triggering another handler call.
_in_handler: bool = False


# ---------------------------------------------------------------------------
# Change detection helpers
# ---------------------------------------------------------------------------

def _vectors_close(a: list, b: list, epsilon: float) -> bool:
    """Return True if all elements of a and b are within epsilon of each other."""
    return all(math.fabs(ai - bi) < epsilon for ai, bi in zip(a, b))


def _transform_unchanged(cached: dict, loc: list, rot: list, scale: list) -> bool:
    """Return True if the transform is effectively the same as the cached value."""
    if not _vectors_close(cached["location"], loc, LOCATION_EPSILON_CM):
        return False
    if not _vectors_close(cached["rotation"], rot, ROTATION_EPSILON):
        return False
    if not _vectors_close(cached["scale"], scale, SCALE_EPSILON):
        return False
    return True


# ---------------------------------------------------------------------------
# Depsgraph handler
# ---------------------------------------------------------------------------

def _on_depsgraph_update(scene, depsgraph):
    """
    Depsgraph post-update handler.

    Called by Blender after every depsgraph evaluation.  Inspects updated
    objects, computes their canonical transforms, compares with the last-sent
    cache, and sends OBJECT_TRANSFORM_UPDATE messages for changed objects.
    """
    global _in_handler
    if _in_handler:
        return

    session = get_session()
    if session is None or not session.is_connected:
        return

    # Only inspect object updates in this depsgraph evaluation.
    updated_object_ids = set()
    for update in depsgraph.updates:
        if isinstance(update.id, bpy.types.Object):
            obj = update.id
            if update.is_updated_transform:
                obj_id = get_id(obj)
                if obj_id:
                    updated_object_ids.add((obj_id, obj))

    if not updated_object_ids:
        return

    _in_handler = True
    try:
        for obj_id, obj in updated_object_ids:
            _maybe_send_transform(session, obj_id, obj)
    finally:
        _in_handler = False


def _maybe_send_transform(session, obj_id: str, obj) -> None:
    """
    Extract the canonical transform for obj and send it if changed.

    Args:
        session: The active LiveSyncSession.
        obj_id:  Stable bubridge_id.
        obj:     bpy.types.Object.
    """
    try:
        parent_id = get_id(obj.parent) if obj.parent else None
        td = extract_transform(obj, parent_id=parent_id)
    except Exception as exc:
        # Never let extraction errors crash Blender.
        import logging
        logging.getLogger(__name__).warning(
            "[LIVE-SYNC] Could not extract transform for %s: %s", obj_id, exc
        )
        return

    loc = td.location
    rot = td.rotation_quaternion
    scale = td.scale
    neg_scale = td.has_negative_scale

    # Compare with cached value
    cached = _last_sent.get(obj_id)
    if cached and _transform_unchanged(cached, loc, rot, scale):
        return  # No meaningful change — skip

    # Send the update
    ok, _msg = session.send_transform_update(obj_id, loc, rot, scale, neg_scale)
    if ok:
        # Update cache
        _last_sent[obj_id] = {
            "location": list(loc),
            "rotation": list(rot),
            "scale": list(scale),
        }


# ---------------------------------------------------------------------------
# Registration / unregistration
# ---------------------------------------------------------------------------

def register_handler() -> None:
    """
    Register the depsgraph update handler.

    Safe to call multiple times — guards against double-registration.
    """
    if _on_depsgraph_update not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph_update)


def unregister_handler() -> None:
    """
    Unregister the depsgraph update handler.

    Safe to call even when not registered.
    """
    if _on_depsgraph_update in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_on_depsgraph_update)


def clear_transform_cache() -> None:
    """
    Clear the last-sent transform cache.

    Should be called when a new session starts so that all current object
    transforms are treated as new and sent on the first change.
    """
    _last_sent.clear()


def prime_transform_cache(scene=None) -> None:
    """
    Pre-populate the transform cache with the current canonical transforms
    of all ID-tagged objects in the scene so that only actual changes are
    transmitted after connection.

    Args:
        scene: bpy.types.Scene.  Defaults to bpy.context.scene.
    """
    if scene is None:
        try:
            scene = bpy.context.scene
        except AttributeError:
            return

    clear_transform_cache()
    for obj in scene.objects:
        obj_id = get_id(obj)
        if obj_id is None:
            continue
        try:
            parent_id = get_id(obj.parent) if obj.parent else None
            td = extract_transform(obj, parent_id=parent_id)
            _last_sent[obj_id] = {
                "location": list(td.location),
                "rotation": list(td.rotation_quaternion),
                "scale": list(td.scale),
            }
        except Exception:
            pass  # Skip objects that cannot be extracted
