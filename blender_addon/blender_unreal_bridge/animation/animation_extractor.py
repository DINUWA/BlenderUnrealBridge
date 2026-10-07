"""
animation/animation_extractor.py
=================================
Authoritative Blender Action and skeletal keyframe extraction for Milestone 9.

Rules:
  - Discovers Actions assigned or associated with the Armature.
  - Non-destructive: restores active action and current frame on completion.
  - Evaluates parent-relative bone transforms at integer frames.
  - Converts keyframes to canonical Bridge coordinates (Left-Handed cm).
  - Enforces monotonic keyframe timestamps and deterministic ordering.
"""

from typing import Any, Dict, List, Optional, Set
import re
import bpy
from mathutils import Matrix

from ..collectors.id_generator import (
    ensure_skeleton_id,
    ensure_bone_id,
    get_bone_id,
    ensure_animation_id,
    get_animation_id,
)
from ..transforms.canonical import (
    _convert_location,
    _convert_quaternion,
    _convert_scale,
)

BONE_PATH_RE = re.compile(r'pose\.bones\["([^"]+)"\]')


def _find_animated_actions_for_armature(armature_obj: bpy.types.Object) -> List[bpy.types.Action]:
    """Find all Blender Actions that contain animation channels for this armature."""
    actions = []
    seen_names = set()

    # 1. Currently active action on object
    if armature_obj.animation_data and armature_obj.animation_data.action:
        act = armature_obj.animation_data.action
        actions.append(act)
        seen_names.add(act.name)

    # 2. Check all actions in bpy.data.actions to discover unassigned actions targeting this armature
    armature_bone_names = set(armature_obj.data.bones.keys())
    for act in bpy.data.actions:
        if act.name in seen_names:
            continue
        # Check if action has any fcurve mentioning our bones
        targets_armature = False
        for fc in act.fcurves:
            m = BONE_PATH_RE.search(fc.data_path)
            if m and m.group(1) in armature_bone_names:
                targets_armature = True
                break
        if targets_armature:
            actions.append(act)
            seen_names.add(act.name)

    return sorted(actions, key=lambda a: a.name)


def extract_animations_for_armature(
    armature_obj: bpy.types.Object,
    scene: Optional[bpy.types.Scene] = None,
) -> List[Dict[str, Any]]:
    """
    Extracts all animation clips for a given Armature in canonical Bridge coordinates.

    Args:
        armature_obj: Blender Object with type == 'ARMATURE'.
        scene: Active Scene (defaults to bpy.context.scene).

    Returns:
        List of animation dictionaries conforming to BUBRIDGE_ANIMATIONS schema.
    """
    if armature_obj.type != "ARMATURE" or not armature_obj.data:
        return []

    if scene is None:
        scene = bpy.context.scene

    skel_id = ensure_skeleton_id(armature_obj)
    armature_bones = armature_obj.data.bones
    bone_name_to_id = {b.name: ensure_bone_id(b) for b in armature_bones}

    actions = _find_animated_actions_for_armature(armature_obj)
    if not actions:
        return []

    # Save original state for non-destructive restore
    orig_action = armature_obj.animation_data.action if armature_obj.animation_data else None
    orig_frame = scene.frame_current

    fps = float(scene.render.fps) / float(getattr(scene.render, "fps_base", 1.0))
    if fps <= 0.0:
        fps = 30.0

    extracted_clips: List[Dict[str, Any]] = []

    try:
        # Ensure animation_data exists
        if not armature_obj.animation_data:
            armature_obj.animation_data_create()

        for action in actions:
            anim_id = ensure_animation_id(action)
            armature_obj.animation_data.action = action

            start_frame = int(round(action.frame_range[0]))
            end_frame = int(round(action.frame_range[1]))
            if end_frame < start_frame:
                end_frame = start_frame

            total_frames = max(1, end_frame - start_frame)
            duration = round(total_frames / fps, 6)

            # Discover animated bone names in this action
            animated_bone_names: Set[str] = set()
            for fc in action.fcurves:
                m = BONE_PATH_RE.search(fc.data_path)
                if m and m.group(1) in bone_name_to_id:
                    animated_bone_names.add(m.group(1))

            if not animated_bone_names:
                # If no bone paths found (e.g. object-level action), animate root bones
                root_bones = [b.name for b in armature_bones if b.parent is None]
                animated_bone_names.update(root_bones)

            sorted_bone_names = sorted(list(animated_bone_names))

            # Sample each frame
            bone_tracks: Dict[str, Dict[str, Any]] = {}
            for bname in sorted_bone_names:
                bone_tracks[bname] = {
                    "bone_id": bone_name_to_id[bname],
                    "bone_name": bname,
                    "channels": {
                        "location": [],
                        "rotation": [],
                        "scale": [],
                    },
                }

            for f in range(start_frame, end_frame + 1):
                scene.frame_set(f)
                t = round((f - start_frame) / fps, 6)

                for bname in sorted_bone_names:
                    pbone = armature_obj.pose.bones.get(bname)
                    if not pbone:
                        continue

                    # Local pose matrix relative to parent pose bone
                    if pbone.parent:
                        parent_inv = pbone.parent.matrix.inverted()
                        local_mat = parent_inv @ pbone.matrix
                    else:
                        local_mat = pbone.matrix.copy()

                    loc, rot, sc = local_mat.decompose()

                    canon_loc = _convert_location((loc.x, loc.y, loc.z))
                    canon_rot = _convert_quaternion((rot.w, rot.x, rot.y, rot.z))
                    canon_sc = _convert_scale((sc.x, sc.y, sc.z))

                    bone_tracks[bname]["channels"]["location"].append({
                        "frame": float(f),
                        "time": t,
                        "value": [round(c, 6) for c in canon_loc],
                    })
                    bone_tracks[bname]["channels"]["rotation"].append({
                        "frame": float(f),
                        "time": t,
                        "value": [round(c, 6) for c in canon_rot],
                    })
                    bone_tracks[bname]["channels"]["scale"].append({
                        "frame": float(f),
                        "time": t,
                        "value": [round(c, 6) for c in canon_sc],
                    })

            ordered_tracks = [bone_tracks[bname] for bname in sorted_bone_names]

            clip_dict = {
                "id": anim_id,
                "name": action.name,
                "skeleton_id": skel_id,
                "frame_range": [start_frame, end_frame],
                "frame_rate": round(fps, 3),
                "duration": duration,
                "tracks": ordered_tracks,
            }
            extracted_clips.append(clip_dict)

    finally:
        # Non-destructive restoration of original state
        if armature_obj.animation_data:
            armature_obj.animation_data.action = orig_action
        scene.frame_set(orig_frame)

    return extracted_clips
