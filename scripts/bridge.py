#!/usr/bin/env python3
"""
MotionBuilderBridge client CLI.

Common use:
    python scripts/bridge.py ping
    python scripts/bridge.py exec "print('hello from MotionBuilder')"
    python scripts/bridge.py exec --stdin < script.py
    python scripts/bridge.py exec -
    python scripts/bridge.py exec-file scripts/example.py
    python scripts/bridge.py list-editors
    python scripts/bridge.py stop
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import struct
import sys
import time
import uuid
from dataclasses import dataclass
from typing import List, Optional, Tuple

DEFAULT_TIMEOUT = 30.0
DEFAULT_DISCOVERY_GROUP = "239.255.43.42"
DEFAULT_DISCOVERY_PORT = 8997
DEFAULT_DISCOVERY_TIMEOUT_MS = 800
MAX_FRAME_BYTES = 10 * 1024 * 1024
VERSION = "0.2.0"


@dataclass
class Endpoint:
    pid: int
    project: str
    project_path: str
    engine_version: str
    tcp_bind: str
    tcp_port: int
    token_fingerprint: str
    token_path: str = ""

    @property
    def host(self) -> str:
        if self.tcp_bind in ("0.0.0.0", "::"):
            return "127.0.0.1"
        return self.tcp_bind or "127.0.0.1"

    @property
    def port(self) -> int:
        return int(self.tcp_port)

    def __str__(self) -> str:
        token = " [token]" if self.token_fingerprint else ""
        version = (" " + self.engine_version) if self.engine_version else ""
        return "%s%s @ %s:%s (pid %s)%s" % (
            self.project or "MotionBuilder",
            version,
            self.host,
            self.port,
            self.pid,
            token,
        )


class DiscoveryError(Exception):
    pass


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass


def parse_host_port(value: str) -> Tuple[str, int]:
    if ":" not in value:
        raise ValueError("endpoint must be host:port")
    host, port_s = value.rsplit(":", 1)
    return host, int(port_s)


def parse_group(value: str) -> Tuple[str, int]:
    if ":" in value:
        host, port_s = value.rsplit(":", 1)
        return host, int(port_s)
    return value, DEFAULT_DISCOVERY_PORT


def encode_frame(data: dict) -> bytes:
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    return struct.pack(">I", len(body)) + body


def recv_all(sock: socket.socket, size: int) -> bytes:
    chunks = []
    remaining = size
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            raise ConnectionError("connection closed while reading response")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def send_request(host: str, port: int, payload: dict, timeout: float,
                 token: Optional[str] = None) -> dict:
    if token:
        payload = dict(payload)
        payload.setdefault("token", token)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect((host, int(port)))
        sock.sendall(encode_frame(payload))

        header = recv_all(sock, 4)
        length = struct.unpack(">I", header)[0]
        if length == 0 or length > MAX_FRAME_BYTES:
            raise RuntimeError("invalid response frame length: %s" % length)
        body = recv_all(sock, length)
        return json.loads(body.decode("utf-8"))


def discover(project_filter: str = "*", group: str = DEFAULT_DISCOVERY_GROUP,
             group_port: int = DEFAULT_DISCOVERY_PORT,
             timeout_ms: int = DEFAULT_DISCOVERY_TIMEOUT_MS) -> List[Endpoint]:
    request_id = str(uuid.uuid4())
    probe = {
        "v": 1,
        "type": "probe",
        "request_id": request_id,
        "filter": {"project": project_filter or "*"},
    }

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
        sock.bind(("0.0.0.0", 0))
        sock.sendto(json.dumps(probe).encode("utf-8"), (group, int(group_port)))

        deadline = time.monotonic() + (float(timeout_ms) / 1000.0)
        results = []
        seen = set()
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            sock.settimeout(remaining)
            try:
                data, _addr = sock.recvfrom(64 * 1024)
            except socket.timeout:
                break

            try:
                resp = json.loads(data.decode("utf-8"))
            except Exception:
                continue

            if resp.get("type") != "response":
                continue
            if resp.get("request_id") != request_id:
                continue
            if resp.get("app") not in ("motionbuilder", None):
                continue
            pid = int(resp.get("pid", 0))
            key = (pid, int(resp.get("tcp_port", 0)))
            if key in seen:
                continue
            seen.add(key)

            results.append(
                Endpoint(
                    pid=pid,
                    project=str(resp.get("project", "MotionBuilder")),
                    project_path=str(resp.get("project_path", "")),
                    engine_version=str(resp.get("engine_version", "")),
                    tcp_bind=str(resp.get("tcp_bind", "127.0.0.1")),
                    tcp_port=int(resp.get("tcp_port", 0)),
                    token_fingerprint=str(resp.get("token_fingerprint", "")),
                    token_path=str(resp.get("token_path", "")),
                )
            )
        return results
    finally:
        sock.close()


def matches_project(ep: Endpoint, project_filter: str) -> bool:
    if not project_filter or project_filter == "*":
        return True
    f = project_filter.replace("\\", "/").lower()
    name = ep.project.lower()
    path = ep.project_path.replace("\\", "/").lower()
    return f == name or f in name or (path and (path == f or path.endswith(f)))


def select_endpoint(endpoints: List[Endpoint],
                    project_filter: Optional[str] = None) -> Endpoint:
    if project_filter and project_filter != "*":
        endpoints = [e for e in endpoints if matches_project(e, project_filter)]

    if not endpoints:
        raise DiscoveryError(
            "no MotionBuilderBridge instance found. Start MotionBuilder and run "
            "scripts/start_bridge.py inside its Python environment, or pass "
            "--endpoint=127.0.0.1:<port>."
        )
    if len(endpoints) == 1:
        return endpoints[0]

    raise DiscoveryError(
        "%s MotionBuilderBridge instances found; pass --project=<name|path>:\n  %s"
        % (len(endpoints), "\n  ".join(str(e) for e in endpoints))
    )


def token_fingerprint(token: str) -> str:
    return hashlib.sha1(token.encode("utf-8")).hexdigest()[:16]


def load_token(ep: Endpoint, explicit_token: Optional[str] = None) -> Optional[str]:
    if not ep.token_fingerprint:
        return explicit_token or os.environ.get("MB_BRIDGE_TOKEN") or None

    candidates = []
    if explicit_token:
        candidates.append(explicit_token)
    env_token = os.environ.get("MB_BRIDGE_TOKEN")
    if env_token:
        candidates.append(env_token)
    if ep.token_path and os.path.isfile(ep.token_path):
        try:
            with open(ep.token_path, "r", encoding="utf-8") as f:
                candidates.append(f.read().strip())
        except OSError:
            pass

    for token in candidates:
        if token_fingerprint(token).lower() == ep.token_fingerprint.lower():
            return token

    raise DiscoveryError(
        "token required for %s but no matching token was found. Pass --token, "
        "set MB_BRIDGE_TOKEN, or read the token file shown by MotionBuilderBridge."
        % ep
    )


def resolve_target(args) -> Tuple[str, int, Optional[str], Optional[Endpoint]]:
    endpoint = getattr(args, "endpoint", None) or os.environ.get("MB_BRIDGE_ENDPOINT")
    explicit_token = getattr(args, "token", None) or os.environ.get("MB_BRIDGE_TOKEN")
    if endpoint:
        host, port = parse_host_port(endpoint)
        return host, port, explicit_token, None

    group_value = (
        getattr(args, "discovery_group", None)
        or os.environ.get("MB_BRIDGE_DISCOVERY_GROUP")
        or "%s:%s" % (DEFAULT_DISCOVERY_GROUP, DEFAULT_DISCOVERY_PORT)
    )
    group, group_port = parse_group(group_value)
    timeout_ms = int(
        getattr(args, "discovery_timeout", None)
        or os.environ.get("MB_BRIDGE_DISCOVERY_TIMEOUT_MS", DEFAULT_DISCOVERY_TIMEOUT_MS)
    )
    project_filter = (
        getattr(args, "project", None)
        or os.environ.get("MB_BRIDGE_PROJECT")
        or "*"
    )

    endpoints = discover(project_filter=project_filter, group=group,
                         group_port=group_port, timeout_ms=timeout_ms)
    ep = select_endpoint(endpoints, project_filter=project_filter)
    return ep.host, ep.port, load_token(ep, explicit_token), ep


def cmd_ping(args) -> int:
    try:
        host, port, token, _ep = resolve_target(args)
        resp = send_request(
            host,
            port,
            {"id": str(uuid.uuid4()), "command": "ping"},
            timeout=float(getattr(args, "timeout", DEFAULT_TIMEOUT)),
            token=token,
        )
    except Exception as exc:
        if getattr(args, "json", False):
            print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print("ERROR: %s" % exc, file=sys.stderr)
        return 1

    if getattr(args, "json", False):
        print(json.dumps(resp, ensure_ascii=False))
    elif resp.get("success"):
        print("Connected to MotionBuilderBridge at %s:%s (ready)" % (host, port))
    else:
        print("ERROR: %s" % (resp.get("error") or resp), file=sys.stderr)
        return 1
    return 0 if resp.get("success") else 1


def execute_code(args, code: str, mode: str, src: Optional[str] = None) -> int:
    try:
        host, port, token, _ep = resolve_target(args)
        resp = send_request(
            host,
            port,
            {
                "id": str(uuid.uuid4()),
                "script": code,
                "timeout": float(getattr(args, "timeout", DEFAULT_TIMEOUT)),
            },
            timeout=float(getattr(args, "timeout", DEFAULT_TIMEOUT)) + 5.0,
            token=token,
        )
    except Exception as exc:
        if getattr(args, "json", False):
            print(json.dumps({"success": False, "mode": mode, "src": src, "error": str(exc)}, ensure_ascii=False))
        else:
            print("ERROR: %s" % exc, file=sys.stderr)
        return 1

    if getattr(args, "json", False):
        print(json.dumps(resp, ensure_ascii=False))
    else:
        output = resp.get("output") or ""
        error = resp.get("error") or ""
        if output:
            print(output, end="" if output.endswith("\n") else "\n")
        if error:
            print(error, file=sys.stderr, end="" if error.endswith("\n") else "\n")

    return 0 if resp.get("success") else 1


def cmd_exec(args) -> int:
    use_stdin = bool(getattr(args, "stdin", False)) or getattr(args, "code", None) == "-"
    if use_stdin:
        if getattr(args, "code", None) not in (None, "-"):
            print("ERROR: cannot pass both a code argument and --stdin", file=sys.stderr)
            return 2
        code = sys.stdin.read()
        if not code.strip():
            print("ERROR: stdin was empty", file=sys.stderr)
            return 2
        return execute_code(args, code, mode="stdin")

    if not getattr(args, "code", None):
        print("ERROR: provide code or use --stdin", file=sys.stderr)
        return 2
    return execute_code(args, args.code, mode="exec")


def cmd_exec_file(args) -> int:
    try:
        with open(args.file, "r", encoding="utf-8") as f:
            code = f.read()
    except OSError as exc:
        print("ERROR: cannot read %s: %s" % (args.file, exc), file=sys.stderr)
        return 1
    return execute_code(args, code, mode="exec-file", src=args.file)


def cmd_stop(args) -> int:
    try:
        host, port, token, _ep = resolve_target(args)
        resp = send_request(
            host,
            port,
            {"id": str(uuid.uuid4()), "command": "stop"},
            timeout=float(getattr(args, "timeout", DEFAULT_TIMEOUT)),
            token=token,
        )
    except Exception as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 1

    if getattr(args, "json", False):
        print(json.dumps(resp, ensure_ascii=False))
    elif resp.get("success"):
        print("Server stop requested")
    else:
        print("ERROR: %s" % (resp.get("error") or resp), file=sys.stderr)
    return 0 if resp.get("success") else 1


def cmd_list_editors(args) -> int:
    group_value = (
        getattr(args, "discovery_group", None)
        or os.environ.get("MB_BRIDGE_DISCOVERY_GROUP")
        or "%s:%s" % (DEFAULT_DISCOVERY_GROUP, DEFAULT_DISCOVERY_PORT)
    )
    group, group_port = parse_group(group_value)
    timeout_ms = int(
        getattr(args, "discovery_timeout", None)
        or os.environ.get("MB_BRIDGE_DISCOVERY_TIMEOUT_MS", DEFAULT_DISCOVERY_TIMEOUT_MS)
    )
    project_filter = (
        getattr(args, "project", None)
        or os.environ.get("MB_BRIDGE_PROJECT")
        or "*"
    )

    try:
        endpoints = discover(project_filter=project_filter, group=group,
                             group_port=group_port, timeout_ms=timeout_ms)
    except OSError as exc:
        print("ERROR: discovery failed: %s" % exc, file=sys.stderr)
        return 2

    if project_filter != "*":
        endpoints = [e for e in endpoints if matches_project(e, project_filter)]

    if getattr(args, "json", False):
        print(json.dumps([e.__dict__ for e in endpoints], ensure_ascii=False))
    elif endpoints:
        for ep in endpoints:
            print(ep)
    else:
        print("(no MotionBuilderBridge instances found)")
        return 1
    return 0


def add_common_args(parser: argparse.ArgumentParser, suppress_defaults: bool = False) -> None:
    default = argparse.SUPPRESS if suppress_defaults else None
    parser.add_argument("--endpoint", default=default,
                        help="Connect directly to host:port instead of discovery.")
    parser.add_argument("--project", default=default,
                        help="Select a discovered instance by scene/project name or path.")
    parser.add_argument("--token", default=default,
                        help="Auth token, or set MB_BRIDGE_TOKEN.")
    parser.add_argument("--timeout", type=float,
                        default=argparse.SUPPRESS if suppress_defaults else DEFAULT_TIMEOUT,
                        help="Per-request timeout in seconds.")
    parser.add_argument("--json", action="store_true",
                        default=argparse.SUPPRESS if suppress_defaults else False,
                        help="Print machine-readable JSON.")
    parser.add_argument("--discovery-group", default=default,
                        help="Multicast group host:port.")
    parser.add_argument("--discovery-timeout", type=int,
                        default=argparse.SUPPRESS if suppress_defaults else DEFAULT_DISCOVERY_TIMEOUT_MS,
                        help="Discovery probe wait window in ms.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bridge.py",
        description="Execute Python inside Autodesk MotionBuilder via MotionBuilderBridge.",
    )
    add_common_args(parser)
    parser.add_argument("--version", action="store_true", help="Show client version.")

    sub = parser.add_subparsers(dest="command")

    ping = sub.add_parser("ping", help="Check bridge connectivity")
    add_common_args(ping, suppress_defaults=True)

    stop = sub.add_parser("stop", help="Ask the in-editor bridge to stop")
    add_common_args(stop, suppress_defaults=True)

    list_p = sub.add_parser("list-editors", help="List discovered MotionBuilder instances")
    add_common_args(list_p, suppress_defaults=True)

    exec_p = sub.add_parser("exec", help="Execute Python code")
    add_common_args(exec_p, suppress_defaults=True)
    exec_p.add_argument("code", nargs="?", help="Python code. Use '-' or --stdin for stdin.")
    exec_p.add_argument("--stdin", action="store_true", help="Read code from stdin.")

    exec_file = sub.add_parser("exec-file", help="Execute a Python file")
    add_common_args(exec_file, suppress_defaults=True)
    exec_file.add_argument("file", help="Path to a .py file")

    return parser


def main() -> None:
    _configure_stdio()
    parser = build_parser()
    args = parser.parse_args()

    if args.version:
        print("MotionBuilderBridge bridge.py v%s" % VERSION)
        raise SystemExit(0)

    command = args.command or "ping"
    if command == "ping":
        raise SystemExit(cmd_ping(args))
    if command == "stop":
        raise SystemExit(cmd_stop(args))
    if command == "list-editors":
        raise SystemExit(cmd_list_editors(args))
    if command == "exec":
        raise SystemExit(cmd_exec(args))
    if command == "exec-file":
        raise SystemExit(cmd_exec_file(args))

    parser.print_help()
    raise SystemExit(2)


if __name__ == "__main__":
    main()
