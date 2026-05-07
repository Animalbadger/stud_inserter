"""
Insert-related sequences (pickup, place) built on MotionController.

All coordinates here are in *machine steps* after homing:
  X=0, Y=0 at MIN limits; Z=0 at top home; +Z moves downward.
"""

from __future__ import annotations

import logging

from motion.homing import home_all_axes
from motion.motors import MotionController

_LOG = logging.getLogger(__name__)


def _move_to_steps(controller: MotionController, *, x: int | None = None, y: int | None = None, z: int | None = None) -> None:
    """
    Very simple absolute move helper (not coordinated).

    Safety rule: if X/Y will move, auto-raise to safe Z first.
    """
    target_x = controller.x if x is None else int(x)
    target_y = controller.y if y is None else int(y)
    target_z = controller.z if z is None else int(z)

    will_move_xy = (target_x != controller.x) or (target_y != controller.y)
    if will_move_xy:
        controller.ensure_safe_z_for_xy()

    dx = target_x - controller.x
    dy = target_y - controller.y
    dz = target_z - controller.z

    if dx:
        controller.step_relative("x", dx)
    if dy:
        controller.step_relative("y", dy)
    if dz:
        controller.step_relative("z", dz, enforce_z_limits=True)


def pickup_insert(
    controller: MotionController,
    *,
    home_first: bool = True,
    above_x: int = 13050,
    above_y: int = 1050,
    above_y_offset: int = -10,
    above_z: int = 6950,
    hook_z: int = 7550,
    retract_z: int = 4500,
    x_backoff_steps: int = 500,
) -> None:
    """
    3-stage pickup:
      1) Move above the insert (x,y,z)
      2) Push down to hook depth (same x,y, deeper z)
      3) Retract to safe-ish height and back X off a bit
    """
    if home_first:
        _LOG.info("Homing before pickup sequence")
        home_all_axes(controller)

    target_y = above_y + above_y_offset
    _LOG.info(
        "Pickup stage 1: above insert -> x=%s y=%s (base %s + off %s) z=%s",
        above_x,
        target_y,
        above_y,
        above_y_offset,
        above_z,
    )
    _move_to_steps(controller, x=above_x, y=target_y, z=above_z)

    _LOG.info("Pickup stage 2: hook/press -> z=%s", hook_z)
    _move_to_steps(controller, z=hook_z)

    _LOG.info("Pickup stage 3: retract -> z=%s, backoff x by %s steps", retract_z, x_backoff_steps)
    _move_to_steps(controller, z=retract_z)
    if x_backoff_steps:
        _move_to_steps(controller, x=max(0, controller.x - int(x_backoff_steps)))

    _LOG.info("Pickup complete. Current coords: x=%s y=%s z=%s", controller.x, controller.y, controller.z)


def main() -> None:
    """
    Runner for quick hardware testing on the Pi:
      python -m actions.insert
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    motors = MotionController()
    motors.setup()
    try:
        pickup_insert(motors, home_first=True)
    finally:
        motors.cleanup()


if __name__ == "__main__":
    main()

