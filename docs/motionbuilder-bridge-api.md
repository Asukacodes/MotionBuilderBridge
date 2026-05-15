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

## FPS Animation Helpers

FPS helpers live in `mb_fps_helpers`. They are designed for agent workflows
around weapon rigs, aim offsets, cover poses, locomotion cycles, weapon-switch
alignment, and retarget planning.

```python
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

### Weapon Rig Suggestions

```python
suggest_weapon_rig(
    weapon_type="assault_rifle",
    character_name=None,
    weapon_model=None,
    create_markers=False,
)
```

Returns recommended right/left hand IK target transforms, source hand/weapon
data, grip-pose offsets, and suggested constraints. If `create_markers=True`,
the helper creates or updates two `FBModelNull` markers named
`FPS_RightHandIK` and `FPS_LeftHandIK`.

Read-only example:

```powershell
python scripts\bridge.py exec "from mb_fps_helpers import suggest_weapon_rig; from mb_helpers import dump_json; dump_json(suggest_weapon_rig('assault_rifle'))"
```

### Aim Offset Pose Sets

```python
generate_aim_offset_set(
    base_pose=None,
    yaw_range=(-45, 45),
    pitch_range=(-30, 30),
    granularity=15,
    apply=False,
)
```

Generates a yaw/pitch grid by distributing rotation across spine, neck, and
head. It returns pose dictionaries compatible with `set_skeleton_pose`.
`apply=False` is read-only. With `apply=True`, poses are keyed into the current
take starting at `start_frame`.

Smoothness check:

```python
aim = generate_aim_offset_set(granularity=15)
report = check_aim_offset_smoothness(aim, max_rotation_delta=20.0)
```

### Cover Pose Variants

```python
generate_cover_variants(
    reference_pose=None,
    cover_types=["left_peek", "right_peek", "crouch", "prone"],
    apply=False,
)
```

Known cover types are `left_peek`, `right_peek`, `crouch`, `prone`,
`left_blind_fire`, and `right_blind_fire`. The result is intended as blocking
poses for artist review and polish.

### Locomotion Loop Checks

```python
analyze_locomotion_loop(
    root_name=None,
    start_frame=None,
    end_frame=None,
    in_place=True,
)
```

Reports endpoint pose seams and simple foot-slide candidates. When
`start_frame` / `end_frame` are omitted, the current playback loop range is
used; if no useful range exists, it checks a 30-frame window.

```python
fix_locomotion_loop(..., apply=False)
```

With `apply=False`, this only returns analysis. With `apply=True`, it keys the
start pose onto the end frame as a conservative loop endpoint patch.

### Weapon Switch And Retarget Planning

```python
auto_align_weapon_switch(
    weapon_anim,
    character_anim,
    sync_points=["draw", "holster"],
)
```

Builds a frame-offset plan from sync-point dictionaries.

```python
retarget_with_style(source_anim, source_skeleton, target_skeleton)
```

Returns a name-normalized bone map, estimated scale ratio, and style-preserving
retarget policy. Use it as an agent-side planning step before applying HumanIK
or manual curve edits.

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
