# MotionBuilderBridge

MotionBuilderBridge lets agents execute Python inside Autodesk MotionBuilder via
a local TCP bridge and the `pyfbsdk` API.

## Start Bridge

In MotionBuilder Python Shell:

```python
exec(open(r"D:/LAFAN/MotionBuilderBridge/scripts/start_bridge.py").read())
```

Optional graphical control panel:

```python
exec(open(r"D:/LAFAN/MotionBuilderBridge/py/mb_bridge_tool.py").read())
```

The panel exposes Start, Stop, Restart, Refresh, Copy Ping, Copy Example,
Smoke Test, and Open Docs.

The bridge binds TCP to `127.0.0.1` with an OS-assigned port by default and
advertises it through UDP discovery on `239.255.43.42:8997`.

## Client Commands

```powershell
cd D:\LAFAN\MotionBuilderBridge
python scripts\bridge.py ping
python scripts\bridge.py exec "print('hello')"
python scripts\bridge.py exec --stdin
python scripts\bridge.py exec-file scripts\example.py
python scripts\bridge.py list-editors
python scripts\bridge.py stop
```

Direct endpoint fallback:

```powershell
python scripts\bridge.py --endpoint 127.0.0.1:8997 ping
```

## Workflow Rules

1. Always run `bridge.py ping` first.
2. Prefer `exec --stdin` for multi-line one-shot scripts.
3. Use `exec-file` only for scripts that should stay in the repo and be rerun.
4. Prefer `mb_helpers` before raw `pyfbsdk` for common operations.
5. Use `mb_fps_helpers` for FPS animation workflows before writing custom rig,
   pose, locomotion, or retarget scripts.
6. Do not delete, save, overwrite, or destructively modify scene data without
   explicit user confirmation.
7. Avoid `time.sleep` and long blocking loops inside one `exec`; it runs in
   MotionBuilder's main Python/UI context.

## Helpers

```python
from mb_helpers import (
    get_scene_info,
    list_models,
    find_models_by_name,
    get_model_transform,
    set_model_transform,
    list_characters,
    get_playback_info,
    set_playback_time,
    list_takes,
    dump_json,
)

from mb_fps_helpers import (
    get_fps_rig_context,
    suggest_weapon_rig,
    generate_aim_offset_set,
    check_aim_offset_smoothness,
    generate_cover_variants,
    analyze_locomotion_loop,
    fix_locomotion_loop,
    auto_align_weapon_switch,
    retarget_with_style,
)
```

## Protocol

TCP frames are 4-byte big-endian length plus UTF-8 JSON:

```text
Request:  {"id":"...","script":"...","timeout":30,"token":"optional"}
Response: {"id":"...","success":true,"output":"...","error":""}
```

Discovery:

```text
UDP group: 239.255.43.42:8997
Probe:     {"v":1,"type":"probe","request_id":"...","filter":{"project":"*"}}
Response:  {"v":1,"type":"response","app":"motionbuilder","tcp_bind":"127.0.0.1","tcp_port":...}
```
