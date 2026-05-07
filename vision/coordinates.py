"""
Link camera pixels to the machine coordinate frame (steps).

After homing (see motion/homing.py), software tracks:
  X, Y: origin at MIN-limit home; +X / +Y move toward MAX limits (within workspace).
  Z:      origin at Z_HOME (top); increasing Z moves downward toward the bed.

The camera sees a 2D image (u right, v down). That is NOT the same as machine X/Y
until you calibrate: fixed mounting means a linear map or homography from (u, v)
→ (x_steps, y_steps), plus ordering holes for the toolpath.

Workflow later:
  1. Fix camera aim and lighting.
  2. Pick a reference: e.g. jog so machine (0,0) sits under a known image point, or use a fiducial.
  3. Measure steps-per-pixel (or full 3×3 homography) and enter constants in config.py.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HolePixel:
    """Hole centre from vision (image coordinates)."""

    u: int
    v: int


@dataclass(frozen=True)
class HoleSteps:
    """Same hole expressed in machine steps (after calibration)."""

    x_steps: int
    y_steps: int


def holes_pixels_to_steps(pixels: list[tuple[int, int]]) -> list[HoleSteps]:
    """
    Convert detected hole centres to machine X/Y steps.

    Raises RuntimeError until vision→machine calibration is filled in config and enabled.
    """
    import config as cfg  # local import keeps startup light if config grows imports

    if not cfg.VISION_TO_MACHINE_READY:
        raise RuntimeError(
            "Vision→machine calibration not enabled. Set VISION_TO_MACHINE_READY=True in "
            "config.py after measuring origin and steps-per-pixel (see comments there)."
        )

    origin_u = cfg.VISION_ORIGIN_PIXEL_U
    origin_v = cfg.VISION_ORIGIN_PIXEL_V
    spx = cfg.VISION_STEPS_PER_PIXEL_X
    spy = cfg.VISION_STEPS_PER_PIXEL_Y

    out: list[HoleSteps] = []
    for u, v in pixels:
        du = u - origin_u
        dv = v - origin_v
        x_steps = int(round(du * spx))
        y_steps = int(round(dv * spy))
        out.append(HoleSteps(x_steps=x_steps, y_steps=y_steps))
    return out


def sort_holes_for_path(holes: list[HoleSteps]) -> list[HoleSteps]:
    """Stable machine-friendly order: sort by Y then X (row-major)."""
    return sorted(holes, key=lambda h: (h.y_steps, h.x_steps))
