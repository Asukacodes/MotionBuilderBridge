"""
FPS animation helpers for MotionBuilderBridge.

These functions are intentionally heuristic. They give agents a stable,
JSON-friendly layer for common FPS animation work such as weapon grip setup,
aim-offset pose generation, cover pose variants, locomotion-loop checks, weapon
switch alignment planning, and skeleton retarget mapping.

By default these helpers do not write scene data. Functions that can write use
explicit flags such as apply=True or create_markers=True.
"""

import copy
import math
import re

import pyfbsdk as fb

import mb_helpers

__all__ = [
    "get_fps_rig_context",
    "suggest_weapon_rig",
    "generate_aim_offset_set",
    "check_aim_offset_smoothness",
    "generate_cover_variants",
    "analyze_locomotion_loop",
    "fix_locomotion_loop",
    "auto_align_weapon_switch",
    "retarget_with_style",
]


HAND_LINKS = {
    "right": "RightHandLink",
    "left": "LeftHandLink",
}

BODY_FALLBACKS = {
    "right_hand": ["RightHand", "right_hand", "hand_r", "r_hand", "mixamorig:RightHand"],
    "left_hand": ["LeftHand", "left_hand", "hand_l", "l_hand", "mixamorig:LeftHand"],
    "right_forearm": ["RightForeArm", "RightForearm", "lowerarm_r", "r_forearm"],
    "left_forearm": ["LeftForeArm", "LeftForearm", "lowerarm_l", "l_forearm"],
    "hips": ["Hips", "Pelvis", "pelvis", "Root"],
    "head": ["Head", "head"],
    "spine": ["Spine", "Spine1", "Spine2", "spine_01", "spine_02", "spine_03"],
    "left_foot": ["LeftFoot", "foot_l", "l_foot"],
    "right_foot": ["RightFoot", "foot_r", "r_foot"],
}

WEAPON_PROFILES = {
    "assault_rifle": {
        "aliases": ["rifle", "ar", "carbine"],
        "right_grip_offset": [0.0, 0.0, 0.0],
        "left_grip_offset": [-28.0, -3.0, 22.0],
        "right_rotation_offset": [0.0, 0.0, 0.0],
        "left_rotation_offset": [0.0, -8.0, 0.0],
        "spine_pitch": -4.0,
        "elbow_out": 8.0,
        "notes": "Two-hand long-gun profile with support hand forward on the fore-end.",
    },
    "smg": {
        "aliases": ["submachine_gun", "pdw"],
        "right_grip_offset": [0.0, 0.0, 0.0],
        "left_grip_offset": [-20.0, -2.0, 16.0],
        "right_rotation_offset": [0.0, 0.0, 0.0],
        "left_rotation_offset": [0.0, -6.0, 0.0],
        "spine_pitch": -3.0,
        "elbow_out": 7.0,
        "notes": "Compact two-hand weapon profile.",
    },
    "pistol": {
        "aliases": ["handgun"],
        "right_grip_offset": [0.0, 0.0, 0.0],
        "left_grip_offset": [-7.0, -2.0, 7.0],
        "right_rotation_offset": [0.0, 0.0, 0.0],
        "left_rotation_offset": [0.0, -3.0, 0.0],
        "spine_pitch": -2.0,
        "elbow_out": 4.0,
        "notes": "Close two-hand pistol profile.",
    },
    "shotgun": {
        "aliases": ["pump_shotgun"],
        "right_grip_offset": [0.0, 0.0, 0.0],
        "left_grip_offset": [-36.0, -4.0, 26.0],
        "right_rotation_offset": [0.0, 0.0, 0.0],
        "left_rotation_offset": [0.0, -10.0, 0.0],
        "spine_pitch": -5.0,
        "elbow_out": 9.0,
        "notes": "Long weapon profile with far support-hand placement.",
    },
}

AIM_DISTRIBUTION = [
    ("Spine", 0.20),
    ("Spine1", 0.25),
    ("Spine2", 0.20),
    ("Neck", 0.15),
    ("Head", 0.20),
]

COVER_VARIANT_OFFSETS = {
    "left_peek": {
        "root_translation": [-18.0, 0.0, 0.0],
        "rotation_offsets": {
            "Hips": [0.0, -8.0, -4.0],
            "Spine": [0.0, -10.0, -6.0],
            "Spine1": [0.0, -12.0, -8.0],
            "Spine2": [0.0, -12.0, -7.0],
            "Head": [0.0, -8.0, -3.0],
        },
    },
    "right_peek": {
        "root_translation": [18.0, 0.0, 0.0],
        "rotation_offsets": {
            "Hips": [0.0, 8.0, 4.0],
            "Spine": [0.0, 10.0, 6.0],
            "Spine1": [0.0, 12.0, 8.0],
            "Spine2": [0.0, 12.0, 7.0],
            "Head": [0.0, 8.0, 3.0],
        },
    },
    "crouch": {
        "root_translation": [0.0, -35.0, 0.0],
        "rotation_offsets": {
            "Hips": [-8.0, 0.0, 0.0],
            "LeftUpLeg": [18.0, 0.0, 0.0],
            "RightUpLeg": [18.0, 0.0, 0.0],
            "LeftLeg": [-28.0, 0.0, 0.0],
            "RightLeg": [-28.0, 0.0, 0.0],
            "Spine": [8.0, 0.0, 0.0],
            "Spine1": [6.0, 0.0, 0.0],
        },
    },
    "prone": {
        "root_translation": [0.0, -80.0, 10.0],
        "rotation_offsets": {
            "Hips": [55.0, 0.0, 0.0],
            "Spine": [-25.0, 0.0, 0.0],
            "Spine1": [-20.0, 0.0, 0.0],
            "Spine2": [-15.0, 0.0, 0.0],
            "Head": [-12.0, 0.0, 0.0],
        },
    },
    "left_blind_fire": {
        "root_translation": [-12.0, 0.0, 0.0],
        "rotation_offsets": {
            "RightArm": [0.0, -30.0, -20.0],
            "RightForeArm": [0.0, -22.0, 0.0],
            "LeftArm": [0.0, -18.0, -12.0],
            "LeftForeArm": [0.0, -12.0, 0.0],
        },
    },
    "right_blind_fire": {
        "root_translation": [12.0, 0.0, 0.0],
        "rotation_offsets": {
            "RightArm": [0.0, 30.0, 20.0],
            "RightForeArm": [0.0, 22.0, 0.0],
            "LeftArm": [0.0, 18.0, 12.0],
            "LeftForeArm": [0.0, 12.0, 0.0],
        },
    },
}


def get_fps_rig_context(character_name=None, weapon_model=None, root_name=None):
    """Return scene, character, hand, weapon, and pose data for FPS work."""
    character = mb_helpers.get_character_link_map(character_name, include_empty=False)
    hands = {
        "right": _body_model(character_name, "right_hand"),
        "left": _body_model(character_name, "left_hand"),
        "right_forearm": _body_model(character_name, "right_forearm"),
        "left_forearm": _body_model(character_name, "left_forearm"),
    }
    resolved_weapon = _resolve_model(weapon_model) or _selected_non_skeleton_model()
    pose = mb_helpers.get_skeleton_pose(root_name=root_name)

    return {
        "scene": mb_helpers.get_scene_info(),
        "character": character,
        "hands": {key: _model_entry(value) for key, value in hands.items()},
        "weapon": _model_entry(resolved_weapon),
        "pose": pose,
        "warnings": _context_warnings(character, hands, resolved_weapon),
    }


def suggest_weapon_rig(
    weapon_type="assault_rifle",
    character_name=None,
    weapon_model=None,
    create_markers=False,
    marker_prefix="FPS",
):
    """Suggest hand IK targets, grip pose offsets, and setup notes for a weapon."""
    profile_name, profile = _weapon_profile(weapon_type)
    right_hand = _body_model(character_name, "right_hand")
    left_hand = _body_model(character_name, "left_hand")
    right_forearm = _body_model(character_name, "right_forearm")
    left_forearm = _body_model(character_name, "left_forearm")
    weapon = _resolve_model(weapon_model) or _selected_non_skeleton_model()

    base_translation = None
    base_rotation = None
    source = "profile"
    if weapon is not None:
        base_translation = _get_world_vector(weapon, "translation")
        base_rotation = _get_world_vector(weapon, "rotation")
        source = "weapon_model"
    elif right_hand is not None:
        base_translation = _get_world_vector(right_hand, "translation")
        base_rotation = _get_world_vector(right_hand, "rotation")
        source = "right_hand"

    if base_translation is None:
        base_translation = [0.0, 0.0, 0.0]
    if base_rotation is None:
        base_rotation = [0.0, 0.0, 0.0]

    right_target = {
        "name": "%s_RightHandIK" % marker_prefix,
        "translation": _add3(base_translation, profile["right_grip_offset"]),
        "rotation": _add3(base_rotation, profile["right_rotation_offset"]),
        "source": source,
    }
    left_target = {
        "name": "%s_LeftHandIK" % marker_prefix,
        "translation": _add3(base_translation, profile["left_grip_offset"]),
        "rotation": _add3(base_rotation, profile["left_rotation_offset"]),
        "source": source,
    }

    created = []
    if create_markers:
        created.append(_create_or_update_null(right_target["name"], right_target))
        created.append(_create_or_update_null(left_target["name"], left_target))

    warnings = []
    if right_hand is None:
        warnings.append("Right hand bone was not found; right IK target is profile-only.")
    if left_hand is None:
        warnings.append("Left hand bone was not found; left IK target is profile-only.")
    if weapon is None:
        warnings.append("Weapon model was not found or selected; offsets are anchored to the right hand/profile.")

    return {
        "weapon_type": profile_name,
        "requested_weapon_type": weapon_type,
        "weapon_model": _model_entry(weapon),
        "character": _character_name(character_name),
        "ik_targets": {
            "right_hand": right_target,
            "left_hand": left_target,
        },
        "source_bones": {
            "right_hand": _model_entry(right_hand),
            "left_hand": _model_entry(left_hand),
            "right_forearm": _model_entry(right_forearm),
            "left_forearm": _model_entry(left_forearm),
        },
        "grip_pose": {
            "spine_pitch_offset": profile["spine_pitch"],
            "elbow_out_offset": profile["elbow_out"],
            "bone_rotation_offsets": {
                "Spine": [profile["spine_pitch"], 0.0, 0.0],
                "RightForeArm": [0.0, profile["elbow_out"], 0.0],
                "LeftForeArm": [0.0, -profile["elbow_out"], 0.0],
            },
        },
        "constraints": [
            {"type": "parent", "source": right_target["name"], "target": "RightHand"},
            {"type": "parent", "source": left_target["name"], "target": "LeftHand"},
            {"type": "aim", "source": "weapon_forward", "target": "camera_forward"},
        ],
        "created_markers": created,
        "notes": profile["notes"],
        "warnings": warnings,
    }


def generate_aim_offset_set(
    base_pose=None,
    yaw_range=(-45, 45),
    pitch_range=(-30, 30),
    granularity=15,
    character_name=None,
    root_name=None,
    apply=False,
    start_frame=0,
    frame_step=1,
    yaw_axis=1,
    pitch_axis=0,
):
    """Generate a grid of upper-body aim-offset poses.

    The return value is a list of pose records. When apply=True, the generated
    poses are keyed into the current take starting at start_frame.
    """
    if base_pose is None:
        base_pose = mb_helpers.get_skeleton_pose(root_name=root_name)

    yaw_values = _inclusive_range(yaw_range[0], yaw_range[1], granularity)
    pitch_values = _inclusive_range(pitch_range[0], pitch_range[1], granularity)

    result = []
    frame = int(start_frame)
    for pitch in pitch_values:
        for yaw in yaw_values:
            pose = _copy_pose(base_pose)
            pose["fps_meta"] = {
                "type": "aim_offset",
                "yaw": yaw,
                "pitch": pitch,
                "yaw_axis": yaw_axis,
                "pitch_axis": pitch_axis,
            }
            _apply_aim_offsets(pose, yaw, pitch, yaw_axis=yaw_axis, pitch_axis=pitch_axis)
            record = {
                "name": _aim_pose_name(yaw, pitch),
                "yaw": yaw,
                "pitch": pitch,
                "frame": frame if apply else None,
                "pose": pose,
            }
            if apply:
                mb_helpers.set_skeleton_pose(pose, frame=frame, key=True)
                frame += int(frame_step)
            result.append(record)

    return {
        "character": _character_name(character_name),
        "yaw_values": yaw_values,
        "pitch_values": pitch_values,
        "pose_count": len(result),
        "applied": bool(apply),
        "poses": result,
        "notes": [
            "Generated poses distribute yaw/pitch across spine, neck, and head.",
            "Axis defaults assume Euler X=pitch and Y=yaw; adjust yaw_axis/pitch_axis for your rig.",
        ],
    }


def check_aim_offset_smoothness(aim_set, max_rotation_delta=20.0):
    """Check neighboring aim poses for large rotation jumps."""
    poses = aim_set.get("poses", aim_set) if isinstance(aim_set, dict) else aim_set
    lookup = {}
    for item in poses:
        lookup[(item.get("yaw"), item.get("pitch"))] = item

    issues = []
    keys = sorted(lookup.keys(), key=lambda k: (k[1], k[0]))
    for yaw, pitch in keys:
        current = lookup[(yaw, pitch)]
        for other_key in _neighbor_keys((yaw, pitch), keys):
            other = lookup[other_key]
            delta = _pose_rotation_delta(current.get("pose"), other.get("pose"))
            if delta["max_delta"] > float(max_rotation_delta):
                issues.append({
                    "from": current.get("name"),
                    "to": other.get("name"),
                    "max_delta": delta["max_delta"],
                    "bone": delta["bone"],
                    "message": "Neighboring aim poses have a large rotation jump.",
                })

    return {
        "issue_count": len(issues),
        "issues": issues,
        "max_rotation_delta": float(max_rotation_delta),
    }


def generate_cover_variants(
    reference_pose=None,
    cover_types=None,
    root_name=None,
    apply=False,
    start_frame=0,
    frame_step=10,
):
    """Generate a family of cover-pose variants from one reference pose."""
    if reference_pose is None:
        reference_pose = mb_helpers.get_skeleton_pose(root_name=root_name)
    if cover_types is None:
        cover_types = ["left_peek", "right_peek", "crouch", "prone"]

    variants = {}
    frame = int(start_frame)
    for cover_type in cover_types:
        offsets = COVER_VARIANT_OFFSETS.get(str(cover_type))
        if offsets is None:
            variants[str(cover_type)] = {
                "error": "unknown cover type",
                "known_cover_types": sorted(COVER_VARIANT_OFFSETS.keys()),
            }
            continue

        pose = _copy_pose(reference_pose)
        pose["fps_meta"] = {
            "type": "cover_variant",
            "cover_type": str(cover_type),
        }
        _apply_cover_offsets(pose, offsets)
        record = {"pose": pose, "frame": frame if apply else None}
        if apply:
            mb_helpers.set_skeleton_pose(pose, frame=frame, key=True)
            frame += int(frame_step)
        variants[str(cover_type)] = record

    return {
        "applied": bool(apply),
        "variant_count": len([v for v in variants.values() if "pose" in v]),
        "variants": variants,
        "notes": [
            "Cover variants are style-preserving heuristic offsets from the reference pose.",
            "Use them as blocking poses, then polish contact, silhouette, and weapon clearance.",
        ],
    }


def analyze_locomotion_loop(
    root_name=None,
    start_frame=None,
    end_frame=None,
    foot_names=None,
    position_tolerance=1.0,
    rotation_tolerance=2.0,
    contact_height_tolerance=3.0,
    foot_slide_tolerance=2.5,
    frame_step=1,
    in_place=True,
):
    """Detect common locomotion-loop seam and foot-slide issues."""
    frames = _resolve_frame_range(start_frame, end_frame)
    start_frame, end_frame = frames["start_frame"], frames["end_frame"]
    if foot_names is None:
        foot_names = ["LeftFoot", "RightFoot"]

    start_pose = mb_helpers.get_skeleton_pose(root_name=root_name, frame=start_frame)
    end_pose = mb_helpers.get_skeleton_pose(root_name=root_name, frame=end_frame)
    seam = _compare_pose_endpoints(start_pose, end_pose)

    issues = []
    for item in seam["bone_deltas"]:
        name = item["name"]
        is_rootish = _norm_name(name) in ("root", "hips", "pelvis")
        if in_place and is_rootish and item["translation_delta"] > float(position_tolerance):
            issues.append({
                "type": "root_translation_seam",
                "bone": name,
                "delta": item["translation_delta"],
                "message": "Root/hips translation does not loop for an in-place cycle.",
            })
        if item["rotation_delta"] > float(rotation_tolerance) and _is_important_loop_bone(name):
            issues.append({
                "type": "rotation_seam",
                "bone": name,
                "delta": item["rotation_delta"],
                "message": "Important bone rotation differs between loop endpoints.",
            })

    foot_reports = []
    for foot_name in foot_names:
        report = _analyze_foot_slide(
            foot_name,
            start_frame,
            end_frame,
            int(frame_step),
            float(contact_height_tolerance),
            float(foot_slide_tolerance),
        )
        foot_reports.append(report)
        for slide in report.get("slides", []):
            issues.append({
                "type": "foot_slide",
                "bone": report["foot"],
                "frame": slide["frame"],
                "delta": slide["delta"],
                "message": "Foot appears to move while near contact height.",
            })

    return {
        "start_frame": start_frame,
        "end_frame": end_frame,
        "in_place": bool(in_place),
        "issue_count": len(issues),
        "issues": issues,
        "seam": seam,
        "feet": foot_reports,
    }


def fix_locomotion_loop(
    root_name=None,
    start_frame=None,
    end_frame=None,
    apply=False,
    position_tolerance=1.0,
    rotation_tolerance=2.0,
    in_place=True,
):
    """Analyze and optionally patch a loop endpoint by matching it to frame 0.

    apply=False returns a report only. apply=True keys the start pose onto the
    end frame. This is a conservative seam patch, not a replacement for final
    animation polish.
    """
    report = analyze_locomotion_loop(
        root_name=root_name,
        start_frame=start_frame,
        end_frame=end_frame,
        position_tolerance=position_tolerance,
        rotation_tolerance=rotation_tolerance,
        in_place=in_place,
    )

    fixes = []
    if apply and report["issue_count"]:
        start_pose = mb_helpers.get_skeleton_pose(root_name=root_name, frame=report["start_frame"])
        mb_helpers.set_skeleton_pose(start_pose, frame=report["end_frame"], key=True)
        fixes.append({
            "type": "endpoint_match",
            "frame": report["end_frame"],
            "message": "Keyed the start pose onto the loop end frame.",
        })

    return {
        "analysis": report,
        "applied": bool(apply),
        "fixes_applied": fixes,
        "remaining_work": [
            "Review root motion policy: in-place cycles should close; root-motion cycles may intentionally translate.",
            "Polish foot contact frames manually if slide issues remain.",
        ],
    }


def auto_align_weapon_switch(
    weapon_anim,
    character_anim,
    sync_points=None,
    hand="right",
):
    """Build an alignment plan for weapon switch, draw, holster, or reload clips."""
    if sync_points is None:
        sync_points = ["draw", "holster"]

    weapon_points = _sync_point_map(weapon_anim)
    character_points = _sync_point_map(character_anim)
    alignments = []
    missing = []

    for name in sync_points:
        if name not in weapon_points or name not in character_points:
            missing.append(name)
            continue
        weapon_frame = weapon_points[name]["frame"]
        char_frame = character_points[name]["frame"]
        alignments.append({
            "sync_point": name,
            "weapon_frame": weapon_frame,
            "character_frame": char_frame,
            "frame_offset": int(char_frame) - int(weapon_frame),
            "weapon_marker": weapon_points[name].get("marker"),
            "character_marker": character_points[name].get("marker"),
        })

    return {
        "hand": hand,
        "sync_points": list(sync_points),
        "alignments": alignments,
        "missing_sync_points": missing,
        "recommended_steps": [
            "Shift weapon animation by frame_offset so sync markers land on the same frame.",
            "Constrain %s hand IK to the weapon grip marker at each sync point." % hand,
            "Blend constraints over 2-4 frames around draw/holster to avoid snapping.",
            "Key upper-body layer weight separately from lower-body locomotion.",
        ],
    }


def retarget_with_style(source_anim, source_skeleton, target_skeleton):
    """Suggest a style-preserving retarget map and scale policy."""
    source_bones = _skeleton_bone_list(source_skeleton)
    target_bones = _skeleton_bone_list(target_skeleton)
    target_by_norm = {_norm_name(item.get("name", "")): item for item in target_bones}

    mapping = []
    unmapped = []
    for src in source_bones:
        src_name = src.get("name", "")
        target = _best_target_bone(src_name, target_by_norm)
        if target is None:
            unmapped.append(src_name)
            continue
        mapping.append({
            "source": src_name,
            "target": target.get("name", ""),
            "confidence": _mapping_confidence(src_name, target.get("name", "")),
        })

    scale = _estimate_skeleton_scale(source_bones, target_bones)
    return {
        "bone_map": mapping,
        "unmapped_source_bones": unmapped,
        "scale": scale,
        "style_policy": {
            "preserve_timing": True,
            "preserve_contact_frames": True,
            "scale_root_translation": scale["ratio"],
            "scale_hand_reach": scale["ratio"],
            "keep_weapon_space": True,
        },
        "recommended_steps": [
            "Characterize both skeletons when possible, then use HumanIK as the first retarget pass.",
            "Scale root and hand reach by the estimated height ratio.",
            "Run locomotion-loop and weapon-grip checks after retargeting.",
        ],
        "source_anim_summary": _anim_summary(source_anim),
    }


def _context_warnings(character, hands, weapon):
    warnings = []
    if not character:
        warnings.append("No HumanIK character link map found.")
    if not hands.get("right"):
        warnings.append("Right hand bone was not resolved.")
    if not hands.get("left"):
        warnings.append("Left hand bone was not resolved.")
    if weapon is None:
        warnings.append("No weapon model was provided or selected.")
    return warnings


def _body_model(character_name, key):
    slot = None
    if key == "right_hand":
        slot = "RightHandLink"
    elif key == "left_hand":
        slot = "LeftHandLink"

    if slot:
        link_map = mb_helpers.get_character_link_map(character_name, include_empty=False)
        links = (link_map or {}).get("links", {})
        names = links.get(slot) or []
        if names:
            model = _resolve_model(names[0])
            if model is not None:
                return model

    for name in BODY_FALLBACKS.get(key, []):
        model = _resolve_model(name)
        if model is not None:
            return model
    return None


def _resolve_model(name):
    if not name:
        return None
    if hasattr(mb_helpers, "_find_model"):
        try:
            return mb_helpers._find_model(str(name))
        except Exception:
            pass
    matches = mb_helpers.find_models_by_name(str(name), exact=True, include_invisible=True)
    if matches:
        return _find_model_from_summary(matches[0])
    return None


def _find_model_from_summary(summary):
    if not summary:
        return None
    name = summary.get("name")
    if hasattr(mb_helpers, "_find_model"):
        return mb_helpers._find_model(name)
    return None


def _selected_non_skeleton_model():
    for item in mb_helpers.list_selected_models():
        name = item.get("name")
        model = _resolve_model(name)
        if model is not None and not _is_skeleton(model):
            return model
    return None


def _model_entry(model):
    if model is None:
        return None
    return {
        "name": getattr(model, "Name", ""),
        "class_name": _type_name(model),
        "translation": _get_world_vector(model, "translation"),
        "rotation": _get_world_vector(model, "rotation"),
        "scaling": _get_world_vector(model, "scaling"),
        "parent": getattr(getattr(model, "Parent", None), "Name", None),
    }


def _get_world_vector(model, channel):
    enum_name = {
        "translation": "kModelTranslation",
        "rotation": "kModelRotation",
        "scaling": "kModelScaling",
    }.get(channel)
    enum = getattr(getattr(fb, "FBModelTransformationType", None), enum_name, None)
    vector = fb.FBVector3d()
    if enum is not None and hasattr(model, "GetVector"):
        try:
            model.GetVector(vector, enum, True)
            return _vec_to_list(vector)
        except Exception:
            pass

    attr = {
        "translation": "Translation",
        "rotation": "Rotation",
        "scaling": "Scaling",
    }.get(channel)
    try:
        return _vec_to_list(getattr(model, attr))
    except Exception:
        return [0.0, 0.0, 0.0] if channel != "scaling" else [1.0, 1.0, 1.0]


def _create_or_update_null(name, target):
    model = _resolve_model(name)
    created = False
    if model is None:
        model = fb.FBModelNull(str(name))
        model.Show = True
        created = True
    _set_world_vector(model, "translation", target.get("translation", [0, 0, 0]))
    _set_world_vector(model, "rotation", target.get("rotation", [0, 0, 0]))
    _evaluate()
    return {
        "name": getattr(model, "Name", str(name)),
        "created": created,
        "translation": _get_world_vector(model, "translation"),
        "rotation": _get_world_vector(model, "rotation"),
    }


def _set_world_vector(model, channel, values):
    enum_name = {
        "translation": "kModelTranslation",
        "rotation": "kModelRotation",
        "scaling": "kModelScaling",
    }.get(channel)
    enum = getattr(getattr(fb, "FBModelTransformationType", None), enum_name, None)
    vector = fb.FBVector3d(float(values[0]), float(values[1]), float(values[2]))
    if enum is not None and hasattr(model, "SetVector"):
        try:
            model.SetVector(vector, enum, True)
            return
        except Exception:
            pass
    setattr(model, channel.capitalize(), vector)


def _copy_pose(pose):
    return copy.deepcopy(pose)


def _apply_aim_offsets(pose, yaw, pitch, yaw_axis=1, pitch_axis=0):
    for bone_name, weight in AIM_DISTRIBUTION:
        for bone in pose.get("bones", []):
            if _norm_name(bone.get("name", "")) == _norm_name(bone_name):
                rot = list(bone.get("rotation", [0.0, 0.0, 0.0]))
                rot[int(yaw_axis)] += float(yaw) * float(weight)
                rot[int(pitch_axis)] += float(pitch) * float(weight)
                bone["rotation"] = rot


def _apply_cover_offsets(pose, offsets):
    rotation_offsets = offsets.get("rotation_offsets", {})
    root_translation = offsets.get("root_translation")
    for bone in pose.get("bones", []):
        name = bone.get("name", "")
        norm = _norm_name(name)
        if root_translation is not None and norm in ("root", "hips", "pelvis"):
            bone["translation"] = _add3(bone.get("translation", [0, 0, 0]), root_translation)
        for target_name, rot_offset in rotation_offsets.items():
            if norm == _norm_name(target_name):
                bone["rotation"] = _add3(bone.get("rotation", [0, 0, 0]), rot_offset)


def _inclusive_range(start, stop, step):
    start = int(start)
    stop = int(stop)
    step = abs(int(step)) or 1
    values = []
    if start <= stop:
        current = start
        while current <= stop:
            values.append(current)
            current += step
        if values[-1] != stop:
            values.append(stop)
    else:
        current = start
        while current >= stop:
            values.append(current)
            current -= step
        if values[-1] != stop:
            values.append(stop)
    return values


def _aim_pose_name(yaw, pitch):
    return "Aim_Yaw%+d_Pitch%+d" % (int(yaw), int(pitch))


def _neighbor_keys(key, all_keys):
    yaw, pitch = key
    yaws = sorted(set(k[0] for k in all_keys))
    pitches = sorted(set(k[1] for k in all_keys))
    result = []
    if yaw in yaws:
        idx = yaws.index(yaw)
        if idx + 1 < len(yaws):
            result.append((yaws[idx + 1], pitch))
    if pitch in pitches:
        idx = pitches.index(pitch)
        if idx + 1 < len(pitches):
            result.append((yaw, pitches[idx + 1]))
    return [item for item in result if item in all_keys]


def _pose_rotation_delta(a_pose, b_pose):
    if not a_pose or not b_pose:
        return {"max_delta": 0.0, "bone": None}
    a = {bone.get("name"): bone for bone in a_pose.get("bones", [])}
    b = {bone.get("name"): bone for bone in b_pose.get("bones", [])}
    max_delta = 0.0
    max_bone = None
    for name, bone_a in a.items():
        bone_b = b.get(name)
        if not bone_b:
            continue
        delta = _distance3(bone_a.get("rotation", [0, 0, 0]), bone_b.get("rotation", [0, 0, 0]))
        if delta > max_delta:
            max_delta = delta
            max_bone = name
    return {"max_delta": max_delta, "bone": max_bone}


def _resolve_frame_range(start_frame, end_frame):
    playback = mb_helpers.get_playback_info()
    if start_frame is None:
        start_frame = playback.get("loop_start_frame", 0)
    if end_frame is None:
        end_frame = playback.get("loop_stop_frame", 0)
    if int(end_frame) <= int(start_frame):
        end_frame = int(start_frame) + 30
    return {"start_frame": int(start_frame), "end_frame": int(end_frame)}


def _compare_pose_endpoints(start_pose, end_pose):
    start_by_name = {bone.get("name"): bone for bone in start_pose.get("bones", [])}
    end_by_name = {bone.get("name"): bone for bone in end_pose.get("bones", [])}
    deltas = []
    for name, start_bone in start_by_name.items():
        end_bone = end_by_name.get(name)
        if not end_bone:
            continue
        deltas.append({
            "name": name,
            "translation_delta": _distance3(
                start_bone.get("translation", [0, 0, 0]),
                end_bone.get("translation", [0, 0, 0]),
            ),
            "rotation_delta": _distance3(
                start_bone.get("rotation", [0, 0, 0]),
                end_bone.get("rotation", [0, 0, 0]),
            ),
        })
    deltas.sort(key=lambda item: max(item["translation_delta"], item["rotation_delta"]), reverse=True)
    return {
        "max_translation_delta": max([item["translation_delta"] for item in deltas] or [0.0]),
        "max_rotation_delta": max([item["rotation_delta"] for item in deltas] or [0.0]),
        "bone_deltas": deltas[:40],
    }


def _analyze_foot_slide(foot_name, start_frame, end_frame, frame_step, height_tolerance, slide_tolerance):
    model = _resolve_model(foot_name)
    if model is None:
        return {"foot": foot_name, "found": False, "slides": []}

    samples = []
    previous_frame = mb_helpers.get_playback_info()["current_frame"]
    try:
        for frame in range(int(start_frame), int(end_frame) + 1, max(1, int(frame_step))):
            mb_helpers.set_playback_time(frame)
            _evaluate()
            pos = _get_world_vector(model, "translation")
            samples.append({"frame": frame, "position": pos})
    finally:
        mb_helpers.set_playback_time(previous_frame)
        _evaluate()

    if not samples:
        return {"foot": foot_name, "found": True, "slides": []}

    min_height = min(sample["position"][1] for sample in samples)
    contact = [
        sample for sample in samples
        if sample["position"][1] <= min_height + float(height_tolerance)
    ]
    slides = []
    for prev, current in zip(contact, contact[1:]):
        if current["frame"] - prev["frame"] > max(1, int(frame_step)):
            continue
        delta = _distance_xz(prev["position"], current["position"])
        if delta > float(slide_tolerance):
            slides.append({
                "frame": current["frame"],
                "delta": delta,
                "from": prev["position"],
                "to": current["position"],
            })
    return {
        "foot": foot_name,
        "found": True,
        "sample_count": len(samples),
        "contact_sample_count": len(contact),
        "min_height": min_height,
        "slides": slides,
    }


def _sync_point_map(anim):
    if anim is None:
        return {}
    points = anim.get("sync_points", anim) if isinstance(anim, dict) else anim
    result = {}
    if isinstance(points, dict):
        for name, value in points.items():
            if isinstance(value, dict):
                item = dict(value)
                item.setdefault("frame", value.get("frame", 0))
            else:
                item = {"frame": value}
            result[str(name)] = item
    elif isinstance(points, list):
        for item in points:
            result[str(item.get("name"))] = dict(item)
    return result


def _skeleton_bone_list(skeleton):
    if skeleton is None:
        return []
    if isinstance(skeleton, dict):
        if "bones" in skeleton:
            return list(skeleton.get("bones") or [])
        if "children" in skeleton:
            result = []
            _flatten_hierarchy(skeleton, result)
            return result
    if isinstance(skeleton, list):
        result = []
        for item in skeleton:
            if isinstance(item, dict) and "children" in item:
                _flatten_hierarchy(item, result)
            else:
                result.append(item)
        return result
    return []


def _flatten_hierarchy(node, result):
    result.append({
        "name": node.get("name", ""),
        "parent": node.get("parent"),
        "translation": node.get("translation", [0, 0, 0]),
    })
    for child in node.get("children", []) or []:
        child = dict(child)
        child.setdefault("parent", node.get("name", ""))
        _flatten_hierarchy(child, result)


def _best_target_bone(source_name, target_by_norm):
    norm = _norm_name(source_name)
    if norm in target_by_norm:
        return target_by_norm[norm]
    swaps = [
        ("left", "l"),
        ("right", "r"),
        ("forearm", "lowerarm"),
        ("upleg", "thigh"),
        ("leg", "calf"),
    ]
    candidates = set([norm])
    for a, b in swaps:
        candidates.add(norm.replace(a, b))
        candidates.add(norm.replace(b, a))
    for candidate in candidates:
        if candidate in target_by_norm:
            return target_by_norm[candidate]
    return None


def _mapping_confidence(source, target):
    if _norm_name(source) == _norm_name(target):
        return 1.0
    return 0.72


def _estimate_skeleton_scale(source_bones, target_bones):
    source_height = _estimate_height(source_bones)
    target_height = _estimate_height(target_bones)
    ratio = 1.0
    if source_height > 0 and target_height > 0:
        ratio = target_height / source_height
    return {
        "source_height": source_height,
        "target_height": target_height,
        "ratio": ratio,
    }


def _estimate_height(bones):
    ys = []
    for bone in bones:
        value = bone.get("translation", [0, 0, 0])
        if len(value) >= 2:
            ys.append(float(value[1]))
    if not ys:
        return 0.0
    return max(ys) - min(ys)


def _anim_summary(anim):
    if not isinstance(anim, dict):
        return {"type": type(anim).__name__}
    return {
        "keys": sorted(anim.keys()),
        "frame_count": anim.get("frame_count"),
        "take": anim.get("take"),
    }


def _weapon_profile(weapon_type):
    requested = str(weapon_type or "assault_rifle").lower()
    if requested in WEAPON_PROFILES:
        return requested, WEAPON_PROFILES[requested]
    for name, profile in WEAPON_PROFILES.items():
        if requested in profile.get("aliases", []):
            return name, profile
    return "assault_rifle", WEAPON_PROFILES["assault_rifle"]


def _character_name(character_name):
    if character_name:
        return character_name
    current = mb_helpers.get_current_character()
    return current.get("name") if current else None


def _is_important_loop_bone(name):
    norm = _norm_name(name)
    return norm in (
        "root",
        "hips",
        "pelvis",
        "spine",
        "spine1",
        "spine2",
        "leftfoot",
        "rightfoot",
        "lefttoe",
        "righttoe",
    )


def _is_skeleton(model):
    type_name = _type_name(model).lower()
    return "skeleton" in type_name or "bone" in type_name


def _type_name(obj):
    for attr in ("GetTypeName", "ClassName"):
        fn = getattr(obj, attr, None)
        if callable(fn):
            try:
                return str(fn())
            except Exception:
                pass
    return type(obj).__name__


def _norm_name(name):
    text = str(name or "").split(":")[-1].lower()
    text = re.sub(r"[^a-z0-9]+", "", text)
    replacements = {
        "lefthand": "lefthand",
        "righthand": "righthand",
        "leftforearm": "leftforearm",
        "rightforearm": "rightforearm",
        "leftfoot": "leftfoot",
        "rightfoot": "rightfoot",
    }
    return replacements.get(text, text)


def _vec_to_list(value):
    return [float(value[0]), float(value[1]), float(value[2])]


def _add3(a, b):
    return [
        float(a[0]) + float(b[0]),
        float(a[1]) + float(b[1]),
        float(a[2]) + float(b[2]),
    ]


def _distance3(a, b):
    return math.sqrt(
        (float(a[0]) - float(b[0])) ** 2
        + (float(a[1]) - float(b[1])) ** 2
        + (float(a[2]) - float(b[2])) ** 2
    )


def _distance_xz(a, b):
    return math.sqrt(
        (float(a[0]) - float(b[0])) ** 2
        + (float(a[2]) - float(b[2])) ** 2
    )


def _evaluate():
    if hasattr(mb_helpers, "_evaluate_scene"):
        mb_helpers._evaluate_scene()
        return
    try:
        fb.FBSystem().Scene.Evaluate()
    except Exception:
        pass
