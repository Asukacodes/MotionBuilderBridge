# MotionBuilderBridge

MotionBuilderBridge is a lightweight TCP bridge that lets external agents run
Python inside Autodesk MotionBuilder through `pyfbsdk`.

It mirrors the useful parts of UnrealBridge:

- length-prefixed JSON over TCP
- UDP multicast discovery, so the TCP port does not need to be hardcoded
- optional token auth for non-loopback binds
- persistent in-application Python namespace
- stdout/stderr capture per execution
- helper APIs for scene files, models, selection, skeletons, animation keys,
  characters, playback, and takes
- agent-facing skill/docs layout under `.claude/skills/motionbuilder-bridge`

## Quick Start

### 1. Start the bridge in MotionBuilder

Open MotionBuilder's Python Shell and run:

```python
exec(open(r"D:/LAFAN/MotionBuilderBridge/scripts/start_bridge.py").read())
```

Optional graphical control panel:

```python
exec(open(r"D:/LAFAN/MotionBuilderBridge/py/mb_bridge_tool.py").read())
```

The panel can start, stop, restart, refresh status, copy common commands, run a
smoke test, and open the API docs.

Expected log:

```text
[MBBridge] listening on 127.0.0.1:<ephemeral-port>
[MBBridge] discovery on 239.255.43.42:8997
```

The TCP port is OS-assigned by default. Clients discover it through UDP.

For a fixed TCP port:

```python
import sys
sys.path.insert(0, r"D:/LAFAN/MotionBuilderBridge/py")
from mb_bridge_server import start_bridge
start_bridge(port=8997)
```

### 2. Test the connection

```powershell
cd D:\LAFAN\MotionBuilderBridge
python scripts\bridge.py ping
```

### 3. Execute MotionBuilder Python

```powershell
python scripts\bridge.py exec "import pyfbsdk as fb; print(fb.FBSystem().Version)"
python scripts\bridge.py exec-file scripts\example.py
```

For multi-line one-shot scripts:

```powershell
@'
from mb_helpers import get_scene_info, dump_json
dump_json(get_scene_info())
'@ | python scripts\bridge.py exec --stdin
```

Stop the server:

```powershell
python scripts\bridge.py stop
```

## Protocol

TCP frames are UnrealBridge-style length-prefixed JSON:

```text
Request:  [4-byte big-endian length][JSON {"id":"...","script":"...","timeout":30,"token":"optional"}]
Response: [4-byte big-endian length][JSON {"id":"...","success":true,"output":"...","error":""}]
```

Inline commands:

| Command | Purpose |
|---|---|
| `ping` | TCP liveness check |
| `stop` | Stop the in-MotionBuilder bridge |

Discovery uses UDP multicast:

```text
Group: 239.255.43.42:8997
Probe:    {"v":1,"type":"probe","request_id":"...","filter":{"project":"*"}}
Response: {"v":1,"type":"response","app":"motionbuilder","tcp_bind":"127.0.0.1","tcp_port":...}
```

## Configuration

Server configuration precedence is explicit `start_bridge(...)` argument, then
environment variable, then default.

| Argument | Environment | Default | Effect |
|---|---|---|---|
| `host` | `MB_BRIDGE_BIND` | `127.0.0.1` | TCP bind interface |
| `port` | `MB_BRIDGE_PORT` | `0` | TCP port; `0` means OS-assigned |
| `token` | `MB_BRIDGE_TOKEN` | empty | Optional auth token |
| `discovery_group` | `MB_BRIDGE_DISCOVERY_GROUP` | `239.255.43.42:8997` | UDP discovery group |
| `discovery_enabled` | `MB_BRIDGE_DISCOVERY` | `1` | `0` disables UDP discovery |

If the server binds a non-loopback interface and no token was supplied, it
generates one and writes it to:

```text
D:\LAFAN\MotionBuilderBridge\Saved\MotionBuilderBridge\token.txt
```

Client overrides:

| CLI / Env | Purpose |
|---|---|
| `--endpoint HOST:PORT` / `MB_BRIDGE_ENDPOINT` | Skip discovery and connect directly |
| `--project NAME_OR_PATH` / `MB_BRIDGE_PROJECT` | Select one discovered instance |
| `--token TOKEN` / `MB_BRIDGE_TOKEN` | Auth token |
| `--discovery-group HOST:PORT` / `MB_BRIDGE_DISCOVERY_GROUP` | Override multicast group |

## Project Layout

```text
MotionBuilderBridge/
  py/
    mb_bridge_server.py      # In-MotionBuilder TCP server + discovery responder
    mb_bridge_protocol.py    # Length-prefixed JSON helpers
    mb_helpers.py            # Agent-friendly pyfbsdk wrappers
    mb_bridge_plugin.py      # Loader that auto-starts the bridge
    mb_bridge_tool.py        # Optional MotionBuilder UI control panel
  scripts/
    bridge.py                # External CLI client
    start_bridge.py          # Script to exec inside MotionBuilder
    example.py               # Read-only smoke script
  docs/
    motionbuilder-bridge-api.md
  .claude/skills/motionbuilder-bridge/
    SKILL.md
    scripts/bridge.py
```

## Packaging / Install For Other Agents

Create a clean zip:

```powershell
powershell -ExecutionPolicy Bypass -File tools\package_release.ps1
```

Install the agent skill globally for Claude and Codex:

```powershell
powershell -ExecutionPolicy Bypass -File tools\install_agent_skill.ps1 -Target Both
```

Optional MotionBuilder auto-start/control-panel loader:

```powershell
powershell -ExecutionPolicy Bypass -File tools\install_mobu_startup.ps1 -MotionBuilderVersion 2024 -AutoStartBridge -OpenPanel
```

See `docs/packaging.md` for the full distribution flow.

## Helper API Highlights

```python
from mb_helpers import (
    get_scene_info,
    list_models,
    create_null,
    select_models,
    list_skeleton_roots,
    get_skeleton_hierarchy,
    get_skeleton_pose,
    set_skeleton_pose,
    get_character_skeleton,
    get_character_link_map,
    characterize_biped,
    list_animatable_properties,
    get_property_animation_keys,
    get_transform_curves,
    set_curve_key,
    set_model_transform_key,
    dump_json,
)
```

See `docs/motionbuilder-bridge-api.md` for the current helper surface.

## Safety

- Read-only inspection is safe by default.
- Destructive operations such as deleting models, modifying files, or saving
  scenes should only be done after explicit user confirmation.
- `exec` runs on MotionBuilder's main Python/UI context. A long `while` loop or
  `time.sleep` inside one script can freeze the application until it returns.

## Requirements

- Autodesk MotionBuilder with Python 3 and `pyfbsdk`
- External client Python 3.9+
