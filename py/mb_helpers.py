"""
Agent-friendly MotionBuilder helper functions.

These helpers wrap common pyfbsdk operations behind small, predictable
functions. The implementation favors APIs verified against MotionBuilder 2024
and avoids relying on older FBModelList static helpers that are not present in
that version.
"""

import fnmatch
import json
import os

import pyfbsdk as fb

__all__ = [
    # Scene / files
    "get_scene_info",
    "open_file",
    "merge_file",
    "save_file",
    "new_scene",
    # Models / selection
    "list_models",
    "list_selected_models",
    "find_models_by_name",
    "find_models_by_class",
    "select_models",
    "clear_selection",
    "create_null",
    "delete_model",
    "get_model_transform",
    "set_model_transform",
    "get_model_children",
    "get_model_parent",
    # Skeletons / characters
    "list_skeleton_roots",
    "get_skeleton_hierarchy",
    "list_body_nodes",
    "get_character_skeleton",
    "get_character_link_map",
    "characterize_biped",
    "get_skeleton_pose",
    "set_skeleton_pose",
    "list_characters",
    "get_current_character",
    # Animation
    "list_animatable_properties",
    "get_property_animation_keys",
    "get_transform_curves",
    "set_curve_key",
    "set_vector_property_key",
    "set_model_transform_key",
    # Playback / takes
    "get_playback_info",
    "set_playback_time",
    "play",
    "stop",
    "pause",
    "list_takes",
    "get_current_take",
    "set_current_take",
    "new_take",
    # Output
    "dump_json",
]


# ---------------------------------------------------------------------------
# Scene / files
# ---------------------------------------------------------------------------

def get_scene_info():
    """Return basic scene and application metadata."""
    system = fb.FBSystem()
    scene = _scene()
    app = fb.FBApplication()
    path = _scene_path()
    current_take = getattr(scene, "CurrentTake", None)
    return {
        "name": _scene_name(path, scene),
        "file_path": path,
        "app_version": str(_first_attr(app, ("AppVersion", "Version"), "")),
        "system_version": str(_first_attr(system, ("Version", "BuildVersion"), "")),
        "model_count": len(list(_iter_models())),
        "selected_model_count": len(list_selected_models()),
        "character_count": len(list(getattr(scene, "Characters", []) or [])),
        "skeleton_root_count": len(list_skeleton_roots()),
        "take_count": len(list(getattr(scene, "Takes", []) or [])),
        "current_take": getattr(current_take, "Name", None),
    }


def open_file(path, prompt=False):
    """Open a scene/FBX file. This replaces the current scene."""
    return bool(fb.FBApplication().FileOpen(str(path), bool(prompt)))


def merge_file(path, prompt=False):
    """Merge a scene/FBX file into the current scene."""
    return bool(fb.FBApplication().FileMerge(str(path), bool(prompt)))


def save_file(path=None):
    """Save the scene, optionally to a new path."""
    app = fb.FBApplication()
    if path:
        return bool(app.FileSave(str(path)))
    return bool(app.FileSave())


def new_scene(prompt=False):
    """Create a new scene. This can discard unsaved changes."""
    return bool(fb.FBApplication().FileNew(bool(prompt)))


# ---------------------------------------------------------------------------
# Models / selection
# ---------------------------------------------------------------------------

def list_models(include_invisible=False):
    """List scene models with names, types, visibility, selection, and transforms."""
    result = []
    for model in _iter_models():
        visible = bool(_first_attr(model, ("Show", "Visible"), True))
        if not include_invisible and not visible:
            continue
        result.append(_model_summary(model))
    return result


def list_selected_models():
    """List selected models."""
    return [
        _model_summary(model)
        for model in _iter_models()
        if bool(getattr(model, "Selected", False))
    ]


def find_models_by_name(pattern, exact=False, include_invisible=True):
    """Find models by exact name, substring, or shell wildcard."""
    results = []
    needle = str(pattern)
    for model in _iter_models():
        name = getattr(model, "Name", "")
        if exact:
            matched = name == needle
        else:
            matched = fnmatch.fnmatch(name.lower(), needle.lower())
            if not matched and "*" not in needle:
                matched = needle.lower() in name.lower()
        if matched:
            visible = bool(_first_attr(model, ("Show", "Visible"), True))
            if include_invisible or visible:
                results.append(_model_summary(model))
    return results


def find_models_by_class(class_name):
    """Find models by pyfbsdk class-name substring."""
    target = str(class_name).lower()
    return [
        _model_summary(model)
        for model in _iter_models()
        if target in _type_name(model).lower()
    ]


def select_models(names, replace=True):
    """Select models by exact name. Returns found names."""
    if isinstance(names, str):
        names = [names]
    wanted = set(str(name) for name in names)
    found = []
    if replace:
        clear_selection()
    for model in _iter_models():
        if getattr(model, "Name", "") in wanted:
            model.Selected = True
            found.append(getattr(model, "Name", ""))
    _evaluate_scene()
    return found


def clear_selection():
    """Clear model selection."""
    for model in _iter_models():
        try:
            model.Selected = False
        except Exception:
            pass
    _evaluate_scene()
    return True


def create_null(name, translation=None, rotation=None, scaling=None, visible=True, select=True):
    """Create an FBModelNull and return its summary."""
    model = fb.FBModelNull(str(name))
    model.Show = bool(visible)
    if translation is not None:
        _set_model_vector(model, translation, "Translation", "kModelTranslation")
    if rotation is not None:
        _set_model_vector(model, rotation, "Rotation", "kModelRotation")
    if scaling is not None:
        _set_model_vector(model, scaling, "Scaling", "kModelScaling")
    if select:
        clear_selection()
        model.Selected = True
    _evaluate_scene()
    return _model_summary(model)


def delete_model(model_name):
    """Delete one model by exact name. This is destructive."""
    model = _find_model(model_name)
    if model is None:
        return False
    model.FBDelete()
    _evaluate_scene()
    return True


def get_model_transform(model_name):
    """Get translation/rotation/scaling for a named model."""
    model = _find_model(model_name)
    if model is None:
        return None
    return {
        "name": getattr(model, "Name", ""),
        "class_name": _type_name(model),
        "translation": _get_model_vector(model, "Translation", "kModelTranslation"),
        "rotation": _get_model_vector(model, "Rotation", "kModelRotation"),
        "scaling": _get_model_vector(model, "Scaling", "kModelScaling"),
    }


def set_model_transform(model_name, translation=None, rotation=None, scaling=None):
    """Set transform values on a named model. Returns False if not found."""
    model = _find_model(model_name)
    if model is None:
        return False
    if translation is not None:
        _set_model_vector(model, translation, "Translation", "kModelTranslation")
    if rotation is not None:
        _set_model_vector(model, rotation, "Rotation", "kModelRotation")
    if scaling is not None:
        _set_model_vector(model, scaling, "Scaling", "kModelScaling")
    _evaluate_scene()
    return True


def get_model_children(model_name):
    """Return direct child names for a model."""
    model = _find_model(model_name)
    if model is None:
        return []
    return [getattr(child, "Name", "") for child in list(getattr(model, "Children", []) or [])]


def get_model_parent(model_name):
    """Return direct parent name for a model."""
    model = _find_model(model_name)
    if model is None:
        return None
    parent = getattr(model, "Parent", None)
    return getattr(parent, "Name", None) if parent else None


# ---------------------------------------------------------------------------
# Skeletons / characters
# ---------------------------------------------------------------------------

def list_skeleton_roots():
    """List root skeleton-like models."""
    return [
        _model_summary(model)
        for model in _iter_models()
        if _is_skeleton_model(model) and not _is_skeleton_model(getattr(model, "Parent", None))
    ]


def get_skeleton_hierarchy(root_name=None):
    """Return skeleton-like hierarchy for one root or every skeleton root."""
    if root_name:
        root = _find_model(root_name)
        roots = [root] if root is not None else []
    else:
        roots = [
            model for model in _iter_models()
            if _is_skeleton_model(model) and not _is_skeleton_model(getattr(model, "Parent", None))
        ]
    return [_hierarchy_node(root) for root in roots]


def list_body_nodes():
    """List available HumanIK body-node enum names."""
    enum = getattr(fb, "FBBodyNodeId", None)
    if enum is None:
        return []
    names = [
        name for name in dir(enum)
        if name.startswith("kFB") and name.endswith("NodeId") and name != "kFBInvalidNodeId"
    ]
    names.sort()
    return names


def get_character_skeleton(character_name=None):
    """Return HumanIK body-node to model mapping for a character.

    If character_name is omitted, the current character is used first, then the
    first scene character.
    """
    char = _find_character(character_name)
    if char is None:
        return None

    bones = []
    seen = set()
    for node_name in list_body_nodes():
        node_id = getattr(fb.FBBodyNodeId, node_name, None)
        if node_id is None:
            continue
        try:
            model = char.GetModel(node_id)
        except Exception:
            model = None
        if model is None:
            continue
        ident = id(model)
        if ident in seen:
            continue
        seen.add(ident)
        item = _model_summary(model)
        item["body_node"] = node_name
        bones.append(item)

    return {
        "character": getattr(char, "Name", ""),
        "class_name": _type_name(char),
        "bone_count": len(bones),
        "bones": bones,
    }


def get_character_link_map(character_name=None, include_empty=False):
    """Return Character slot -> linked model names."""
    char = _find_character(character_name)
    if char is None:
        return None
    links = {}
    for prop in char.PropertyList:
        slot = getattr(prop, "Name", "")
        if not slot.endswith("Link"):
            continue
        if not hasattr(prop, "__len__"):
            continue
        names = [getattr(prop[i], "Name", str(prop[i])) for i in range(len(prop))]
        if names or include_empty:
            links[slot] = names
    return {
        "character": getattr(char, "Name", ""),
        "characterized": bool(char.GetCharacterize()),
        "error": char.GetCharacterizeError(),
        "active": bool(getattr(char, "Active", False)),
        "links": links,
    }


def characterize_biped(character_name="Character", activate=True):
    """Create or update a standard biped Character from matching skeleton names.

    This maps common HumanIK slots such as HipsLink, LeftArmLink, RightFootLink
    to models with the same base name, then calls SetCharacterizeOn(True).
    """
    char = _find_character(character_name)
    created = False
    if char is None:
        char = fb.FBCharacter(str(character_name))
        created = True

    mapping = _default_character_link_mapping()
    linked = {}
    missing = []
    for slot, model_name in mapping.items():
        prop = char.PropertyList.Find(slot)
        model = _find_model(model_name)
        if prop is None or model is None:
            missing.append({"slot": slot, "model": model_name})
            continue
        _property_list_set_single(prop, model)
        linked[slot] = model_name

    characterized = bool(char.SetCharacterizeOn(True))
    if activate:
        try:
            char.Active = True
        except Exception:
            pass
        try:
            fb.FBApplication().CurrentCharacter = char
        except Exception:
            pass

    return {
        "character": getattr(char, "Name", ""),
        "created": created,
        "characterized": characterized,
        "get_characterize": bool(char.GetCharacterize()),
        "error": char.GetCharacterizeError(),
        "active": bool(getattr(char, "Active", False)),
        "linked": linked,
        "missing": missing,
    }


def get_skeleton_pose(root_name=None, frame=None, space="local", include_matrix=False):
    """Read a pose from a skeleton root or all skeleton-like models.

    The returned format is intentionally simple for agents:
    {"frame": int|None, "space": "local", "bones": [{name,parent,translation,rotation,scaling,...}]}
    """
    previous_frame = None
    if frame is not None:
        previous_frame = get_playback_info()["current_frame"]
        set_playback_time(frame)
        _evaluate_scene()

    try:
        models = _pose_models(root_name)
        return {
            "frame": frame,
            "space": space,
            "bone_count": len(models),
            "bones": [_pose_model_entry(model, space=space, include_matrix=include_matrix) for model in models],
        }
    finally:
        if previous_frame is not None:
            set_playback_time(previous_frame)
            _evaluate_scene()


def set_skeleton_pose(pose, frame=None, key=True, space="local"):
    """Apply a pose dictionary produced by get_skeleton_pose.

    This sets matching model transforms by name. When key=True, transform keys
    are written at frame.
    """
    if pose is None:
        return {"applied": 0, "missing": []}
    bones = pose.get("bones", []) if isinstance(pose, dict) else pose
    if frame is None and isinstance(pose, dict):
        frame = pose.get("frame", None)

    applied = 0
    missing = []
    for item in bones:
        name = item.get("name")
        if not name:
            continue
        model = _find_model(name)
        if model is None:
            missing.append(name)
            continue
        translation = item.get("translation", None)
        rotation = item.get("rotation", None)
        scaling = item.get("scaling", None)
        if key:
            if frame is None:
                frame = get_playback_info()["current_frame"]
            set_model_transform_key(
                name,
                frame,
                translation=translation,
                rotation=rotation,
                scaling=scaling,
            )
        else:
            set_model_transform(name, translation=translation, rotation=rotation, scaling=scaling)
        applied += 1

    _evaluate_scene()
    return {"applied": applied, "missing": missing}


def list_characters():
    """List characters in the current scene."""
    result = []
    for char in list(getattr(_scene(), "Characters", []) or []):
        result.append({
            "name": getattr(char, "Name", ""),
            "class_name": _type_name(char),
            "active": bool(_first_attr(char, ("Active",), False)),
        })
    return result


def get_current_character():
    """Return the current application character when MotionBuilder exposes it."""
    app = fb.FBApplication()
    char = _first_attr(app, ("CurrentCharacter",), None)
    if not char:
        return None
    return {
        "name": getattr(char, "Name", ""),
        "class_name": _type_name(char),
        "active": bool(_first_attr(char, ("Active",), False)),
    }


# ---------------------------------------------------------------------------
# Animation
# ---------------------------------------------------------------------------

def list_animatable_properties(model_name):
    """List common animatable properties on a model."""
    model = _find_model(model_name)
    if model is None:
        return []
    prop_list = getattr(model, "PropertyList", None)
    if prop_list is None:
        return []

    result = []
    for name in ("Lcl Translation", "Lcl Rotation", "Lcl Scaling", "Visibility"):
        prop = prop_list.Find(name)
        if prop is not None:
            result.append(_property_summary(prop, name))
    return result


def get_property_animation_keys(model_name, property_name="Lcl Translation"):
    """Read animation keys from a scalar or vector animatable property."""
    prop = _find_property(model_name, property_name)
    if prop is None:
        return None

    node = _property_animation_node(prop, create=False)
    if node is None:
        return {
            "model": model_name,
            "property": property_name,
            "animated": False,
            "channels": [],
        }

    child_nodes = list(getattr(node, "Nodes", []) or [])
    if child_nodes:
        channels = [_channel_keys(child) for child in child_nodes]
    else:
        channels = [_channel_keys(node)]

    return {
        "model": model_name,
        "property": property_name,
        "animated": True,
        "channels": channels,
    }


def get_transform_curves(model_name):
    """Read Translation/Rotation/Scaling animation curves for a model."""
    return {
        "model": model_name,
        "properties": [
            get_property_animation_keys(model_name, "Lcl Translation"),
            get_property_animation_keys(model_name, "Lcl Rotation"),
            get_property_animation_keys(model_name, "Lcl Scaling"),
        ],
    }


def set_curve_key(model_name, property_name, channel, frame, value):
    """Set one scalar FCurve key.

    property_name is typically "Lcl Translation", "Lcl Rotation", or
    "Lcl Scaling". channel can be "X"/"Y"/"Z" or 0/1/2.
    """
    prop = _find_property(model_name, property_name)
    if prop is None:
        return False

    node = _property_animation_node(prop, create=True)
    if node is None:
        return False

    target = _find_channel_node(node, channel)
    if target is None:
        target = node

    fcurve = getattr(target, "FCurve", None)
    if fcurve is None:
        return False

    key_time = _frame_to_time(frame)
    existing_index = _find_key_index_at_frame(fcurve, frame)
    if existing_index is not None:
        fcurve.KeySetValue(existing_index, float(value))
    else:
        fcurve.KeyAdd(key_time, float(value))
    _evaluate_scene()
    return True


def set_vector_property_key(model_name, property_name, frame, value):
    """Set a vector property value and key it at a frame."""
    prop = _find_property(model_name, property_name)
    if prop is None:
        return False
    prop.SetAnimated(True)
    prop.Data = fb.FBVector3d(float(value[0]), float(value[1]), float(value[2]))
    prop.KeyAt(_frame_to_time(frame))
    _evaluate_scene()
    return True


def set_model_transform_key(model_name, frame, translation=None, rotation=None, scaling=None):
    """Set transform values and key selected transform channels at a frame."""
    ok = False
    if translation is not None:
        ok = set_vector_property_key(model_name, "Lcl Translation", frame, translation) or ok
    if rotation is not None:
        ok = set_vector_property_key(model_name, "Lcl Rotation", frame, rotation) or ok
    if scaling is not None:
        ok = set_vector_property_key(model_name, "Lcl Scaling", frame, scaling) or ok
    return ok


# ---------------------------------------------------------------------------
# Playback / takes
# ---------------------------------------------------------------------------

def get_playback_info():
    """Return transport, frame, and loop range state."""
    player = fb.FBPlayerControl()
    rate = _frame_rate()
    return {
        "playing": bool(_first_attr(player, ("IsPlaying",), False)),
        "looping": bool(_first_attr(player, ("Loop",), False)),
        "current_frame": _time_to_frame(_first_attr(player, ("Time",), None), rate),
        "loop_start_frame": _time_to_frame(_first_attr(player, ("LoopStart",), None), rate),
        "loop_stop_frame": _time_to_frame(_first_attr(player, ("LoopStop",), None), rate),
        "framerate": rate,
    }


def set_playback_time(frame):
    player = fb.FBPlayerControl()
    player.Time = _frame_to_time(frame)
    return True


def play():
    fb.FBPlayerControl().Play()
    return True


def stop():
    fb.FBPlayerControl().Stop()
    return True


def pause():
    fb.FBPlayerControl().Stop()
    return True


def list_takes():
    """List take names."""
    return [getattr(take, "Name", "") for take in list(getattr(_scene(), "Takes", []) or [])]


def get_current_take():
    take = getattr(_scene(), "CurrentTake", None)
    return getattr(take, "Name", None) if take else None


def set_current_take(take_name):
    scene = _scene()
    for take in list(getattr(scene, "Takes", []) or []):
        if getattr(take, "Name", "") == take_name:
            scene.CurrentTake = take
            return True
    return False


def new_take(take_name, duration_frames=100):
    scene = _scene()
    try:
        try:
            take = fb.FBTake(str(take_name))
        except TypeError:
            take = fb.FBTake()
            take.Name = str(take_name)
        scene.Takes.append(take)
        scene.CurrentTake = take
        take.Stop = _frame_to_time(duration_frames)
        return True
    except Exception:
        return False


def dump_json(value):
    """Print compact UTF-8 JSON for bridge consumers."""
    print(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _scene():
    system = fb.FBSystem()
    scene = getattr(system, "Scene", None)
    if scene is not None:
        return scene
    return fb.FBScene()


def _scene_path():
    app = fb.FBApplication()
    for attr in ("FBXFileName", "FileName"):
        value = getattr(app, attr, "")
        if value:
            return str(value)
    return ""


def _scene_name(path, scene):
    if path:
        return os.path.splitext(os.path.basename(path))[0]
    return str(_first_attr(scene, ("Name",), "Scene"))


def _iter_models():
    seen = set()

    def emit(model):
        ident = id(model)
        if ident in seen:
            return
        seen.add(ident)
        yield model
        for child in list(getattr(model, "Children", []) or []):
            for nested in emit(child):
                yield nested

    scene = _scene()
    for comp in list(getattr(scene, "Components", []) or []):
        if _looks_like_model(comp):
            for item in emit(comp):
                yield item


def _looks_like_model(obj):
    try:
        if isinstance(obj, fb.FBModel):
            return True
    except Exception:
        pass
    return hasattr(obj, "Children") and (
        hasattr(obj, "Translation") or hasattr(obj, "GetVector")
    )


def _find_model(name):
    for model in _iter_models():
        if getattr(model, "Name", "") == name:
            return model
    return None


def _find_character(name=None):
    scene = _scene()
    chars = list(getattr(scene, "Characters", []) or [])
    if name:
        for char in chars:
            if getattr(char, "Name", "") == name:
                return char
        return None
    current = _first_attr(fb.FBApplication(), ("CurrentCharacter",), None)
    if current:
        return current
    return chars[0] if chars else None


def _find_property(model_name, property_name):
    model = _find_model(model_name)
    if model is None:
        return None
    prop_list = getattr(model, "PropertyList", None)
    if prop_list is None:
        return None
    return prop_list.Find(str(property_name))


def _pose_models(root_name=None):
    if root_name:
        root = _find_model(root_name)
        if root is None:
            return []
        return list(_iter_model_hierarchy(root))
    skeletons = [model for model in _iter_models() if _is_skeleton_model(model)]
    if skeletons:
        return skeletons
    return []


def _iter_model_hierarchy(root):
    yield root
    for child in list(getattr(root, "Children", []) or []):
        for nested in _iter_model_hierarchy(child):
            yield nested


def _model_summary(model):
    return {
        "name": getattr(model, "Name", ""),
        "class_name": _type_name(model),
        "translation": _get_model_vector(model, "Translation", "kModelTranslation"),
        "rotation": _get_model_vector(model, "Rotation", "kModelRotation"),
        "scaling": _get_model_vector(model, "Scaling", "kModelScaling"),
        "visible": bool(_first_attr(model, ("Show", "Visible"), True)),
        "selected": bool(_first_attr(model, ("Selected",), False)),
        "parent": getattr(getattr(model, "Parent", None), "Name", None),
        "child_count": len(list(getattr(model, "Children", []) or [])),
    }


def _pose_model_entry(model, space="local", include_matrix=False):
    entry = {
        "name": getattr(model, "Name", ""),
        "class_name": _type_name(model),
        "parent": getattr(getattr(model, "Parent", None), "Name", None),
        "translation": _get_model_vector(model, "Translation", "kModelTranslation"),
        "rotation": _get_model_vector(model, "Rotation", "kModelRotation"),
        "scaling": _get_model_vector(model, "Scaling", "kModelScaling"),
    }
    if include_matrix:
        entry["matrix"] = _get_model_matrix(model, space=space)
    return entry


def _property_summary(prop, fallback_name):
    return {
        "name": str(getattr(prop, "Name", fallback_name) or fallback_name),
        "class_name": _type_name(prop),
        "is_animatable": bool(_call_or_default(prop, "IsAnimatable", False)),
        "is_animated": bool(_call_or_default(prop, "IsAnimated", False)),
        "data": _jsonable_value(getattr(prop, "Data", None)),
    }


def _type_name(obj):
    for attr in ("GetTypeName", "ClassName"):
        fn = getattr(obj, attr, None)
        if callable(fn):
            try:
                return str(fn())
            except Exception:
                pass
    return type(obj).__name__


def _get_model_vector(model, direct_attr, transform_enum_name):
    try:
        return _vector_to_list(getattr(model, direct_attr))
    except Exception:
        pass

    enum_value = _transform_enum(transform_enum_name)
    if enum_value is not None and hasattr(model, "GetVector"):
        try:
            v = fb.FBVector3d()
            model.GetVector(v, enum_value, True)
            return _vector_to_list(v)
        except Exception:
            pass
    return [0.0, 0.0, 0.0]


def _get_model_matrix(model, space="local"):
    if not hasattr(model, "GetMatrix") or not hasattr(fb, "FBMatrix"):
        return []
    matrix = fb.FBMatrix()
    transform_type = getattr(
        getattr(fb, "FBModelTransformationType", None),
        "kModelTransformation",
        None,
    )
    try:
        global_info = str(space).lower() in ("global", "world")
        if transform_type is not None:
            model.GetMatrix(matrix, transform_type, global_info)
        else:
            model.GetMatrix(matrix)
        return [float(matrix[i]) for i in range(16)]
    except Exception:
        return []


def _set_model_vector(model, values, direct_attr, transform_enum_name):
    v = fb.FBVector3d(float(values[0]), float(values[1]), float(values[2]))
    enum_value = _transform_enum(transform_enum_name)
    if enum_value is not None and hasattr(model, "SetVector"):
        try:
            model.SetVector(v, enum_value, True)
            return
        except Exception:
            pass
    setattr(model, direct_attr, v)


def _transform_enum(name):
    enum = getattr(fb, "FBModelTransformationType", None)
    return getattr(enum, name, None) if enum is not None else None


def _vector_to_list(v):
    return [float(v[0]), float(v[1]), float(v[2])]


def _first_attr(obj, names, default=None):
    for name in names:
        try:
            value = getattr(obj, name)
            if value is not None:
                return value
        except Exception:
            pass
    return default


def _call_or_default(obj, method_name, default=None):
    fn = getattr(obj, method_name, None)
    if not callable(fn):
        return default
    try:
        return fn()
    except Exception:
        return default


def _is_skeleton_model(model):
    if model is None:
        return False
    type_name = _type_name(model).lower()
    if "skeleton" in type_name or "bone" in type_name:
        return True
    try:
        return isinstance(model, fb.FBModelSkeleton)
    except Exception:
        return False


def _hierarchy_node(model):
    children = [
        child for child in list(getattr(model, "Children", []) or [])
        if _is_skeleton_model(child)
    ]
    return {
        "name": getattr(model, "Name", ""),
        "class_name": _type_name(model),
        "translation": _get_model_vector(model, "Translation", "kModelTranslation"),
        "rotation": _get_model_vector(model, "Rotation", "kModelRotation"),
        "children": [_hierarchy_node(child) for child in children],
    }


def _property_animation_node(prop, create=False):
    try:
        if create and hasattr(prop, "SetAnimated"):
            prop.SetAnimated(True)
        if hasattr(prop, "GetAnimationNode"):
            return prop.GetAnimationNode()
    except Exception:
        return None
    return None


def _channel_keys(node):
    fcurve = getattr(node, "FCurve", None)
    keys = []
    if fcurve is not None:
        for key in list(getattr(fcurve, "Keys", []) or []):
            keys.append({
                "frame": _time_to_frame(getattr(key, "Time", None), _frame_rate()),
                "seconds": _time_to_seconds(getattr(key, "Time", None)),
                "value": float(getattr(key, "Value", 0.0)),
                "interpolation": str(getattr(key, "Interpolation", "")),
            })
    return {
        "name": getattr(node, "Name", ""),
        "key_count": len(keys),
        "keys": keys,
    }


def _find_channel_node(node, channel):
    child_nodes = list(getattr(node, "Nodes", []) or [])
    if not child_nodes:
        return node
    if isinstance(channel, int):
        return child_nodes[channel] if 0 <= channel < len(child_nodes) else None
    channel_name = str(channel).upper()
    axis_to_index = {"X": 0, "Y": 1, "Z": 2}
    if channel_name in axis_to_index:
        idx = axis_to_index[channel_name]
        return child_nodes[idx] if idx < len(child_nodes) else None
    for child in child_nodes:
        if getattr(child, "Name", "").upper() == channel_name:
            return child
    return None


def _property_list_set_single(prop, model):
    try:
        while len(prop):
            prop.pop()
    except Exception:
        try:
            while len(prop):
                prop.remove(prop[0])
        except Exception:
            pass
    prop.append(model)


def _default_character_link_mapping():
    return {
        "ReferenceLink": "Root",
        "HipsLink": "Hips",
        "LeftUpLegLink": "LeftUpLeg",
        "LeftLegLink": "LeftLeg",
        "LeftFootLink": "LeftFoot",
        "RightUpLegLink": "RightUpLeg",
        "RightLegLink": "RightLeg",
        "RightFootLink": "RightFoot",
        "SpineLink": "Spine",
        "LeftArmLink": "LeftArm",
        "LeftForeArmLink": "LeftForeArm",
        "LeftHandLink": "LeftHand",
        "RightArmLink": "RightArm",
        "RightForeArmLink": "RightForeArm",
        "RightHandLink": "RightHand",
        "HeadLink": "Head",
        "LeftToeBaseLink": "LeftToeBase",
        "RightToeBaseLink": "RightToeBase",
        "LeftShoulderLink": "LeftShoulder",
        "RightShoulderLink": "RightShoulder",
        "NeckLink": "Neck",
        "Spine1Link": "Spine1",
    }


def _find_key_index_at_frame(fcurve, frame):
    target = int(frame)
    for index, key in enumerate(list(getattr(fcurve, "Keys", []) or [])):
        if _time_to_frame(getattr(key, "Time", None), _frame_rate()) == target:
            return index
    return None


def _frame_rate():
    try:
        return float(fb.FBTime().GetFrameRate())
    except Exception:
        return 30.0


def _frame_to_time(frame):
    t = fb.FBTime()
    try:
        t.SetFrame(int(frame))
        return t
    except TypeError:
        pass
    try:
        t.SetFrame(int(frame), _frame_rate())
        return t
    except TypeError:
        pass
    t.SetTime(0, 0, 0, int(frame), 0, 0, _frame_rate())
    return t


def _time_to_frame(value, rate):
    if value is None:
        return 0
    try:
        return int(value.GetFrame(rate))
    except Exception:
        try:
            return int(value.GetFrame())
        except Exception:
            return 0


def _time_to_seconds(value):
    if value is None:
        return 0.0
    try:
        return float(value.GetSecondDouble())
    except Exception:
        return 0.0


def _jsonable_value(value):
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    try:
        return [float(value[i]) for i in range(len(value))]
    except Exception:
        return str(value)


def _evaluate_scene():
    try:
        _scene().Evaluate()
    except Exception:
        pass
