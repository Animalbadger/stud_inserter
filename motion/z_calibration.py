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

def _read_key(timeout_s: float = 0.1) -> str | None:
    """
    Read a single keypress without requiring Enter (POSIX terminals only).
    Returns None if no key is available within timeout.
    """
    try:
        import select
        import sys

        if select.select([sys.stdin], [], [], timeout_s)[0]:
            ch = sys.stdin.read(1)
            return ch
        return None
    except Exception:
        return None


class _RawTerminal:
    """Context manager to put stdin into cbreak/raw-ish mode (POSIX only)."""

    def __enter__(self):
        import sys

        try:
            import termios
            import tty

            self._termios = termios
            self._fd = sys.stdin.fileno()
            self._old = termios.tcgetattr(self._fd)
            tty.setcbreak(self._fd)
            self._enabled = True
        except Exception:
            self._enabled = False
        return self

    def __exit__(self, exc_type, exc, tb):
        if not getattr(self, "_enabled", False):
            return False
        self._termios.tcsetattr(self._fd, self._termios.TCSADRAIN, self._old)
        return False

    @property
    def enabled(self) -> bool:
        return getattr(self, "_enabled", False)


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
    print("=== Jog + Z max-down calibration ===")
    print("- Keep hands near E-stop / power. Stop BEFORE hardware crash.")
    print(f"- Enter = Z down {nudge} steps (limits bypassed for probing)")
    print(f"- u = Z up {nudge} steps")
    print(f"- a/d = X left/right {cfg.XY_CALIBRATION_NUDGE_STEPS} steps")
    print(f"- w/x = Y forward/back {cfg.XY_CALIBRATION_NUDGE_STEPS} steps")
    print("- s = print suggested Z_MAX_DOWN_STEPS and exit")
    print("- q = quit")
    print("- Note: before any X/Y move, Z will auto-raise to Z_SAFE_FOR_XY_STEPS.")
    print(f"- Abort if z would exceed {ceiling} (config Z_CALIBRATION_ABS_CEILING_STEPS).")
    print(f"- Current position (steps): x={controller.x} y={controller.y} z={controller.z}  (z=0 is homed top)")
    print()

    print("Press keys directly (no Enter needed). If keys don't register, run from a real Pi terminal (not some IDE consoles).")
    print()

    with _RawTerminal() as rt:
        if not rt.enabled:
            print("Raw key mode unavailable here; falling back to line input (requires Enter).")

        while True:
            if rt.enabled:
                ch = _read_key(0.1)
                if ch is None:
                    continue
                key = ch.lower()
            else:
                key = input(f"x={controller.x} y={controller.y} z={controller.z}  key? ").strip().lower()
                if key == "":
                    key = "\n"

            if key in ("q",):
                print("Quit without saving.")
                return None

            if key in ("s",):
                measured_z = controller.z
                suggested = max(0, measured_z - margin)
                print()
                print(f"Measured depth z ≈ {measured_z} steps from Z home (z=0).")
                print(f"Suggested: set Z_MAX_DOWN_STEPS = {suggested}  (applied margin −{margin})")
                print("Copy into config.py, save, then restart your program.")
                return suggested

            if key in ("u", "r"):
                try:
                    controller.step_relative("z", -nudge, enforce_z_limits=True)
                except RuntimeError as e:
                    print(f"Blocked: {e}")
                continue

            if key in ("\n", "\r", "f"):
                # Down
                nz = controller.z + nudge
                if nz > ceiling:
                    print(f"Refusing: z would exceed calibration ceiling ({ceiling}).")
                    continue
                controller.step_relative("z", nudge, enforce_z_limits=False)
                continue

            if key in ("a", "d", "w", "x"):
                try:
                    controller.ensure_safe_z_for_xy()
                    xy = cfg.XY_CALIBRATION_NUDGE_STEPS
                    if key == "a":
                        controller.step_relative("x", -xy)
                    elif key == "d":
                        controller.step_relative("x", xy)
                    elif key == "w":
                        controller.step_relative("y", xy)
                    else:  # "x"
                        controller.step_relative("y", -xy)
                except RuntimeError as e:
                    print(f"Blocked: {e}")
                continue

            # ignore unknown keys (arrow keys send escape sequences etc.)


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
