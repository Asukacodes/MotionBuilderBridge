"""
Length-prefixed JSON protocol helpers for MotionBuilderBridge.

Wire format:
    [4-byte big-endian payload length][UTF-8 JSON payload]
"""

import json
import select
import struct
from typing import Optional

MAX_FRAME_BYTES = 10 * 1024 * 1024


def encode_frame(data):
    """Serialize a dictionary to a length-prefixed UTF-8 JSON frame."""
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    return struct.pack(">I", len(body)) + body


def decode_frame(sock, timeout=30.0):
    """Read one frame from a socket. Returns None on timeout, EOF, or bad size."""
    header = recv_exact(sock, 4, timeout=timeout)
    if not header:
        return None

    length = struct.unpack(">I", header)[0]
    if length == 0 or length > MAX_FRAME_BYTES:
        return None

    payload = recv_exact(sock, length, timeout=timeout)
    if not payload:
        return None

    return json.loads(payload.decode("utf-8"))


def recv_exact(sock, n, timeout=30.0):
    """Receive exactly n bytes, returning None on timeout or EOF."""
    old_timeout = sock.gettimeout()
    sock.setblocking(False)
    try:
        buf = b""
        while len(buf) < n:
            ready, _, _ = select.select([sock], [], [], timeout)
            if not ready:
                return None
            chunk = sock.recv(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf
    finally:
        sock.setblocking(True)
        sock.settimeout(old_timeout)


def send_frame(sock, data):
    """Send one JSON frame. Returns True when sendall succeeds."""
    try:
        sock.sendall(encode_frame(data))
        return True
    except OSError:
        return False
