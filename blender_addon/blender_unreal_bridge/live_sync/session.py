"""
live_sync/session.py — Live Sync Session Lifecycle (Milestone 10)
=================================================================

Manages the single live-sync session between Blender and Unreal.

The session is a simple state machine:

    DISCONNECTED
         |
    connect()
         |
    HANDSHAKING  (sends HELLO, waits for HELLO_ACK)
         |
    CONNECTED
         |  (depsgraph changes trigger transform updates)
         |
    disconnect() or transport error
         |
    DISCONNECTED

Rules
-----
* One session at a time (module-level singleton).
* Blender must remain usable when Unreal is unavailable.
* Transport errors transition the session to DISCONNECTED without raising.
* Sequence numbers are monotonically increasing within a session.
* On reconnect a fresh session_id and sequence counter are started.
"""

import logging

from .protocol import (
    LIVESYNC_PROTOCOL_VERSION,
    MSG_HELLO_ACK,
    generate_session_id,
    build_hello,
    build_goodbye,
    build_keepalive,
    build_object_transform_update,
    encode_message,
    decode_message,
    validate_message,
)
from .transport import LiveSyncTransport, TransportError

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Session states
# ---------------------------------------------------------------------------

STATE_DISCONNECTED = "DISCONNECTED"
STATE_HANDSHAKING = "HANDSHAKING"
STATE_CONNECTED = "CONNECTED"


# ---------------------------------------------------------------------------
# Session class
# ---------------------------------------------------------------------------

class LiveSyncSession:
    """
    Manages the lifecycle of a live-sync connection to Unreal.

    Attributes (read-only externally):
        state: Current state string (DISCONNECTED / HANDSHAKING / CONNECTED).
        session_id: Active session identifier, or None if disconnected.
        host, port: Connection parameters.
    """

    def __init__(self, host: str, port: int, addon_version: str = "0.1.0"):
        self._host = host
        self._port = port
        self._addon_version = addon_version
        self._state = STATE_DISCONNECTED
        self._session_id: str | None = None
        self._sequence = 0
        self._transport: LiveSyncTransport | None = None

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> str:
        return self._state

    @property
    def is_connected(self) -> bool:
        return self._state == STATE_CONNECTED

    @property
    def session_id(self) -> str | None:
        return self._session_id

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> tuple[bool, str]:
        """
        Attempt to connect and perform the HELLO handshake.

        Returns:
            (success: bool, message: str)
        """
        if self._state == STATE_CONNECTED:
            return True, "Already connected."

        # Fresh session state
        self._session_id = generate_session_id()
        self._sequence = 0
        self._transport = LiveSyncTransport(self._host, self._port)
        self._state = STATE_HANDSHAKING

        # --- 1. Connect TCP ---
        try:
            self._transport.connect()
        except TransportError as exc:
            self._reset()
            msg = f"[LIVE-SYNC] Connection failed: {exc}"
            log.warning(msg)
            return False, msg

        # --- 2. Send HELLO ---
        hello_msg = build_hello(self._session_id, self._addon_version, self._sequence)
        self._sequence += 1
        try:
            self._transport.send_line(encode_message(hello_msg))
        except TransportError as exc:
            self._reset()
            msg = f"[LIVE-SYNC] Failed to send HELLO: {exc}"
            log.warning(msg)
            return False, msg

        # --- 3. Wait for HELLO_ACK ---
        try:
            raw = self._transport.recv_line()
        except TransportError as exc:
            self._reset()
            msg = f"[LIVE-SYNC] Failed to receive HELLO_ACK: {exc}"
            log.warning(msg)
            return False, msg

        if raw is None:
            self._reset()
            msg = "[LIVE-SYNC] No HELLO_ACK received within timeout."
            log.warning(msg)
            return False, msg

        try:
            ack = decode_message(raw)
        except (ValueError, UnicodeDecodeError) as exc:
            self._reset()
            msg = f"[LIVE-SYNC] Malformed HELLO_ACK: {exc}"
            log.warning(msg)
            return False, msg

        # Validate ACK
        if ack.get("message_type") != MSG_HELLO_ACK:
            self._reset()
            msg = (
                f"[LIVE-SYNC] Expected HELLO_ACK, got '{ack.get('message_type')}'."
            )
            log.warning(msg)
            return False, msg

        if not ack.get("accepted", False):
            reason = ack.get("reason", "no reason given")
            self._reset()
            msg = f"[LIVE-SYNC] Handshake rejected by Unreal: {reason}"
            log.warning(msg)
            return False, msg

        # Check protocol version compatibility
        ack_version = ack.get("protocol_version", "")
        if ack_version != LIVESYNC_PROTOCOL_VERSION:
            self._reset()
            msg = (
                f"[LIVE-SYNC] Protocol version mismatch: Blender={LIVESYNC_PROTOCOL_VERSION}, "
                f"Unreal={ack_version}"
            )
            log.warning(msg)
            return False, msg

        self._state = STATE_CONNECTED
        ok_msg = (
            f"[LIVE-SYNC] Connected to Unreal at {self._host}:{self._port} "
            f"(session={self._session_id})"
        )
        log.info(ok_msg)
        return True, ok_msg

    def disconnect(self, reason: str = "user_disconnect") -> None:
        """
        Send GOODBYE and cleanly close the connection.

        Args:
            reason: Human-readable reason for the disconnection.
        """
        if self._state == STATE_CONNECTED and self._transport and self._transport.is_connected:
            try:
                goodbye = build_goodbye(self._session_id, self._sequence, reason)
                self._sequence += 1
                self._transport.send_line(encode_message(goodbye))
            except TransportError:
                pass  # Best-effort GOODBYE

        if self._transport:
            self._transport.close()
        self._reset()
        log.info("[LIVE-SYNC] Disconnected.")

    def send_transform_update(
        self,
        object_id: str,
        location: list,
        rotation: list,
        scale: list,
        has_negative_scale: bool = False,
    ) -> tuple[bool, str]:
        """
        Send an OBJECT_TRANSFORM_UPDATE message.

        All transform values must already be in canonical Bridge space.

        Args:
            object_id:          Stable bubridge_id.
            location:           [x, y, z] cm.
            rotation:           [x, y, z, w] quaternion.
            scale:              [sx, sy, sz].
            has_negative_scale: True if any scale component is negative.

        Returns:
            (success: bool, message: str)
        """
        if not self.is_connected:
            return False, "[LIVE-SYNC] Not connected."

        msg = build_object_transform_update(
            self._session_id,
            self._sequence,
            object_id,
            location,
            rotation,
            scale,
            has_negative_scale,
        )
        self._sequence += 1

        try:
            self._transport.send_line(encode_message(msg))
        except TransportError as exc:
            self._handle_transport_error(exc)
            return False, f"[LIVE-SYNC] Send failed: {exc}"

        return True, f"[LIVE-SYNC] Transform sent for {object_id} (seq={self._sequence - 1})"

    def send_keepalive(self) -> tuple[bool, str]:
        """
        Send a KEEPALIVE heartbeat.

        Returns:
            (success: bool, message: str)
        """
        if not self.is_connected:
            return False, "[LIVE-SYNC] Not connected."

        msg = build_keepalive(self._session_id, self._sequence)
        self._sequence += 1
        try:
            self._transport.send_line(encode_message(msg))
        except TransportError as exc:
            self._handle_transport_error(exc)
            return False, f"[LIVE-SYNC] Keepalive failed: {exc}"

        return True, "[LIVE-SYNC] Keepalive sent."

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _handle_transport_error(self, exc: TransportError) -> None:
        """Transition to DISCONNECTED on a transport error."""
        log.warning("[LIVE-SYNC] Transport error — disconnecting: %s", exc)
        if self._transport:
            self._transport.close()
        self._reset()

    def _reset(self) -> None:
        """Reset session to DISCONNECTED state."""
        self._state = STATE_DISCONNECTED
        self._session_id = None
        self._sequence = 0
        if self._transport:
            self._transport.close()
            self._transport = None


# ---------------------------------------------------------------------------
# Module-level singleton session
# ---------------------------------------------------------------------------

_session: LiveSyncSession | None = None


def get_session() -> LiveSyncSession | None:
    """Return the current module-level session, or None if none exists."""
    return _session


def ensure_session(host: str, port: int, addon_version: str = "0.1.0") -> LiveSyncSession:
    """
    Return the existing session if it matches (host, port), otherwise create
    a new one.  Does NOT connect — call session.connect() separately.

    Args:
        host: TCP host.
        port: TCP port.
        addon_version: Version string embedded in HELLO.

    Returns:
        LiveSyncSession instance.
    """
    global _session
    if _session is None or _session.host != host or _session.port != port:
        if _session is not None:
            _session.disconnect("replaced_by_new_session")
        _session = LiveSyncSession(host, port, addon_version)
    return _session


def clear_session() -> None:
    """Disconnect and discard the module-level session."""
    global _session
    if _session is not None:
        _session.disconnect("session_cleared")
        _session = None
