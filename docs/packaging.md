# Packaging MotionBuilderBridge

MotionBuilderBridge has two install targets:

1. MotionBuilder side: Python modules plus optional startup loader/control panel.
2. Agent side: a skill wrapper that lets Claude/Codex call `scripts/bridge.py`.

## Build A Zip

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File tools\package_release.ps1
```

Output:

```text
dist\MotionBuilderBridge.zip
```

The package excludes `__pycache__`, `.pyc`, and machine-local `bridge_home.txt`.

## Install For Claude/Codex

After extracting the zip:

```powershell
cd MotionBuilderBridge
powershell -ExecutionPolicy Bypass -File tools\install_agent_skill.ps1 -Target Both
```

This copies the skill to:

```text
%USERPROFILE%\.claude\skills\motionbuilder-bridge
%USERPROFILE%\.codex\skills\motionbuilder-bridge
```

It also writes `bridge_home.txt` inside each installed skill and sets the user
environment variable:

```text
MOTIONBUILDER_BRIDGE_HOME=<extracted repo path>
```

Restart Claude/Codex after installing so skills and environment variables are
reloaded.

## Install MotionBuilder Startup Loader

Optional:

```powershell
powershell -ExecutionPolicy Bypass -File tools\install_mobu_startup.ps1 -MotionBuilderVersion 2024 -Scope User -AutoStartBridge -OpenPanel
```

This writes user startup loaders to the common MotionBuilder user startup
locations:

```text
C:\Users\<user>\Documents\MB\2024\config\PythonStartup\MotionBuilderBridge_startup.py
C:\Users\<user>\AppData\Roaming\Autodesk\MotionBuilder\config\PythonStartup\MotionBuilderBridge_startup.py
C:\Users\<user>\Documents\MB\PythonStartup\MotionBuilderBridge_startup.py
```

Flags:

| Flag | Effect |
|---|---|
| `-Scope User` | Install to the current user's MotionBuilder startup folder; default and does not require admin |
| `-Scope System` | Install to `Program Files`; usually requires admin |
| `-Scope All` | Install both user and system startup loaders |
| `-AutoStartBridge` | Start TCP bridge automatically when MotionBuilder starts |
| `-OpenPanel` | Open the MotionBuilderBridge control panel automatically |

The startup loader always registers `MotionBuilderBridge Control Panel` as a
Python Tool, so it appears under MotionBuilder's `Python Tools` menu after
startup. `-OpenPanel` only controls whether the panel is shown immediately.

For system-wide installation:

```powershell
powershell -ExecutionPolicy Bypass -File tools\install_mobu_startup.ps1 -MotionBuilderVersion 2024 -Scope System -AutoStartBridge -OpenPanel
```

If Program Files requires admin rights, run PowerShell as Administrator or use
the default `-Scope User`.

## Manual MotionBuilder Load

Without startup installation, run in MotionBuilder Python Shell:

```python
exec(open(r"D:/LAFAN/MotionBuilderBridge/scripts/start_bridge.py").read())
```

Optional panel:

```python
exec(open(r"D:/LAFAN/MotionBuilderBridge/py/mb_bridge_tool.py").read())
```

## Smoke Test

With MotionBuilder open and bridge started:

```powershell
python scripts\bridge.py ping
python scripts\bridge.py exec "from mb_helpers import get_scene_info, dump_json; dump_json(get_scene_info())"
```

`bridge.py ping` first tries UDP discovery. If multicast discovery is delayed
or blocked, it automatically falls back to the endpoint cache written by the
in-MotionBuilder server:

```text
Saved\MotionBuilderBridge\endpoint.json
%LOCALAPPDATA%\MotionBuilderBridge\endpoint.json
```

From an installed Claude/Codex skill, the wrapper command is:

```powershell
python "%USERPROFILE%\.claude\skills\motionbuilder-bridge\scripts\bridge.py" ping
```

or:

```powershell
python "%USERPROFILE%\.codex\skills\motionbuilder-bridge\scripts\bridge.py" ping
```

## What Other Agents Need To Know

Agents should not redefine bridge functions. They should import helpers inside
MotionBuilder executions:

```python
from mb_helpers import get_skeleton_pose, characterize_biped, dump_json
dump_json(get_skeleton_pose())
```

Useful helper entry points:

```python
get_scene_info()
list_models(include_invisible=True)
characterize_biped("Character", activate=True)
get_character_link_map("Character")
get_skeleton_pose(root_name="Hips", frame=0)
set_skeleton_pose(pose, frame=10, key=True)
get_transform_curves("Hips")
set_curve_key("Hips", "Lcl Translation", "X", 12, 42.0)
```
