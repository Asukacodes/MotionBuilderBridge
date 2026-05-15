# MotionBuilderBridge API Reference

Canonical copy:

```text
D:/LAFAN/MotionBuilderBridge/docs/motionbuilder-bridge-api.md
```

Common helpers:

```python
from mb_helpers import (
    get_scene_info,
    list_models,
    list_selected_models,
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
    list_animatable_properties,
    get_property_animation_keys,
    get_transform_curves,
    set_curve_key,
    set_model_transform_key,
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

Raw `pyfbsdk` is available as `fb` and `pyfbsdk`.

FPS helpers are read-only by default. They only modify the scene when a call
uses explicit flags such as `create_markers=True` or `apply=True`.

Do not call `open_file`, `save_file`, `new_scene`, `delete_model`, or other
destructive operations without explicit user confirmation.
