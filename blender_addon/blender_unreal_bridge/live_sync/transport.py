"""
live_sync/transport.py — TCP Transport Abstraction (Milestone 10)
=================================================================

Provides a thin, blocking TCP client transport used by the live-sync session.

Design constraints
------------------
* No external dependencies — uses Python stdlib `socket` only.
* Transport is isolated behind the LiveSyncTransport class so the session
  can swap implementations (e.g. named pipe on Windows) without changing
  protocol code.
* Blender must never crash due to transport errors.  All I/O is wrapped in
  try/except and returns structured results.
* Thread safety: intended to be called from Blender's main thread via
  app.timers or depsgraph handlers.  No background threads are used.
* Line-delimited protocol: each message is one UTF-8 JSON line terminated
  by '\\n'.
"""

import socket
import errno


class TransportError(Exception):
    """Raised for unrecoverable transport errors (connection refused, etc.)."""
    pass


class LiveSyncTransport:
    """
    Blocking line-framed TCP client transport.

    Usage
    -----
    t = LiveSyncTransport("127.0.0.1", 27284)
    t.connect()        # raises TransportError on failure
    t.send_line(data)  # send bytes ending with '\\n'
    line = t.recv_line()  # receive one line (blocks until newline)
    t.close()

    Both send_line and recv_line propagate TransportError on socket failure.
    The caller (session) is responsible for catching TransportError and
    transitioning to the DISCONNECTED state.
    """

    RECV_BUFFER_SIZE = 65536  # 64 KB
    CONNECT_TIMEOUT_S = 3.0   # 3-second connect timeout

    def __init__(self, host: str, port: int):
        self._host = host
        self._port = port
        self._sock: socket.socket | None = None
        self._recv_buf = b""  # partial line buffer

    @property
    def is_connected(self) -> bool:
        """Return True if the socket is currently open."""
        return self._sock is not None

    def connect(self) -> None:
        """
        Open a TCP connection to (host, port).

        Raises:
            TransportError: If connection fails or times out.
        """
        if self._sock is not None:
            return  # Already connected

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(self.CONNECT_TIMEOUT_S)
            s.connect((self._host, self._port))
            # Switch to blocking mode with a generous read timeout
            s.settimeout(5.0)
            self._sock = s
            self._recv_buf = b""
        except (ConnectionRefusedError, TimeoutError, OSError) as exc:
            self._sock = None
            raise TransportError(
                f"Cannot connect to {self._host}:{self._port} — {exc}"
            ) from exc

    def send_line(self, data: bytes) -> None:
        """
        Send one message line.

        Args:
            data: UTF-8 encoded bytes.  Must end with '\\n'.

        Raises:
            TransportError: If the socket is closed or send fails.
        """
        if self._sock is None:
            raise TransportError("Transport is not connected.")
        try:
            self._sock.sendall(data)
        except (BrokenPipeError, ConnectionResetError, OSError) as exc:
            self._close_socket()
            raise TransportError(f"Send failed: {exc}") from exc

    def recv_line(self) -> bytes | None:
        """
        Receive one complete newline-terminated message line without blocking
        longer than the socket timeout.

        Returns:
            bytes of one complete line (including '\\n'), or None if the
            socket timed out (no data available).

        Raises:
            TransportError: If the connection is closed or an I/O error occurs.
        """
        if self._sock is None:
            raise TransportError("Transport is not connected.")

        # Check if there is already a complete line in the buffer.
        nl_idx = self._recv_buf.find(b"\n")
        if nl_idx != -1:
            line = self._recv_buf[: nl_idx + 1]
            self._recv_buf = self._recv_buf[nl_idx + 1 :]
            return line

        # Try to receive more data.
        try:
            chunk = self._sock.recv(self.RECV_BUFFER_SIZE)
            if not chunk:
                # Remote end closed connection gracefully.
                self._close_socket()
                raise TransportError("Remote end closed the connection.")
            self._recv_buf += chunk
        except socket.timeout:
            return None  # No data within timeout — not an error
        except OSError as exc:
            if exc.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                return None
            self._close_socket()
            raise TransportError(f"Recv failed: {exc}") from exc

        # Check again after receiving new data.
        nl_idx = self._recv_buf.find(b"\n")
        if nl_idx != -1:
            line = self._recv_buf[: nl_idx + 1]
            self._recv_buf = self._recv_buf[nl_idx + 1 :]
            return line

        return None  # Partial line — more data needed

    def close(self) -> None:
        """Close the transport connection cleanly."""
        self._close_socket()

    def _close_socket(self) -> None:
        """Internal: close and discard the socket."""
        if self._sock is not None:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        self._recv_buf = b""
