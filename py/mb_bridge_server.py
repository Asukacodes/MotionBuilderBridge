"""
MotionBuilderBridge in-editor TCP server.

This module is loaded inside Autodesk MotionBuilder's Python interpreter. It
keeps all networking non-blocking from MotionBuilder's point of view by polling
TCP accepts and UDP discovery probes from FBSystem.OnUIIdle.

Protocol:
    TCP request:  [4-byte BE length][JSON {"id", "script"|"command", "timeout", "token"?}]
    TCP response: [4-byte BE length][JSON {"id", "success", "output", "error"}]

Discovery:
    UDP multicast probe  -> {"v":1,"type":"probe","request_id":"...","filter":{"project":"*"}}
    UDP unicast response -> {"v":1,"type":"response","app":"motionbuilder", ...}
"""

import contextlib
import hashlib
import hmac
import io
import json
import os
import secrets
import socket
import struct
import sys
import traceback
from typing import Optional

try:
    import pyfbsdk as fb
except ImportError:
    fb = None

try:
    from mb_bridge_protocol import MAX_FRAME_BYTES, send_frame
except ImportError:
    # Support loading this file directly through exec(open(...).read()).
    _THIS_DIR = os.path.dirname(os.path.abspath(globals().get("__file__", os.getcwd())))
    if _THIS_DIR not in sys.path:
        sys.path.insert(0, _THIS_DIR)
    from mb_bridge_protocol import MAX_FRAME_BYTES, send_frame

__all__ = ["MBServer", "start_bridge", "stop_bridge", "get_bridge"]

DEFAULT_BIND = "127.0.0.1"
DEFAULT_PORT = 0
DEFAULT_DISCOVERY_GROUP = "239.255.43.42"
DEFAULT_DISCOVERY_PORT = 8997
DEFAULT_DISCOVERY_ENABLED = True
_MODULE_DIR = os.path.dirname(os.path.abspath(globals().get("__file__", os.getcwd())))
TOKEN_DIR = os.path.abspath(
    os.path.join(_MODULE_DIR, "..", "Saved", "MotionBuilderBridge")
)
TOKEN_FILE = os.path.join(TOKEN_DIR, "token.txt")


def _require_motionbuilder():
    if fb is None:
        raise RuntimeError(
            "pyfbsdk is not available. Load mb_bridge_server.py inside MotionBuilder."
        )


def _is_loopback(host):
    return host in ("127.0.0.1", "localhost", "::1")


def _parse_group(value):
    if not value:
        return DEFAULT_DISCOVERY_GROUP, DEFAULT_DISCOVERY_PORT
    if ":" in value:
        host, port_s = value.rsplit(":", 1)
        return host, int(port_s)
    return value, DEFAULT_DISCOVERY_PORT


def _token_fingerprint(token):
    if not token:
        return ""
    return hashlib.sha1(token.encode("utf-8")).hexdigest()[:16]


class MBServer(object):
    """MotionBuilder TCP bridge server driven by FBSystem.OnUIIdle."""

    def __init__(
        self,
        host=DEFAULT_BIND,
        port=DEFAULT_PORT,
        token="",
        discovery_group=DEFAULT_DISCOVERY_GROUP,
        discovery_port=DEFAULT_DISCOVERY_PORT,
        discovery_enabled=DEFAULT_DISCOVERY_ENABLED,
    ):
        _require_motionbuilder()
        self.host = host
        self.port = int(port)
        self.token = token or ""
        self.discovery_group = discovery_group
        self.discovery_port = int(discovery_port)
        self.discovery_enabled = bool(discovery_enabled)

        self._srv = None
        self._discovery_sock = None
        self._running = False
        self._pending_stop = False
        self._idle_callback = None
        self._globals = self._make_exec_globals()
        self.token_file = ""

    def start(self):
        if self._running:
            print("[MBBridge] already running on %s:%s" % (self.host, self.port))
            return self

        self._ensure_token_policy()
        self._start_tcp()
        self._start_discovery()

        self._idle_callback = self._on_idle
        fb.FBSystem().OnUIIdle.Add(self._idle_callback)
        self._running = True

        print("[MBBridge] listening on %s:%s" % (self.host, self.port))
        if self.discovery_enabled and self._discovery_sock is not None:
            print(
                "[MBBridge] discovery on %s:%s"
                % (self.discovery_group, self.discovery_port)
            )
        if self.token:
            print("[MBBridge] token auth enabled (%s)" % _token_fingerprint(self.token))
        return self

    def stop(self):
        self._pending_stop = False
        if self._idle_callback is not None:
            try:
                fb.FBSystem().OnUIIdle.Remove(self._idle_callback)
            except Exception:
                pass
            self._idle_callback = None

        for sock_attr in ("_srv", "_discovery_sock"):
            sock = getattr(self, sock_attr)
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass
                setattr(self, sock_attr, None)

        if self._running:
            print("[MBBridge] stopped")
        self._running = False

    def _ensure_token_policy(self):
        if self.token:
            self._write_token_file(self.token)
            return

        if _is_loopback(self.host):
            return

        self.token = secrets.token_urlsafe(32)
        self._write_token_file(self.token)
        print(
            "[MBBridge] non-loopback bind requires auth; generated token at %s"
            % self.token_file
        )

    def _write_token_file(self, token):
        try:
            if not os.path.isdir(TOKEN_DIR):
                os.makedirs(TOKEN_DIR)
            with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                f.write(token)
            self.token_file = TOKEN_FILE
        except Exception as exc:
            print("[MBBridge] warning: could not write token file: %s" % exc)

    def _start_tcp(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.host, self.port))
        srv.listen(8)
        srv.setblocking(False)
        self.port = srv.getsockname()[1]
        self._srv = srv

    def _start_discovery(self):
        if not self.discovery_enabled:
            return

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
            except OSError:
                pass
            sock.bind(("", self.discovery_port))
            mreq = socket.inet_aton(self.discovery_group) + socket.inet_aton("0.0.0.0")
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            sock.setblocking(False)
            self._discovery_sock = sock
        except OSError as exc:
            print("[MBBridge] discovery disabled: %s" % exc)
            try:
                sock.close()
            except OSError:
                pass
            self._discovery_sock = None

    def _on_idle(self, *args):
        if not self._running:
            return

        self._poll_discovery()
        self._poll_tcp()

        if self._pending_stop:
            self.stop()

    def _poll_discovery(self):
        sock = self._discovery_sock
        if sock is None:
            return

        for _ in range(8):
            try:
                data, addr = sock.recvfrom(64 * 1024)
            except BlockingIOError:
                return
            except OSError:
                return
            self._handle_discovery_datagram(data, addr)

    def _handle_discovery_datagram(self, data, addr):
        try:
            req = json.loads(data.decode("utf-8"))
        except Exception:
            return

        if req.get("v") != 1 or req.get("type") != "probe":
            return
        request_id = req.get("request_id")
        if not request_id:
            return

        filter_obj = req.get("filter") or {}
        project_filter = filter_obj.get("project", "*")
        if not self._matches_project_filter(project_filter):
            return

        resp = self._discovery_response(request_id)
        try:
            self._discovery_sock.sendto(
                json.dumps(resp, ensure_ascii=False).encode("utf-8"), addr
            )
        except OSError:
            pass

    def _matches_project_filter(self, project_filter):
        if not project_filter or project_filter == "*":
            return True
        f = str(project_filter).replace("\\", "/").lower()
        name = self._project_name().lower()
        path = self._scene_path().replace("\\", "/").lower()
        return f == name or f in name or (path and (path == f or path.endswith(f)))

    def _discovery_response(self, request_id):
        return {
            "v": 1,
            "type": "response",
            "app": "motionbuilder",
            "request_id": request_id,
            "pid": os.getpid(),
            "project": self._project_name(),
            "project_path": self._scene_path(),
            "engine_version": self._motionbuilder_version(),
            "tcp_bind": self.host,
            "tcp_port": self.port,
            "token_fingerprint": _token_fingerprint(self.token),
            "token_path": self.token_file,
        }

    def _poll_tcp(self):
        if self._srv is None:
            return

        for _ in range(4):
            try:
                client, _addr = self._srv.accept()
            except BlockingIOError:
                return
            except OSError:
                return
            self._handle_client(client)

    def _handle_client(self, client):
        try:
            client.settimeout(5.0)
            req = self._read_request(client)
            if req is None:
                return

            req_id = req.get("id", "<missing>")
            if not self._authorize(req):
                self._send(client, req_id, False, "", "unauthorized: bad token")
                return

            command = req.get("command", "")
            if command == "ping":
                self._send(client, req_id, True, "pong", "")
                return
            if command == "stop":
                self._send(client, req_id, True, "stopping", "")
                self._pending_stop = True
                return
            if command:
                self._send(client, req_id, False, "", "unknown command: %s" % command)
                return

            script = req.get("script", "")
            if not script:
                self._send(client, req_id, False, "", "missing 'script' field")
                return

            success, output, error = self._exec(script)
            self._send(client, req_id, success, output, error)
        except Exception:
            try:
                self._send(client, "<unknown>", False, "", traceback.format_exc())
            except Exception:
                pass
        finally:
            try:
                client.close()
            except OSError:
                pass

    def _read_request(self, client):
        header = self._recv_exact(client, 4)
        if not header:
            return None
        length = struct.unpack(">I", header)[0]
        if length == 0 or length > MAX_FRAME_BYTES:
            return None
        payload = self._recv_exact(client, length)
        if not payload:
            return None
        try:
            return json.loads(payload.decode("utf-8"))
        except Exception:
            self._send(client, "<invalid>", False, "", "invalid JSON")
            return None

    def _recv_exact(self, client, size):
        buf = b""
        while len(buf) < size:
            chunk = client.recv(size - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf

    def _authorize(self, req):
        if not self.token:
            return True
        given = req.get("token", "")
        return hmac.compare_digest(str(given), self.token)

    def _exec(self, script):
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        self._globals["__mb_result__"] = {}

        success = True
        error = ""
        with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
            try:
                exec(script, self._globals, self._globals)
            except Exception:
                success = False
                error = traceback.format_exc()

        stdout = stdout_buf.getvalue()
        stderr = stderr_buf.getvalue()
        if stderr:
            error = stderr + (("\n" + error) if error else "")
        return success, stdout, error

    def _send(self, client, req_id, success, output, error):
        send_frame(
            client,
            {
                "id": req_id,
                "success": bool(success),
                "output": output or "",
                "error": error or "",
            },
        )

    def _make_exec_globals(self):
        namespace = {
            "__name__": "__motionbuilder_bridge_exec__",
            "__builtins__": __builtins__,
            "fb": fb,
            "pyfbsdk": fb,
        }

        def bridge_output(key, value):
            namespace.setdefault("__mb_result__", {})[key] = value

        namespace["bridge_output"] = bridge_output

        try:
            import mb_helpers
            namespace["mb_helpers"] = mb_helpers
        except Exception:
            pass

        try:
            import mb_fps_helpers
            namespace["mb_fps_helpers"] = mb_fps_helpers
        except Exception:
            pass

        return namespace

    def _project_name(self):
        path = self._scene_path()
        if path:
            return os.path.splitext(os.path.basename(path))[0]
        return "MotionBuilder"

    def _scene_path(self):
        try:
            app = fb.FBApplication()
            for attr in ("FBXFileName", "FileName"):
                value = getattr(app, attr, "")
                if value:
                    return str(value)
        except Exception:
            pass
        return ""

    def _motionbuilder_version(self):
        try:
            system = fb.FBSystem()
            for attr in ("Version", "BuildVersion"):
                value = getattr(system, attr, "")
                if value:
                    return str(value)
        except Exception:
            pass
        return ""


_server_instance = None


def start_bridge(
    host=None,
    port=None,
    token=None,
    discovery_group=None,
    discovery_enabled=None,
):
    """Start MotionBuilderBridge inside MotionBuilder.

    Configuration precedence: explicit argument -> MB_BRIDGE_* env var -> default.
    """
    global _server_instance
    _require_motionbuilder()

    if _server_instance is not None and _server_instance._running:
        print(
            "[MBBridge] already running on %s:%s"
            % (_server_instance.host, _server_instance.port)
        )
        return _server_instance

    host = host if host is not None else os.environ.get("MB_BRIDGE_BIND", DEFAULT_BIND)
    if port is None:
        port = int(os.environ.get("MB_BRIDGE_PORT", DEFAULT_PORT))
    token = token if token is not None else os.environ.get("MB_BRIDGE_TOKEN", "")

    group_value = (
        discovery_group
        if discovery_group is not None
        else os.environ.get(
            "MB_BRIDGE_DISCOVERY_GROUP",
            "%s:%s" % (DEFAULT_DISCOVERY_GROUP, DEFAULT_DISCOVERY_PORT),
        )
    )
    disc_group, disc_port = _parse_group(group_value)

    if discovery_enabled is None:
        discovery_enabled = os.environ.get("MB_BRIDGE_DISCOVERY", "1") not in (
            "0",
            "false",
            "False",
            "no",
        )

    _server_instance = MBServer(
        host=host,
        port=port,
        token=token,
        discovery_group=disc_group,
        discovery_port=disc_port,
        discovery_enabled=discovery_enabled,
    )
    return _server_instance.start()


def stop_bridge():
    """Stop the active bridge server."""
    global _server_instance
    if _server_instance is not None:
        _server_instance.stop()
        _server_instance = None


def get_bridge():
    """Return the active MBServer instance, if any."""
    return _server_instance
