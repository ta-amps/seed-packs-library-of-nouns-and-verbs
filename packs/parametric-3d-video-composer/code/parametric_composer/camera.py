"""3D perspective Product Hub (1x3 and 2x2) camera trajectory planner and pinhole projector."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence

SCREEN_W = 1920
SCREEN_H = 1080
STAGE_CENTER_X = 960.0
STAGE_CENTER_Y = 446.0  # Midpoint of safe stage y: 72..820


@dataclass(frozen=True)
class CameraPose:
    """3D pinhole camera pose looking toward the z=0 stage plane from positive z."""

    x: float
    y: float
    z: float
    yaw_deg: float = 0.0
    pitch_deg: float = 0.0
    fov_deg: float = 45.0

    def to_dict(self) -> dict[str, float]:
        return {
            "x": round(self.x, 3),
            "y": round(self.y, 3),
            "z": round(self.z, 3),
            "yaw_deg": round(self.yaw_deg, 3),
            "pitch_deg": round(self.pitch_deg, 3),
            "fov_deg": round(self.fov_deg, 3),
        }


def quintic_ease(u: float) -> float:
    """C2-continuous quintic smootherstep with zero first and second derivatives at u=0 and u=1."""
    t = max(0.0, min(1.0, float(u)))
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def interpolate_pose(a: CameraPose, b: CameraPose, u: float) -> CameraPose:
    s = quintic_ease(u)
    return CameraPose(
        x=a.x + (b.x - a.x) * s,
        y=a.y + (b.y - a.y) * s,
        z=a.z + (b.z - a.z) * s,
        yaw_deg=a.yaw_deg + (b.yaw_deg - a.yaw_deg) * s,
        pitch_deg=a.pitch_deg + (b.pitch_deg - a.pitch_deg) * s,
        fov_deg=a.fov_deg + (b.fov_deg - a.fov_deg) * s,
    )


def focal_length_px(fov_deg: float, screen_h: int = SCREEN_H) -> float:
    half_rad = math.radians(max(5.0, min(120.0, fov_deg)) * 0.5)
    return (screen_h * 0.5) / math.tan(half_rad)


def project_point_3d(
    world_xyz: tuple[float, float, float],
    pose: CameraPose,
    *,
    screen_w: int = SCREEN_W,
    screen_h: int = SCREEN_H,
) -> tuple[float, float]:
    """Project a 3D world point `(wx, wy, wz)` onto 2D screen coordinates `(sx, sy)`.

    World coordinates place `(STAGE_CENTER_X, STAGE_CENTER_Y, 0)` at the center of the safe stage
    when the camera sits at `(STAGE_CENTER_X, STAGE_CENTER_Y, z_overview)` with zero yaw/pitch.
    """
    dx = world_xyz[0] - pose.x
    dy = world_xyz[1] - pose.y
    dz = pose.z - world_xyz[2]  # Positive depth in front of camera

    yaw = math.radians(pose.yaw_deg)
    pitch = math.radians(pose.pitch_deg)

    # Rotate around Y (yaw)
    rx = dx * math.cos(yaw) - dz * math.sin(yaw)
    rz1 = dx * math.sin(yaw) + dz * math.cos(yaw)
    # Rotate around X (pitch)
    ry = dy * math.cos(pitch) - rz1 * math.sin(pitch)
    rz = max(1.0, dy * math.sin(pitch) + rz1 * math.cos(pitch))

    f = focal_length_px(pose.fov_deg, screen_h=screen_h)
    sx = (screen_w * 0.5) + (rx * f / rz)
    # Shift optical principal Y to STAGE_CENTER_Y so overview/focus keep stage cards out of caption band
    sy = STAGE_CENTER_Y + (ry * f / rz)
    return round(sx, 2), round(sy, 2)


def build_product_hub_cards(grid_mode: str = "1x3", pillar_ids: Sequence[str] | None = None) -> list[dict[str, Any]]:
    """Build world-space pillar cards inside the safe stage `x: 96..1824, y: 72..820` on `z = 0`."""
    if grid_mode == "1x3":
        ids = list(pillar_ids) if pillar_ids is not None else ["pillar-1", "pillar-2", "pillar-3"]
        if len(ids) != 3:
            raise ValueError("1x3 grid_mode requires 3 pillar_ids")
        card_w, card_h, gap_x = 500.0, 560.0, 48.0
        total_w = 3 * card_w + 2 * gap_x
        start_x = STAGE_CENTER_X - total_w * 0.5
        y0 = STAGE_CENTER_Y - card_h * 0.5
        cards = []
        for idx, pid in enumerate(ids):
            x0 = start_x + idx * (card_w + gap_x)
            cards.append({
                "id": pid,
                "grid_index": idx,
                "box": [round(x0, 1), round(y0, 1), round(x0 + card_w, 1), round(y0 + card_h, 1)],
                "center": [round(x0 + card_w * 0.5, 1), round(y0 + card_h * 0.5, 1), 0.0],
            })
        return cards

    if grid_mode == "2x2":
        ids = list(pillar_ids) if pillar_ids is not None else ["pillar-1", "pillar-2", "pillar-3", "pillar-4"]
        if len(ids) != 4:
            raise ValueError("2x2 grid_mode requires 4 pillar_ids")
        card_w, card_h, gap_x, gap_y = 720.0, 310.0, 56.0, 36.0
        start_x = STAGE_CENTER_X - (2 * card_w + gap_x) * 0.5
        start_y = STAGE_CENTER_Y - (2 * card_h + gap_y) * 0.5
        cards = []
        for idx, pid in enumerate(ids):
            row, col = divmod(idx, 2)
            x0 = start_x + col * (card_w + gap_x)
            y0 = start_y + row * (card_h + gap_y)
            cards.append({
                "id": pid,
                "grid_index": idx,
                "box": [round(x0, 1), round(y0, 1), round(x0 + card_w, 1), round(y0 + card_h, 1)],
                "center": [round(x0 + card_w * 0.5, 1), round(y0 + card_h * 0.5, 1), 0.0],
            })
        return cards

    raise ValueError(f"unsupported grid_mode: {grid_mode!r}; expected '1x3' or '2x2'")


def plan_product_hub_trajectory(
    grid_mode: str = "1x3",
    pillar_ids: Sequence[str] | None = None,
    *,
    fov_deg: float = 45.0,
    overview_hold_s: float = 2.0,
    zoom_s: float = 0.9,
    pillar_hold_s: float = 3.2,
    bridge_hold_s: float = 0.8,
    finale_hold_s: float = 2.4,
) -> dict[str, Any]:
    """Plan overview -> pillar_focus -> bridge_zoom_out -> next_pillar -> finale_hub camera trajectory."""
    cards = build_product_hub_cards(grid_mode=grid_mode, pillar_ids=pillar_ids)
    f_px = focal_length_px(fov_deg)
    z_overview = round(f_px, 2)  # 1:1 pixel scale at z = f_px
    z_bridge = round(f_px * 0.94, 2)  # Subtle closer overview during inter-pillar bridge
    z_focus = round(f_px * 0.56, 2) if grid_mode == "1x3" else round(f_px * 0.52, 2)

    overview_pose = CameraPose(x=STAGE_CENTER_X, y=STAGE_CENTER_Y, z=z_overview, yaw_deg=0.0, pitch_deg=0.0, fov_deg=fov_deg)
    bridge_pose = CameraPose(x=STAGE_CENTER_X, y=STAGE_CENTER_Y, z=z_bridge, yaw_deg=0.0, pitch_deg=1.2, fov_deg=fov_deg)

    segments: list[dict[str, Any]] = []
    t = 0.0

    def _add_seg(phase: str, target_id: str, start_pose: CameraPose, end_pose: CameraPose, dur: float) -> None:
        nonlocal t
        segments.append({
            "phase": phase,
            "target": target_id,
            "t_start": round(t, 3),
            "t_end": round(t + dur, 3),
            "duration_s": round(dur, 3),
            "start_pose": start_pose.to_dict(),
            "end_pose": end_pose.to_dict(),
        })
        t += dur

    # 1. Opening hub overview
    _add_seg("overview", "hub", overview_pose, overview_pose, overview_hold_s)
    current = overview_pose

    for idx, card in enumerate(cards):
        cx, cy, _ = card["center"]
        # Subtle inward perspective yaw toward outer cards for 3D depth parallax without distortion
        yaw = round((cx - STAGE_CENTER_X) / 900.0 * -3.5, 3)
        pitch = round((cy - STAGE_CENTER_Y) / 600.0 * -2.0, 3)
        focus_pose = CameraPose(x=cx, y=cy, z=z_focus, yaw_deg=yaw, pitch_deg=pitch, fov_deg=fov_deg)

        _add_seg("zoom_in", card["id"], current, focus_pose, zoom_s)
        _add_seg("pillar_focus", card["id"], focus_pose, focus_pose, pillar_hold_s)

        if idx < len(cards) - 1:
            _add_seg("bridge_zoom_out", "hub_bridge", focus_pose, bridge_pose, zoom_s)
            _add_seg("bridge_hold", "hub_bridge", bridge_pose, bridge_pose, bridge_hold_s)
            current = bridge_pose
        else:
            _add_seg("finale_zoom_out", "hub", focus_pose, overview_pose, zoom_s)
            _add_seg("finale_hub", "hub", overview_pose, overview_pose, finale_hold_s)
            current = overview_pose

    return {
        "grid_mode": grid_mode,
        "total_duration_s": round(t, 3),
        "cards": cards,
        "segments": segments,
    }


def sample_trajectory(plan: dict[str, Any], t_s: float) -> CameraPose:
    """Evaluate exact CameraPose at timestamp `t_s` along a planned trajectory."""
    segs = plan["segments"]
    if not segs:
        raise ValueError("trajectory has no segments")
    if t_s <= segs[0]["t_start"]:
        p = segs[0]["start_pose"]
        return CameraPose(**p)
    for seg in segs:
        if seg["t_start"] <= t_s <= seg["t_end"]:
            sp = CameraPose(**seg["start_pose"])
            ep = CameraPose(**seg["end_pose"])
            dur = max(1e-9, seg["t_end"] - seg["t_start"])
            return interpolate_pose(sp, ep, (t_s - seg["t_start"]) / dur)
    p = segs[-1]["end_pose"]
    return CameraPose(**p)
