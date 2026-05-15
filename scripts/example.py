"""
Example MotionBuilderBridge script.

Run from the repo root:
    python scripts/bridge.py exec-file scripts/example.py
"""

import json

from mb_helpers import (
    get_playback_info,
    get_skeleton_pose,
    list_animatable_properties,
    get_scene_info,
    list_characters,
    list_models,
    list_body_nodes,
    list_skeleton_roots,
    list_takes,
)

models = list_models(include_invisible=True)
first_model = models[0]["name"] if models else None
summary = {
    "scene": get_scene_info(),
    "playback": get_playback_info(),
    "takes": list_takes(),
    "characters": list_characters(),
    "skeleton_roots": list_skeleton_roots(),
    "body_nodes_sample": list_body_nodes()[:10],
    "skeleton_pose": get_skeleton_pose(),
    "first_model_animatable_properties": (
        list_animatable_properties(first_model) if first_model else []
    ),
    "models": models[:20],
}

print(json.dumps(summary, ensure_ascii=False, indent=2))
