# AGENTS.md

This repository provides a MotionBuilder counterpart to UnrealBridge. It lets
Codex/Claude-style agents execute Python inside Autodesk MotionBuilder through
`pyfbsdk`.

## Project Overview

MotionBuilderBridge consists of:

- `py/mb_bridge_server.py` - in-MotionBuilder TCP server plus UDP discovery
- `py/mb_helpers.py` - high-level scene/model/selection/skeleton/animation helpers over `pyfbsdk`
- `py/mb_fps_helpers.py` - FPS animation helpers for weapon rig suggestions, aim offsets, cover poses, locomotion-loop checks, weapon switch planning, and retarget mapping
- `py/mb_bridge_tool.py` - optional MoBu UI for start/stop/status/smoke-test
- `scripts/bridge.py` - external CLI client
- `scripts/start_bridge.py` - script to load inside MotionBuilder
- `.claude/skills/motionbuilder-bridge/` - agent-facing skill wrapper

## Key Commands

Start the bridge in MotionBuilder Python Shell:

```python
exec(open(r"D:/LAFAN/MotionBuilderBridge/scripts/start_bridge.py").read())
```

Open the optional MotionBuilder control panel:

```python
exec(open(r"D:/LAFAN/MotionBuilderBridge/py/mb_bridge_tool.py").read())
```

Test connection from PowerShell:

```powershell
cd D:\LAFAN\MotionBuilderBridge
python scripts\bridge.py ping
```

Execute Python in MotionBuilder:

```powershell
python scripts\bridge.py exec "from mb_helpers import get_scene_info, dump_json; dump_json(get_scene_info())"
python scripts\bridge.py exec-file scripts\example.py
```

Exercise animation helpers:

```powershell
@'
from mb_helpers import *
create_null("Probe", translation=[0, 0, 0])
set_model_transform_key("Probe", 0, translation=[0, 0, 0])
set_model_transform_key("Probe", 10, translation=[100, 0, 0])
dump_json(get_property_animation_keys("Probe", "Lcl Translation"))
'@ | python scripts\bridge.py exec --stdin
```

Exercise FPS helpers:

```powershell
python scripts\bridge.py exec "from mb_fps_helpers import suggest_weapon_rig; from mb_helpers import dump_json; dump_json(suggest_weapon_rig('assault_rifle'))"
```

Read/write skeleton pose:

```powershell
@'
from mb_helpers import get_skeleton_pose, set_skeleton_pose, dump_json
pose = get_skeleton_pose(root_name="Hips", frame=0)
dump_json(pose)
'@ | python scripts\bridge.py exec --stdin
```

For multi-line one-shot scripts, prefer stdin:

```powershell
@'
from mb_helpers import list_models, dump_json
dump_json(list_models(include_invisible=True)[:10])
'@ | python scripts\bridge.py exec --stdin
```

Stop bridge:

```powershell
python scripts\bridge.py stop
```

## Architecture

### TCP Protocol

Length-prefixed JSON over TCP. The TCP port is OS-assigned by default; clients
discover it through UDP.

```text
Request:  [4 bytes big-endian length][JSON {"id":"...","script":"...","timeout":30,"token":"optional"}]
Response: [4 bytes big-endian length][JSON {"id":"...","success":true,"output":"...","error":""}]
```

Special commands:

- `{"id":"...","command":"ping"}` -> `pong`
- `{"id":"...","command":"stop"}` -> stops the server

### Discovery Protocol

UDP multicast on `239.255.43.42:8997`.

```text
Probe:
{"v":1,"type":"probe","request_id":"<uuid>","filter":{"project":"<name|path|*>"}}

Response:
{"v":1,"type":"response","app":"motionbuilder","request_id":"<uuid>","pid":...,
 "project":"...","project_path":"...","engine_version":"...",
 "tcp_bind":"127.0.0.1","tcp_port":...,"token_fingerprint":"...","token_path":"..."}
```

### Server Configuration

Precedence: explicit `start_bridge(...)` argument > environment variable >
default.

| Argument | Env | Default | Effect |
|---|---|---|---|
| `host` | `MB_BRIDGE_BIND` | `127.0.0.1` | TCP bind address |
| `port` | `MB_BRIDGE_PORT` | `0` | TCP port, `0` means OS-assigned |
| `token` | `MB_BRIDGE_TOKEN` | empty | Optional auth token |
| `discovery_group` | `MB_BRIDGE_DISCOVERY_GROUP` | `239.255.43.42:8997` | UDP multicast group |
| `discovery_enabled` | `MB_BRIDGE_DISCOVERY` | `1` | `0` disables discovery |

If binding non-loopback without a token, the server generates one and writes it
to `Saved/MotionBuilderBridge/token.txt`.

## Development Workflow

Edit Python files directly under `py/` and reload in MotionBuilder:

```python
import sys, importlib
sys.path.insert(0, r"D:/LAFAN/MotionBuilderBridge/py")
import mb_bridge_server
importlib.reload(mb_bridge_server)
mb_bridge_server.start_bridge()
```

After changes:

```powershell
python scripts\bridge.py ping
python scripts\bridge.py exec "from mb_helpers import get_scene_info, dump_json; dump_json(get_scene_info())"
```

## Safety Rules

- Do not delete models, save scenes, overwrite files, or perform destructive
  operations without explicit user confirmation.
- Prefer read-only inspection helpers first.
- `exec` runs in MotionBuilder's main Python/UI context. Avoid long blocking
  loops and `time.sleep` inside a single request.
- Show full tracebacks from bridge failures; do not silently retry destructive
  operations.
