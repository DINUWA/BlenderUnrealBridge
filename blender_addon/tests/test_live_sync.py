"""
test_live_sync.py — Unit Tests for Milestone 10 Live Synchronization
=====================================================================

Tests:
  1. Protocol constants and schema validation
  2. Message encoding and decoding
  3. Handshake message generation (HELLO, HELLO_ACK)
  4. Transform update message generation and numeric validation
  5. Object ID format validation
  6. Change detector epsilon checks and cache behaviour
  7. Loopback socket integration: connect, handshake, transform update, disconnect
"""

import json
import math
import socket
import threading
import time
import unittest

from blender_unreal_bridge.live_sync.protocol import (
    LIVESYNC_PROTOCOL_VERSION,
    MSG_HELLO,
    MSG_HELLO_ACK,
    MSG_GOODBYE,
    MSG_KEEPALIVE,
    MSG_OBJECT_TRANSFORM_UPDATE,
    generate_session_id,
    build_hello,
    build_hello_ack,
    build_goodbye,
    build_keepalive,
    build_object_transform_update,
    encode_message,
    decode_message,
    validate_message,
    is_valid_object_id,
)
from blender_unreal_bridge.live_sync.transport import LiveSyncTransport, TransportError
from blender_unreal_bridge.live_sync.session import (
    LiveSyncSession,
    STATE_DISCONNECTED,
    STATE_CONNECTED,
)
from blender_unreal_bridge.live_sync.change_detector import (
    _vectors_close,
    _transform_unchanged,
    clear_transform_cache,
    LOCATION_EPSILON_CM,
    ROTATION_EPSILON,
    SCALE_EPSILON,
)


class TestLiveSyncProtocol(unittest.TestCase):
    """Test protocol constants, message generation, and schema validation."""

    def test_protocol_version(self):
        self.assertEqual(LIVESYNC_PROTOCOL_VERSION, "0.1.0")

    def test_session_id_generation(self):
        sid1 = generate_session_id()
        sid2 = generate_session_id()
        self.assertEqual(len(sid1), 8)
        self.assertNotEqual(sid1, sid2)

    def test_build_hello(self):
        msg = build_hello("sess1234", "0.1.0", 0)
        self.assertEqual(msg["message_type"], MSG_HELLO)
        self.assertEqual(msg["protocol_version"], "0.1.0")
        self.assertEqual(msg["session_id"], "sess1234")
        self.assertEqual(msg["sequence"], 0)
        errors = validate_message(msg)
        self.assertEqual(errors, [])

    def test_build_hello_ack(self):
        msg = build_hello_ack("sess1234", 0, accepted=True)
        self.assertEqual(msg["message_type"], MSG_HELLO_ACK)
        self.assertTrue(msg["accepted"])
        errors = validate_message(msg)
        self.assertEqual(errors, [])

    def test_build_goodbye(self):
        msg = build_goodbye("sess1234", 5, "test")
        self.assertEqual(msg["message_type"], MSG_GOODBYE)
        self.assertEqual(msg["sequence"], 5)
        errors = validate_message(msg)
        self.assertEqual(errors, [])

    def test_build_keepalive(self):
        msg = build_keepalive("sess1234", 3)
        self.assertEqual(msg["message_type"], MSG_KEEPALIVE)
        errors = validate_message(msg)
        self.assertEqual(errors, [])

    def test_build_object_transform_update(self):
        msg = build_object_transform_update(
            "sess1234",
            1,
            "obj_12345678",
            [10.0, 20.0, 30.0],
            [0.0, 0.0, 0.0, 1.0],
            [1.0, 1.0, 1.0],
            False,
        )
        self.assertEqual(msg["message_type"], MSG_OBJECT_TRANSFORM_UPDATE)
        self.assertEqual(msg["object_id"], "obj_12345678")
        self.assertEqual(msg["transform"]["location"], [10.0, 20.0, 30.0])
        errors = validate_message(msg)
        self.assertEqual(errors, [])

    def test_encode_decode_roundtrip(self):
        original = build_object_transform_update(
            "sess1234", 2, "obj_abcdef01", [1.0, 2.0, 3.0], [0.0, 0.0, 0.0, 1.0], [1.0, 1.0, 1.0]
        )
        encoded = encode_message(original)
        self.assertTrue(encoded.endswith(b"\n"))
        decoded = decode_message(encoded)
        self.assertEqual(original, decoded)

    def test_validation_missing_fields(self):
        self.assertTrue(len(validate_message({})) > 0)
        self.assertTrue(len(validate_message({"message_type": MSG_HELLO})) > 0)

    def test_validation_unsupported_version(self):
        msg = build_hello("sess1234")
        msg["protocol_version"] = "99.0.0"
        errors = validate_message(msg)
        self.assertTrue(any("Unsupported protocol version" in e for e in errors))

    def test_validation_invalid_object_id(self):
        msg = build_object_transform_update(
            "sess1234", 1, "invalid_id", [0, 0, 0], [0, 0, 0, 1], [1, 1, 1]
        )
        errors = validate_message(msg)
        self.assertTrue(any("Invalid 'object_id' format" in e for e in errors))

    def test_validation_non_finite_location(self):
        msg = build_object_transform_update(
            "sess1234", 1, "obj_12345678", [float("nan"), 0, 0], [0, 0, 0, 1], [1, 1, 1]
        )
        errors = validate_message(msg)
        self.assertTrue(any("finite numbers" in e for e in errors))

    def test_validation_zero_scale(self):
        msg = build_object_transform_update(
            "sess1234", 1, "obj_12345678", [0, 0, 0], [0, 0, 0, 1], [0.0, 1.0, 1.0]
        )
        errors = validate_message(msg)
        self.assertTrue(any("zero components" in e for e in errors))

    def test_is_valid_object_id(self):
        self.assertTrue(is_valid_object_id("obj_12345678"))
        self.assertTrue(is_valid_object_id("obj_abcdef01"))
        self.assertFalse(is_valid_object_id("obj_123"))
        self.assertFalse(is_valid_object_id("mesh_12345678"))
        self.assertFalse(is_valid_object_id("obj_1234567G"))  # G is not hex
        self.assertFalse(is_valid_object_id(None))


class TestChangeDetector(unittest.TestCase):
    """Test change detector epsilon and caching logic."""

    def test_vectors_close(self):
        self.assertTrue(_vectors_close([1.0, 2.0, 3.0], [1.0001, 2.0, 3.0], 0.001))
        self.assertFalse(_vectors_close([1.0, 2.0, 3.0], [1.01, 2.0, 3.0], 0.001))

    def test_transform_unchanged(self):
        cached = {
            "location": [100.0, 200.0, 300.0],
            "rotation": [0.0, 0.0, 0.0, 1.0],
            "scale": [1.0, 1.0, 1.0],
        }
        # Identical
        self.assertTrue(_transform_unchanged(cached, [100.0, 200.0, 300.0], [0.0, 0.0, 0.0, 1.0], [1.0, 1.0, 1.0]))
        # Sub-epsilon change (noise)
        self.assertTrue(_transform_unchanged(
            cached,
            [100.00001, 200.0, 300.0],
            [0.0, 0.0, 0.0, 1.0],
            [1.0, 1.0, 1.0],
        ))
        # Meaningful location change
        self.assertFalse(_transform_unchanged(
            cached,
            [101.0, 200.0, 300.0],
            [0.0, 0.0, 0.0, 1.0],
            [1.0, 1.0, 1.0],
        ))
        # Meaningful rotation change
        self.assertFalse(_transform_unchanged(
            cached,
            [100.0, 200.0, 300.0],
            [0.1, 0.0, 0.0, 0.995],
            [1.0, 1.0, 1.0],
        ))
        # Meaningful scale change
        self.assertFalse(_transform_unchanged(
            cached,
            [100.0, 200.0, 300.0],
            [0.0, 0.0, 0.0, 1.0],
            [1.5, 1.0, 1.0],
        ))


class TestLiveSyncLoopbackIntegration(unittest.TestCase):
    """Loopback socket test verifying handshake, transform send, and clean disconnect."""

    def test_loopback_session_flow(self):
        # Create a mock Unreal server on an ephemeral port
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.bind(("127.0.0.1", 0))
        server_sock.listen(1)
        port = server_sock.getsockname()[1]

        received_messages = []

        def server_thread():
            conn, _ = server_sock.accept()
            # Read HELLO
            buf = b""
            while b"\n" not in buf:
                buf += conn.recv(1024)
            hello_line, rest = buf.split(b"\n", 1)
            hello_msg = json.loads(hello_line.decode("utf-8"))
            received_messages.append(hello_msg)

            # Send HELLO_ACK
            ack = build_hello_ack(hello_msg["session_id"], sequence=0, accepted=True)
            conn.sendall(encode_message(ack))

            # Read updates until GOODBYE
            buf = rest
            while True:
                while b"\n" not in buf:
                    data = conn.recv(1024)
                    if not data:
                        break
                    buf += data
                if not buf:
                    break
                line, buf = buf.split(b"\n", 1)
                msg = json.loads(line.decode("utf-8"))
                received_messages.append(msg)
                if msg.get("message_type") == MSG_GOODBYE:
                    break
            conn.close()

        th = threading.Thread(target=server_thread, daemon=True)
        th.start()

        session = LiveSyncSession("127.0.0.1", port)
        self.assertEqual(session.state, STATE_DISCONNECTED)

        # 1. Connect & Handshake
        ok, msg = session.connect()
        self.assertTrue(ok)
        self.assertEqual(session.state, STATE_CONNECTED)
        self.assertIsNotNone(session.session_id)

        # 2. Send transform update
        ok, _ = session.send_transform_update(
            "obj_a1b2c3d4",
            [50.0, 100.0, 150.0],
            [0.0, 0.0, 0.0, 1.0],
            [1.0, 1.0, 1.0],
        )
        self.assertTrue(ok)

        # 3. Send keepalive
        ok, _ = session.send_keepalive()
        self.assertTrue(ok)

        # 4. Disconnect cleanly
        session.disconnect("test_done")
        self.assertEqual(session.state, STATE_DISCONNECTED)

        th.join(timeout=2.0)
        server_sock.close()

        # Verify messages received by the mock server
        self.assertGreaterEqual(len(received_messages), 3)
        self.assertEqual(received_messages[0]["message_type"], MSG_HELLO)
        self.assertEqual(received_messages[1]["message_type"], MSG_OBJECT_TRANSFORM_UPDATE)
        self.assertEqual(received_messages[1]["object_id"], "obj_a1b2c3d4")
        self.assertEqual(received_messages[2]["message_type"], MSG_KEEPALIVE)
        self.assertEqual(received_messages[3]["message_type"], MSG_GOODBYE)


if __name__ == "__main__":
    unittest.main()
