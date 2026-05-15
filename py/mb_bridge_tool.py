"""
MotionBuilderBridge control panel for Autodesk MotionBuilder.

Load inside MotionBuilder:
    exec(open(r"D:/LAFAN/MotionBuilderBridge/py/mb_bridge_tool.py").read())
"""

import importlib
import os
import subprocess
import sys
import traceback

import pyfbsdk as fb
import pyfbsdk_additions as ui

_ROOT = os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(globals().get("__file__", r"D:/LAFAN/MotionBuilderBridge/py/mb_bridge_tool.py"))),
    "..",
))
_PY_DIR = os.path.join(_ROOT, "py")
_BRIDGE_CLI = os.path.join(_ROOT, "scripts", "bridge.py")
_API_DOC = os.path.join(_ROOT, "docs", "motionbuilder-bridge-api.md")
_README = os.path.join(_ROOT, "README.md")

if _PY_DIR not in sys.path:
    sys.path.insert(0, _PY_DIR)

import mb_bridge_server

TOOL_NAME = "MotionBuilderBridge Control Panel"
_STATE = {}


def register_tool(auto_start=False, show=False):
    """Create/register the control panel so it appears in Python Tools."""
    if auto_start and not _server_running():
        mb_bridge_server.start_bridge()
    return show_tool(show=show)


def show_tool(show=True):
    """Create and optionally show the MotionBuilderBridge control panel."""
    tool = ui.FBCreateUniqueTool(TOOL_NAME)
    tool.StartSizeX = 620
    tool.StartSizeY = 430
    tool.Caption = TOOL_NAME
    _STATE.clear()
    _STATE.update({
        "tool": tool,
        "controls": [],
    })

    main = ui.FBVBoxLayout()
    _attach_full(tool, "main", main)

    title = _label("MotionBuilderBridge", height=24)
    status = fb.FBMemo()
    status.ReadOnly = True
    status.Text = ""

    row_server = ui.FBHBoxLayout()
    row_server.Add(_button("Start", _on_start), 92)
    row_server.Add(_button("Stop", _on_stop), 92)
    row_server.Add(_button("Restart", _on_restart), 92)
    row_server.Add(_button("Refresh", _on_refresh), 92)

    row_tools = ui.FBHBoxLayout()
    row_tools.Add(_button("Copy Ping", _on_copy_ping), 110)
    row_tools.Add(_button("Copy Example", _on_copy_example), 120)
    row_tools.Add(_button("Smoke Test", _on_smoke_test), 115)
    row_tools.Add(_button("Open Docs", _on_open_docs), 105)

    command_label = _label("Command", height=18)
    command = fb.FBEdit()
    command.ReadOnly = False
    command.Text = ""

    log_label = _label("Log", height=18)
    log = fb.FBMemo()
    log.ReadOnly = True
    log.Text = ""

    main.Add(title, 28)
    main.Add(status, 96)
    main.Add(row_server, 34)
    main.Add(row_tools, 34)
    main.Add(command_label, 22)
    main.Add(command, 28)
    main.Add(log_label, 22)
    main.AddRelative(log, 1.0)

    _STATE.update({
        "status": status,
        "command": command,
        "log": log,
    })
    _STATE["controls"].extend([
        main,
        title,
        status,
        row_server,
        row_tools,
        command_label,
        command,
        log_label,
        log,
    ])

    _refresh_status()
    _log("Control panel loaded.")
    if show:
        fb.ShowTool(tool)
    return tool


def _attach_full(tool, name, control):
    x = fb.FBAddRegionParam(8, fb.FBAttachType.kFBAttachLeft, "")
    y = fb.FBAddRegionParam(8, fb.FBAttachType.kFBAttachTop, "")
    w = fb.FBAddRegionParam(-8, fb.FBAttachType.kFBAttachRight, "")
    h = fb.FBAddRegionParam(-8, fb.FBAttachType.kFBAttachBottom, "")
    tool.AddRegion(name, name, x, y, w, h)
    tool.SetControl(name, control)


def _label(text, height=22):
    label = fb.FBLabel()
    label.Caption = text
    label.WordWrap = False
    try:
        label.Justify = fb.FBTextJustify.kFBTextJustifyLeft
    except Exception:
        pass
    return label


def _button(text, callback):
    button = fb.FBButton()
    button.Caption = text
    button.Style = fb.FBButtonStyle.kFBPushButton
    button.OnClick.Add(callback)
    _STATE.setdefault("controls", []).append(button)
    return button


def _get_server():
    return mb_bridge_server.get_bridge()


def _server_running():
    server = _get_server()
    return bool(server is not None and getattr(server, "_running", False))


def _server_lines():
    server = _get_server()
    if server is None or not getattr(server, "_running", False):
        return [
            "Status: stopped",
            "TCP: not listening",
            "Discovery: not active",
            "Token: none",
        ]

    discovery = "off"
    if getattr(server, "discovery_enabled", False):
        discovery = "%s:%s" % (server.discovery_group, server.discovery_port)

    token = "enabled (%s)" % _fingerprint(server.token) if getattr(server, "token", "") else "none"
    return [
        "Status: running",
        "TCP: %s:%s" % (server.host, server.port),
        "Discovery: %s" % discovery,
        "Token: %s" % token,
    ]


def _refresh_status():
    status = _STATE.get("status")
    if status is not None:
        status.Text = "\n".join(_server_lines())
    _set_command(_ping_command())


def _set_command(command):
    edit = _STATE.get("command")
    if edit is not None:
        edit.Text = command


def _log(message):
    log = _STATE.get("log")
    if log is None:
        print("[MBBridgeTool] %s" % message)
        return
    existing = log.Text or ""
    line = "[MBBridgeTool] %s" % message
    log.Text = (existing + "\n" + line).strip()
    print(line)


def _copy_text(text):
    _set_command(text)
    try:
        proc = subprocess.Popen(
            ["clip.exe"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
        proc.communicate(text.encode("utf-16le"), timeout=2.0)
        if proc.returncode == 0:
            _log("Copied command to clipboard.")
            return True
    except Exception as exc:
        _log("Clipboard unavailable: %s" % exc)
    _log("Command is shown in the Command field.")
    return False


def _ping_command():
    server = _get_server()
    if server is not None and getattr(server, "_running", False):
        return 'python "%s" --endpoint %s:%s ping' % (_BRIDGE_CLI, server.host, server.port)
    return 'python "%s" ping' % _BRIDGE_CLI


def _example_command():
    return (
        'python "%s" exec "from mb_helpers import get_scene_info, dump_json; '
        'dump_json(get_scene_info())"'
    ) % _BRIDGE_CLI


def _fingerprint(token):
    if not token:
        return ""
    import hashlib
    return hashlib.sha1(token.encode("utf-8")).hexdigest()[:16]


def _safe_call(label, fn):
    try:
        result = fn()
        _refresh_status()
        return result
    except Exception:
        _log("%s failed:\n%s" % (label, traceback.format_exc()))
        _refresh_status()
        return None


def _on_start(control, event):
    def run():
        importlib.reload(mb_bridge_server)
        server = mb_bridge_server.start_bridge()
        _log("Started bridge on %s:%s." % (server.host, server.port))
    _safe_call("Start", run)


def _on_stop(control, event):
    def run():
        mb_bridge_server.stop_bridge()
        _log("Stopped bridge.")
    _safe_call("Stop", run)


def _on_restart(control, event):
    def run():
        mb_bridge_server.stop_bridge()
        importlib.reload(mb_bridge_server)
        server = mb_bridge_server.start_bridge()
        _log("Restarted bridge on %s:%s." % (server.host, server.port))
    _safe_call("Restart", run)


def _on_refresh(control, event):
    _refresh_status()
    _log("Refreshed status.")


def _on_copy_ping(control, event):
    _copy_text(_ping_command())


def _on_copy_example(control, event):
    _copy_text(_example_command())


def _on_smoke_test(control, event):
    def run():
        import mb_helpers
        importlib.reload(mb_helpers)
        info = mb_helpers.get_scene_info()
        _log("Smoke test ok: %s models, %s takes." % (
            info.get("model_count"),
            info.get("take_count"),
        ))
        _set_command(_example_command())
    _safe_call("Smoke Test", run)


def _on_open_docs(control, event):
    target = _API_DOC if os.path.isfile(_API_DOC) else _README
    try:
        os.startfile(target)
        _log("Opened docs: %s" % target)
    except Exception as exc:
        _log("Open docs failed: %s" % exc)


if __name__ in ("__main__", "__motionbuilder_bridge_exec__"):
    show_tool()
