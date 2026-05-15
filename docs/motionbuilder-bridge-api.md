# MotionBuilderBridge API

Use helpers from scripts executed through `scripts/bridge.py`.

```python
from mb_helpers import get_scene_info, list_models, dump_json
dump_json(get_scene_info())
```

## Scene And Files

`get_scene_info()` returns scene path, MotionBuilder version, model count,
selected model count, character count, skeleton root count, take count, and
current take.

File operations:

```python
open_file(path, prompt=False)     # replaces current scene
merge_file(path, prompt=False)    # merges into current scene
save_file(path=None)              # saves current scene
new_scene(prompt=False)           # creates a new scene
```

`open_file`, `save_file`, and `new_scene` can destroy unsaved state. Use only
after explicit user confirmation.

## Models

```python
list_models(include_invisible=False)
list_selected_models()
find_models_by_name(pattern, exact=False, include_invisible=True)
find_models_by_class(class_name)
select_models(names, replace=True)
clear_selection()
create_null(name, translation=None, rotation=None, scaling=None, visible=True, select=True)
delete_model(model_name)
```

Model summaries include:

```json
{
  "name": "Hips",
  "class_name": "FBModelSkeleton",
  "translation": [0.0, 0.0, 0.0],
  "rotation": [0.0, 0.0, 0.0],
  "scaling": [1.0, 1.0, 1.0],
  "visible": true,
  "selected": false,
  "parent": null,
  "child_count": 3
}
```

Transforms:

```python
get_model_transform(model_name)
set_model_transform(model_name, translation=None, rotation=None, scaling=None)
get_model_children(model_name)
get_model_parent(model_name)
```

## Skeletons And Characters

```python
list_skeleton_roots()
get_skeleton_hierarchy(root_name=None)
list_body_nodes()
get_character_skeleton(character_name=None)
get_character_link_map(character_name=None, include_empty=False)
characterize_biped(character_name="Character", activate=True)
get_skeleton_pose(root_name=None, frame=None, space="local", include_matrix=False)
set_skeleton_pose(pose, frame=None, key=True, space="local")
list_characters()
get_current_character()
```

`get_skeleton_hierarchy` returns nested skeleton-like children with local
translation and rotation.

`get_character_skeleton` uses `FBCharacter.GetModel(FBBodyNodeId.*)` when a
HumanIK character exists. It returns `None` when the scene has no character.

`characterize_biped` maps standard biped skeleton names (`Hips`, `Spine`,
`LeftArm`, `RightFoot`, etc.) to Character `*Link` slots, calls
`SetCharacterizeOn(True)`, and can activate the character. It is intended for
standard HumanIK-style skeletons.

`get_skeleton_pose` and `set_skeleton_pose` use a simple agent-facing format:

```json
{
  "frame": 0,
  "space": "local",
  "bone_count": 2,
  "bones": [
    {
      "name": "Hips",
      "parent": null,
      "translation": [0.0, 90.0, 0.0],
      "rotation": [0.0, 0.0, 0.0],
      "scaling": [1.0, 1.0, 1.0]
    }
  ]
}
```

If `include_matrix=True`, each bone also includes a 16-float transform matrix.

## Animation

Common animatable model properties:

```python
list_animatable_properties(model_name)
get_property_animation_keys(model_name, property_name="Lcl Translation")
get_transform_curves(model_name)
set_curve_key(model_name, property_name, channel, frame, value)
set_vector_property_key(model_name, property_name, frame, value)
set_model_transform_key(model_name, frame, translation=None, rotation=None, scaling=None)
```

Example:

```python
from mb_helpers import *

create_null("Probe", translation=[0, 0, 0])
set_model_transform_key("Probe", 0, translation=[0, 0, 0])
set_model_transform_key("Probe", 10, translation=[100, 0, 0])
dump_json(get_property_animation_keys("Probe", "Lcl Translation"))
```

Set one scalar curve channel:

```python
set_curve_key("Probe", "Lcl Translation", "X", 12, 42.0)
```

Animation key output is grouped by channels:

```json
{
  "model": "Probe",
  "property": "Lcl Translation",
  "animated": true,
  "channels": [
    {"name": "X", "key_count": 2, "keys": [{"frame": 0, "value": 0.0}]}
  ]
}
```

## Playback And Takes

```python
get_playback_info()
set_playback_time(frame)
play()
stop()
pause()
list_takes()
get_current_take()
set_current_take(take_name)
new_take(take_name, duration_frames=100)
```

## Output

`dump_json(value)` prints compact UTF-8 JSON:

```powershell
python scripts\bridge.py exec "from mb_helpers import list_takes, dump_json; dump_json(list_takes())"
```

Raw `pyfbsdk` remains available as `fb` and `pyfbsdk` in bridge executions.
