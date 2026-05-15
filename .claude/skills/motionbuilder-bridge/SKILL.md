---
name: motionbuilder-bridge
description: Execute Python scripts inside a running Autodesk MotionBuilder session via MotionBuilderBridge. Use when the user asks to inspect, query, or automate MotionBuilder scenes, characters, skeletons, animation takes, playback, or pyfbsdk state.
allowed-tools: Bash Read Write Edit Glob Grep
---

# MotionBuilderBridge

Execute Python inside a running MotionBuilder session. The server is loaded into
MotionBuilder and the CLI auto-discovers it over UDP multicast
`239.255.43.42:8997`.

## Preconditions

If `bridge.py ping` cannot find an instance, check these in order:

1. MotionBuilder is running.
2. The bridge has been loaded in MotionBuilder Python Shell:

   ```python
   exec(open(r"D:/LAFAN/MotionBuilderBridge/scripts/start_bridge.py").read())
   ```

3. Optional control panel can be opened with:

   ```python
   exec(open(r"D:/LAFAN/MotionBuilderBridge/py/mb_bridge_tool.py").read())
   ```

4. Discovery is not blocked. If needed, use `--endpoint=127.0.0.1:<port>` with
   the port printed by `[MBBridge] listening on ...`.

## Bridge CLI

```bash
python "${CLAUDE_SKILL_DIR}/scripts/bridge.py" [options] <command> [args]
```

| Command | Purpose |
|---|---|
| `ping` | Check bridge connectivity |
| `exec "<code>"` | Execute inline Python |
| `exec --stdin` / `exec -` | Execute multi-line code from stdin |
| `exec-file <path>` | Execute a checked-in or reusable script file |
| `list-editors` | List discovered MotionBuilderBridge instances |
| `stop` | Stop the in-MotionBuilder server |

Useful flags: `--endpoint=host:port`, `--project=<name|path>`,
`--token=<secret>`, `--timeout=<seconds>`, `--json`.

## Workflow

1. Always run `ping` before doing real work.
2. Prefer `exec --stdin` for one-shot multi-line code.
3. Prefer `mb_helpers` before raw `pyfbsdk` for common scene queries.
4. Use `--json` or `mb_helpers.dump_json(...)` when the result will be parsed.
5. Do not delete, save, overwrite, or destructively modify scene data without
   explicit user confirmation.
6. Avoid `time.sleep` and long blocking loops inside one `exec`; scripts run in
   MotionBuilder's main Python/UI context.

## Helper API

```python
from mb_helpers import (
    get_scene_info,
    list_models,
    list_selected_models,
    find_models_by_name,
    create_null,
    select_models,
    get_model_transform,
    set_model_transform,
    list_skeleton_roots,
    get_skeleton_hierarchy,
    list_body_nodes,
    get_character_skeleton,
    get_character_link_map,
    characterize_biped,
    get_skeleton_pose,
    set_skeleton_pose,
    list_characters,
    list_animatable_properties,
    get_property_animation_keys,
    get_transform_curves,
    set_curve_key,
    set_model_transform_key,
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

Read `references/motionbuilder-bridge-api.md` before using less common helpers.

## Examples

```bash
python "${CLAUDE_SKILL_DIR}/scripts/bridge.py" exec "from mb_helpers import get_scene_info, dump_json; dump_json(get_scene_info())"
```

```bash
python "${CLAUDE_SKILL_DIR}/scripts/bridge.py" exec --stdin <<'EOF'
from mb_helpers import list_models, dump_json
dump_json(list_models(include_invisible=True)[:20])
EOF
```
