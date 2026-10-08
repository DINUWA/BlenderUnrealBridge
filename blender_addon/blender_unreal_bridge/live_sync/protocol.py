"""
live_sync/protocol.py — Live Synchronisation Message Protocol (Milestone 10)
=============================================================================

Defines the versioned, schema-first live-sync message model for the Blender ↔
Unreal Bridge live synchronisation layer (BUBRIDGE_LIVESYNC v0.1.0).

Design constraints
------------------
* Backward compatibility: does NOT modify any .bubridge package schemas.
* Transport-agnostic: message building/parsing functions work with plain dicts.
* Canonical coordinates: every transform value is ALREADY in Bridge canonical
  space (Left-Handed, +Z Up, +X Forward, +Y Right, Centimetres).
  The live-sync layer NEVER performs coordinate conversion itself; it
  delegates to transforms/canonical.py (Blender side) or reuses the existing
  BridgeTransformConverter (Unreal side).
* Idempotent updates: all transform updates are ABSOLUTE (not relative deltas),
  so applying the same message twice produces the same result.
* Schema versioning: "protocol_version" is present in every message.
* Stable IDs only: objects are identified by bubridge_id — never by name.

Message types
-------------
HELLO          : Initial handshake sent by Blender to Unreal.
HELLO_ACK      : Acknowledgement from Unreal — confirms version compatibility.
GOODBYE        : Clean shutdown notification.
KEEPALIVE      : Heartbeat to detect stale connections.
OBJECT_TRANSFORM_UPDATE : Absolute canonical transform for one object.

Wire format
-----------
Each message is a single JSON object encoded as UTF-8, terminated by a
newline (\\n). This allows simple line-by-line reading on both ends.

Example HELLO:
{
  "message_type": "HELLO",
  "protocol_version": "0.1.0",
  "session_id": "abc12345",
  "source": "BlenderUnrealBridge_Addon",
  "source_version": "0.1.0",
  "sequence": 0
}

Example OBJECT_TRANSFORM_UPDATE:
{
  "message_type": "OBJECT_TRANSFORM_UPDATE",
  "protocol_version": "0.1.0",
  "session_id": "abc12345",
  "sequence": 1,
  "object_id": "obj_12345678",
  "transform": {
    "location": [0.0, 0.0, 100.0],
    "rotation": [0.0, 0.0, 0.0, 1.0],
    "scale": [1.0, 1.0, 1.0],
    "has_negative_scale": false
  }
}
"""

import json
import uuid

# ---------------------------------------------------------------------------
# Protocol constants
# ---------------------------------------------------------------------------

LIVESYNC_PROTOCOL_VERSION = "0.1.0"

# Message type identifiers
MSG_HELLO = "HELLO"
MSG_HELLO_ACK = "HELLO_ACK"
MSG_GOODBYE = "GOODBYE"
MSG_KEEPALIVE = "KEEPALIVE"
MSG_OBJECT_TRANSFORM_UPDATE = "OBJECT_TRANSFORM_UPDATE"

# Source identifier string embedded in HELLO
ADDON_SOURCE_IDENTIFIER = "BlenderUnrealBridge_Addon"

# Default TCP port for live sync
DEFAULT_PORT = 27284
DEFAULT_HOST = "127.0.0.1"


# ---------------------------------------------------------------------------
# Session ID generation
# ---------------------------------------------------------------------------

def generate_session_id() -> str:
    """Generate a random 8-character hex session ID."""
    return uuid.uuid4().hex[:8]


# ---------------------------------------------------------------------------
# Message builders (pure functions, no I/O)
# ---------------------------------------------------------------------------

def build_hello(session_id: str, addon_version: str = "0.1.0", sequence: int = 0) -> dict:
    """
    Build a HELLO handshake message.

    Args:
        session_id:     Unique session identifier (8 hex chars).
        addon_version:  Add-on version string.
        sequence:       Message sequence counter.

    Returns:
        Dict representing the HELLO message.
    """
    return {
        "message_type": MSG_HELLO,
        "protocol_version": LIVESYNC_PROTOCOL_VERSION,
        "session_id": session_id,
        "source": ADDON_SOURCE_IDENTIFIER,
        "source_version": addon_version,
        "sequence": sequence,
    }


def build_hello_ack(session_id: str, sequence: int = 0, accepted: bool = True, reason: str = "") -> dict:
    """
    Build a HELLO_ACK acknowledgement message.

    Args:
        session_id: Session ID from the original HELLO.
        sequence:   Response sequence number.
        accepted:   Whether the handshake was accepted.
        reason:     Human-readable reason if rejected.

    Returns:
        Dict representing the HELLO_ACK message.
    """
    msg = {
        "message_type": MSG_HELLO_ACK,
        "protocol_version": LIVESYNC_PROTOCOL_VERSION,
        "session_id": session_id,
        "accepted": accepted,
        "sequence": sequence,
    }
    if not accepted and reason:
        msg["reason"] = reason
    return msg


def build_goodbye(session_id: str, sequence: int, reason: str = "shutdown") -> dict:
    """
    Build a GOODBYE clean-shutdown message.

    Args:
        session_id: Active session ID.
        sequence:   Message sequence number.
        reason:     Human-readable reason string.

    Returns:
        Dict representing the GOODBYE message.
    """
    return {
        "message_type": MSG_GOODBYE,
        "protocol_version": LIVESYNC_PROTOCOL_VERSION,
        "session_id": session_id,
        "sequence": sequence,
        "reason": reason,
    }


def build_keepalive(session_id: str, sequence: int) -> dict:
    """
    Build a KEEPALIVE heartbeat message.

    Args:
        session_id: Active session ID.
        sequence:   Message sequence number.

    Returns:
        Dict representing the KEEPALIVE message.
    """
    return {
        "message_type": MSG_KEEPALIVE,
        "protocol_version": LIVESYNC_PROTOCOL_VERSION,
        "session_id": session_id,
        "sequence": sequence,
    }


def build_object_transform_update(
    session_id: str,
    sequence: int,
    object_id: str,
    location: list,
    rotation: list,
    scale: list,
    has_negative_scale: bool = False,
) -> dict:
    """
    Build an OBJECT_TRANSFORM_UPDATE message carrying an absolute canonical
    Bridge transform.

    All values must already be in canonical Bridge space:
      - location:  [x, y, z] in centimetres
      - rotation:  [x, y, z, w] unit quaternion
      - scale:     [sx, sy, sz] dimensionless ratio

    Args:
        session_id:         Active session ID.
        sequence:           Monotonically increasing sequence number.
        object_id:          Stable bubridge_id (e.g. "obj_12345678").
        location:           [x, y, z] cm.
        rotation:           [x, y, z, w] canonical quaternion.
        scale:              [sx, sy, sz].
        has_negative_scale: True if any scale component is negative.

    Returns:
        Dict representing the OBJECT_TRANSFORM_UPDATE message.
    """
    return {
        "message_type": MSG_OBJECT_TRANSFORM_UPDATE,
        "protocol_version": LIVESYNC_PROTOCOL_VERSION,
        "session_id": session_id,
        "sequence": sequence,
        "object_id": object_id,
        "transform": {
            "location": [float(location[0]), float(location[1]), float(location[2])],
            "rotation": [float(rotation[0]), float(rotation[1]), float(rotation[2]), float(rotation[3])],
            "scale": [float(scale[0]), float(scale[1]), float(scale[2])],
            "has_negative_scale": bool(has_negative_scale),
        },
    }


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def encode_message(msg: dict) -> bytes:
    """
    Serialise a message dict to UTF-8 bytes with a trailing newline.

    Args:
        msg: Message dict.

    Returns:
        UTF-8 encoded bytes ending with '\\n'.

    Raises:
        ValueError: If msg contains non-JSON-serialisable values.
    """
    return (json.dumps(msg, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def decode_message(raw: bytes) -> dict:
    """
    Decode a UTF-8 byte string (one message line) into a message dict.

    Args:
        raw: Raw bytes of a single message line.

    Returns:
        Parsed message dict.

    Raises:
        ValueError: If the bytes are not valid JSON.
    """
    return json.loads(raw.decode("utf-8").strip())


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def validate_message(msg: dict) -> list:
    """
    Validate a parsed message dict against the live-sync protocol schema.

    Returns a list of error strings (empty list = valid).

    Args:
        msg: Parsed message dict.

    Returns:
        List of human-readable error strings.  Empty = no errors.
    """
    errors = []

    if not isinstance(msg, dict):
        return ["Message is not a JSON object."]

    # Required fields in every message
    if "message_type" not in msg:
        errors.append("Missing required field: 'message_type'.")
    if "protocol_version" not in msg:
        errors.append("Missing required field: 'protocol_version'.")
    elif msg["protocol_version"] != LIVESYNC_PROTOCOL_VERSION:
        errors.append(
            f"Unsupported protocol version '{msg['protocol_version']}'. "
            f"Expected '{LIVESYNC_PROTOCOL_VERSION}'."
        )
    if "session_id" not in msg:
        errors.append("Missing required field: 'session_id'.")

    if errors:
        return errors

    msg_type = msg.get("message_type", "")
    known_types = {MSG_HELLO, MSG_HELLO_ACK, MSG_GOODBYE, MSG_KEEPALIVE, MSG_OBJECT_TRANSFORM_UPDATE}
    if msg_type not in known_types:
        errors.append(f"Unknown message_type: '{msg_type}'.")
        return errors

    if msg_type == MSG_OBJECT_TRANSFORM_UPDATE:
        errors.extend(_validate_transform_update(msg))

    return errors


def _validate_transform_update(msg: dict) -> list:
    """Validate fields specific to OBJECT_TRANSFORM_UPDATE messages."""
    errors = []

    # object_id
    obj_id = msg.get("object_id", "")
    if not obj_id:
        errors.append("OBJECT_TRANSFORM_UPDATE: Missing 'object_id'.")
    elif not isinstance(obj_id, str) or not obj_id.startswith("obj_") or len(obj_id) != 12:
        errors.append(
            f"OBJECT_TRANSFORM_UPDATE: Invalid 'object_id' format '{obj_id}'. "
            f"Expected 'obj_<8 hex chars>'."
        )

    # transform block
    transform = msg.get("transform")
    if transform is None:
        errors.append("OBJECT_TRANSFORM_UPDATE: Missing 'transform' block.")
        return errors
    if not isinstance(transform, dict):
        errors.append("OBJECT_TRANSFORM_UPDATE: 'transform' must be a JSON object.")
        return errors

    # location: array of 3 finite floats
    loc = transform.get("location")
    if loc is None:
        errors.append("OBJECT_TRANSFORM_UPDATE: Missing 'transform.location'.")
    elif not _is_finite_vector3(loc):
        errors.append("OBJECT_TRANSFORM_UPDATE: 'transform.location' must be [x, y, z] with finite numbers.")

    # rotation: array of 4 finite floats (quaternion)
    rot = transform.get("rotation")
    if rot is None:
        errors.append("OBJECT_TRANSFORM_UPDATE: Missing 'transform.rotation'.")
    elif not _is_finite_vector4(rot):
        errors.append("OBJECT_TRANSFORM_UPDATE: 'transform.rotation' must be [x, y, z, w] with finite numbers.")

    # scale: array of 3 finite floats, no zero
    scale = transform.get("scale")
    if scale is None:
        errors.append("OBJECT_TRANSFORM_UPDATE: Missing 'transform.scale'.")
    elif not _is_finite_vector3(scale):
        errors.append("OBJECT_TRANSFORM_UPDATE: 'transform.scale' must be [sx, sy, sz] with finite numbers.")
    elif any(s == 0.0 for s in scale):
        errors.append("OBJECT_TRANSFORM_UPDATE: 'transform.scale' must not contain zero components.")

    return errors


def _is_finite_vector3(val) -> bool:
    """Return True if val is a list of exactly 3 finite numbers."""
    import math
    if not isinstance(val, list) or len(val) != 3:
        return False
    return all(isinstance(v, (int, float)) and math.isfinite(v) for v in val)


def _is_finite_vector4(val) -> bool:
    """Return True if val is a list of exactly 4 finite numbers."""
    import math
    if not isinstance(val, list) or len(val) != 4:
        return False
    return all(isinstance(v, (int, float)) and math.isfinite(v) for v in val)


def is_valid_object_id(obj_id: str) -> bool:
    """Return True if obj_id matches the 'obj_XXXXXXXX' format."""
    if not isinstance(obj_id, str):
        return False
    if not obj_id.startswith("obj_") or len(obj_id) != 12:
        return False
    hex_part = obj_id[4:]
    return all(c in "0123456789abcdef" for c in hex_part)
