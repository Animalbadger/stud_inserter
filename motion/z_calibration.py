"""
Interactive Z travel calibration (run on the Raspberry Pi with hardware).

The controller does NOT sense where the shaft is if you move it by hand —
software position only updates when THIS code pulses STEP pins.

You slowly command small Z moves, watch the tip vs plate, then fix config.py.

There is no encoder: “reading” depth means trusting the **step counter** we update while
STEP pulses fire — not measuring the screw angle independently.

Do **not** rely on “kill the program” as your stop: human reaction + inertia can overshoot.
Use Ctrl+C in ``continuous_slow_probe_down`` (graceful), or the interactive ``s`` command.
"""

from __future__ import annotations

import argparse
import logging
import time

import config as cfg
from motion.homing import home_all_axes
from motion.motors import MotionController

_LOG = logging.getLogger(__name__)


def interactive_probe_z_max_down(
    controller: MotionController,
    *,
    home_first: bool = True,
    nudge_steps: int | None = None,
    margin_steps: int | None = None,
) -> int | None:
    """
    After homing (optional), nudge Z downward in small batches until you stop at the
    deepest *safe* travel (light touch / just above crash).

    Returns a suggested value for ``config.Z_MAX_DOWN_STEPS`` (measured z minus margin),
    or None if user quits without saving.

    Downward moves temporarily bypass ``Z_MAX_DOWN_STEPS`` so you can discover a new limit.
    """
    nudge = cfg.Z_CALIBRATION_NUDGE_STEPS if nudge_steps is None else nudge_steps
    margin = cfg.Z_CALIBRATION_MARGIN_STEPS if margin_steps is None else margin_steps
    ceiling = cfg.Z_CALIBRATION_ABS_CEILING_STEPS

    if home_first:
        _LOG.info("Homing before Z probe…")
        home_all_axes(controller)

    print()
    print(" Z max-down calibration")
    print("- .")
    print("- turn off the power supply if the machine starts tweeking. Stop BEFORE hardware crash.")
    print(f"- Each [Enter] moves DOWNward {nudge} steps (i bypassed the limits bypassed for downward probe).")
    print("- Commands: [Enter]=down  [u]=up same amount  [s]=print or shows you the suggested config and oress [q]=quit")
    print(f"- Abort if z would exceed {ceiling} (config Z_CALIBRATION_ABS_CEILING_STEPS).")
    print(f"- Current z = {controller.z} (0 = homed top)")
    print()

    while True:
        raw = input(f"z={controller.z}  Enter/u/s/q? ").strip().lower()

        if raw == "q":
            print("Quit without saving.")
            return None

        if raw == "s":
            measured_z = controller.z
            suggested = max(0, measured_z - margin)
            print()
            print(f"Measured depth z ≈ {measured_z} steps from the intial Z home.")
            print(f"Suggested set Z_MAX_DOWN_STEPS = {suggested}  (applied margin −{margin})")
            print("save this number and just send to me or save it")
            return suggested

        if raw == "u":
            controller.step_relative("z", -nudge, enforce_z_limits=True)
            continue

        if raw != "" and raw != "d":
            print("Unknown key; use Enter (down), u, s, or q.")
            continue

        # Down (default Enter or explicit)
        nz = controller.z + nudge
        if nz > ceiling:
            print(f"Refusing: z would exceed calibration ceiling ({ceiling}).")
            continue

        controller.step_relative("z", nudge, enforce_z_limits=False)


def continuous_slow_probe_down(
    controller: MotionController,
    *,
    home_first: bool = True,
    extra_delay_s: float | None = None,
    log_path: str | None = None,
) -> int | None:
    """
    Move Z **down one step at a time**, slowly, logging optional ``z`` after each step.

    Press **Ctrl+C** to stop: prints ``measured z`` and suggested ``Z_MAX_DOWN_STEPS``
    (minus margin). Returns suggested value or None if aborted before any downward motion.

    Still supervised — no plate detector yet; you stop when the gap looks right.
    """
    extra = (
        cfg.Z_CALIBRATION_SLOW_EXTRA_DELAY_S if extra_delay_s is None else extra_delay_s
    )
    ceiling = cfg.Z_CALIBRATION_ABS_CEILING_STEPS
    margin = cfg.Z_CALIBRATION_MARGIN_STEPS
    path = log_path
    if path is None:
        raw = getattr(cfg, "Z_CALIBRATION_SLOW_LOG_PATH", "") or ""
        path = raw.strip() or None

    if home_first:
        _LOG.info("Homing before slow Z probe…")
        home_all_axes(controller)

    z_start = controller.z
    print()
    print("=== Slow continuous Z probe (DOWN) ===")
    print(f"- One step per tick; extra pause {extra}s (motor pulse adds its own delay).")
    print("- Watch tip vs plate. Press Ctrl+C when you are at safe max depth.")
    print(f"- Hard ceiling z < {ceiling}")
    if path:
        print(f"- Appending z to {path}")
    print(f"- Starting z = {controller.z}")
    print()

    try:
        while controller.z < ceiling:
            controller.step_relative("z", 1, enforce_z_limits=False)
            if extra > 0:
                time.sleep(extra)
            if path:
                with open(path, "a", encoding="utf-8") as f:
                    f.write(f"{controller.z}\n")
    except KeyboardInterrupt:
        measured = controller.z
        suggested = max(0, measured - margin)
        print()
        if measured <= z_start:
            print("(You stopped before Z moved down — suggested limit may be meaningless.)")
        print(f"Stopped at z = {measured} (started from {z_start}).")
        print(f"Suggested: Z_MAX_DOWN_STEPS = {suggested}  (margin −{margin})")
        print("Put that in config.py.")
        return suggested

    print(f"Hit calibration ceiling z={ceiling} without Ctrl+C — increase ceiling if wrong.")
    return None


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Z depth calibration (Pi + hardware).")
    parser.add_argument(
        "--slow",
        action="store_true",
        help="Continuous one-step-down probe; Ctrl+C prints suggested Z_MAX_DOWN_STEPS",
    )
    args = parser.parse_args()

    motors = MotionController()
    motors.setup()
    try:
        if args.slow:
            continuous_slow_probe_down(motors)
        else:
            interactive_probe_z_max_down(motors)
    finally:
        motors.cleanup()


if __name__ == "__main__":
    main()
