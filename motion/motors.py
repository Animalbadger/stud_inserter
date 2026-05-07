"""
Step/dir GPIO interface with software position tracking.

Position convention (after homing in homing.py):
  X, Y: 0 at MIN-limit home; increasing position moves away from MIN toward MAX.
  Z:    0 at Z_HOME (top); increasing Z moves the tool downward toward the bed.

Tune config.X_POSITION_DELTA_DIR_HIGH (etc.) if an axis moves the wrong way logically.
"""

from __future__ import annotations

import logging
import time

import config as cfg

_LOG = logging.getLogger(__name__)

try:
    import RPi.GPIO as GPIO  # type: ignore

    _GPIO_AVAILABLE = True
except ImportError:
    GPIO = None  # type: ignore
    _GPIO_AVAILABLE = False


class MotionController:
    def __init__(self) -> None:
        self.x = 0
        self.y = 0
        self.z = 0
        self._gpio_initialized = False
        self._mock = cfg.MOCK_GPIO or not _GPIO_AVAILABLE

    def setup(self) -> None:
        if self._mock:
            _LOG.warning("MotionController running in MOCK mode (no GPIO).")
            self._gpio_initialized = True
            return

        GPIO.setmode(GPIO.BCM)
        for pin in (
            cfg.X_STEP_PIN,
            cfg.X_DIR_PIN,
            cfg.Y_STEP_PIN,
            cfg.Y_DIR_PIN,
            cfg.Z_STEP_PIN,
            cfg.Z_DIR_PIN,
        ):
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)

        for pin in (
            cfg.X_MIN_PIN,
            cfg.X_MAX_PIN,
            cfg.Y_MIN_PIN,
            cfg.Y_MAX_PIN,
            cfg.Z_HOME_PIN,
        ):
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        self._gpio_initialized = True

    def cleanup(self) -> None:
        if self._mock or not self._gpio_initialized:
            self._gpio_initialized = False
            return
        GPIO.cleanup()
        self._gpio_initialized = False

    def switch_pressed(self, pin: int) -> bool:
        """True when limit switch is active (contact to GND, LOW)."""
        if self._mock:
            return False
        return GPIO.input(pin) == GPIO.LOW

    def _limit_blocked(self, axis: str, logical_step: int) -> str | None:
        """
        Returns a message if motion is blocked by a pressed limit switch.

        logical_step: +1 means moving toward the MAX end, -1 toward the MIN end
        (based on our post-home coordinate convention).
        """
        if self._mock:
            return None

        if axis == "x":
            if logical_step < 0 and self.switch_pressed(cfg.X_MIN_PIN):
                return "X_MIN limit switch is pressed"
            if logical_step > 0 and self.switch_pressed(cfg.X_MAX_PIN):
                return "X_MAX limit switch is pressed"
        elif axis == "y":
            if logical_step < 0 and self.switch_pressed(cfg.Y_MIN_PIN):
                return "Y_MIN limit switch is pressed"
            if logical_step > 0 and self.switch_pressed(cfg.Y_MAX_PIN):
                return "Y_MAX limit switch is pressed"
        elif axis == "z":
            # Only a top/home switch exists right now.
            if logical_step < 0 and self.switch_pressed(cfg.Z_HOME_PIN):
                return "Z_HOME limit switch is pressed"

        return None

    def _axis_delay_s(self, axis: str) -> float:
        if axis in ("x", "y"):
            return getattr(cfg, "STEP_DELAY_XY_S", cfg.STEP_DELAY_S)
        return getattr(cfg, "STEP_DELAY_Z_S", cfg.STEP_DELAY_S)

    def _pulse_step_pin(self, step_pin: int, *, delay_s: float) -> None:
        delay = delay_s
        if self._mock:
            time.sleep(delay * 0.1)
            return
        GPIO.output(step_pin, GPIO.HIGH)
        time.sleep(delay)
        GPIO.output(step_pin, GPIO.LOW)
        time.sleep(delay)

    def set_dir_level(self, dir_pin: int, dir_high: bool) -> None:
        """Drive DIR pin (used by homing and internal stepping)."""
        if self._mock:
            return
        GPIO.output(dir_pin, GPIO.HIGH if dir_high else GPIO.LOW)

    def _set_dir(self, dir_pin: int, dir_high: bool) -> None:
        self.set_dir_level(dir_pin, dir_high)

    def _delta_cfg(self, axis: str) -> int:
        if axis == "x":
            return cfg.X_POSITION_DELTA_DIR_HIGH
        if axis == "y":
            return cfg.Y_POSITION_DELTA_DIR_HIGH
        if axis == "z":
            return cfg.Z_POSITION_DELTA_DIR_HIGH
        raise ValueError(axis)

    def _dir_high_for_soft_step(self, axis: str, signed_steps: int) -> bool:
        """DIR level so each pulse advances software coordinate by sign(signed_steps)."""
        dc = self._delta_cfg(axis)
        if signed_steps > 0:
            return dc > 0
        return dc < 0

    def _apply_z_limit_for_step(self, delta_z: int) -> None:
        new_z = self.z + delta_z
        if new_z < 0:
            raise RuntimeError(f"Z would exceed upward limit (z={self.z}, delta={delta_z}).")
        if new_z > cfg.Z_MAX_DOWN_STEPS:
            raise RuntimeError(
                f"Z would exceed Z_MAX_DOWN_STEPS ({cfg.Z_MAX_DOWN_STEPS}); "
                f"refusing move (z={self.z}, delta={delta_z})."
            )

    def _apply_xy_soft_limit_for_step(self, axis: str, coord_delta: int) -> None:
        if axis == "x":
            nx = self.x + coord_delta
            if nx < 0:
                raise RuntimeError(f"X would go negative (x={self.x}, delta={coord_delta}).")
            if cfg.X_MAX_SOFT_STEPS is not None and nx > cfg.X_MAX_SOFT_STEPS:
                raise RuntimeError(
                    f"X would exceed X_MAX_SOFT_STEPS ({cfg.X_MAX_SOFT_STEPS}); "
                    f"refusing move (x={self.x}, delta={coord_delta})."
                )
        elif axis == "y":
            ny = self.y + coord_delta
            if ny < 0:
                raise RuntimeError(f"Y would go negative (y={self.y}, delta={coord_delta}).")
            if cfg.Y_MAX_SOFT_STEPS is not None and ny > cfg.Y_MAX_SOFT_STEPS:
                raise RuntimeError(
                    f"Y would exceed Y_MAX_SOFT_STEPS ({cfg.Y_MAX_SOFT_STEPS}); "
                    f"refusing move (y={self.y}, delta={coord_delta})."
                )

    def step_relative(self, axis: str, signed_steps: int, *, enforce_z_limits: bool = True) -> None:
        """Move axis by signed step count; updates software position."""
        if signed_steps == 0:
            return
        axis = axis.lower()
        if axis not in ("x", "y", "z"):
            raise ValueError(axis)

        pins = {
            "x": (cfg.X_STEP_PIN, cfg.X_DIR_PIN),
            "y": (cfg.Y_STEP_PIN, cfg.Y_DIR_PIN),
            "z": (cfg.Z_STEP_PIN, cfg.Z_DIR_PIN),
        }
        step_pin, dir_pin = pins[axis]
        delay_s = self._axis_delay_s(axis)

        dc = self._delta_cfg(axis)
        logical_step = 1 if signed_steps > 0 else -1
        remaining = abs(int(signed_steps))
        dir_high = self._dir_high_for_soft_step(axis, signed_steps)
        coord_delta = logical_step * abs(int(dc))

        while remaining > 0:
            blocked = self._limit_blocked(axis, logical_step)
            if blocked is not None:
                raise RuntimeError(f"Blocked by limit switch: {blocked}")

            if axis in ("x", "y"):
                self._apply_xy_soft_limit_for_step(axis, coord_delta)
            if axis == "z" and enforce_z_limits:
                self._apply_z_limit_for_step(coord_delta)

            self._set_dir(dir_pin, dir_high)
            self._pulse_step_pin(step_pin, delay_s=delay_s)

            if axis == "x":
                self.x += coord_delta
            elif axis == "y":
                self.y += coord_delta
            else:
                self.z += coord_delta

            remaining -= 1

    def pulse_raw(self, step_pin: int, dir_pin: int, dir_high: bool, *, step_delay_s: float | None = None) -> None:
        """Single pulse without updating position (for internal homing backoff patterns)."""
        self._set_dir(dir_pin, dir_high)
        if self._mock:
            delay = step_delay_s if step_delay_s is not None else cfg.STEP_DELAY_S
            time.sleep(delay * 0.1)
            return
        delay = step_delay_s if step_delay_s is not None else cfg.STEP_DELAY_S
        GPIO.output(step_pin, GPIO.HIGH)
        time.sleep(delay)
        GPIO.output(step_pin, GPIO.LOW)
        time.sleep(delay)

    def ensure_safe_z_for_xy(self) -> None:
        """Raise Z until within Z_SAFE_FOR_XY_STEPS (tool clear for horizontal moves)."""
        while self.z > cfg.Z_SAFE_FOR_XY_STEPS:
            self.step_relative("z", -1)

    def set_position(self, x: int | None = None, y: int | None = None, z: int | None = None) -> None:
        """Set tracked position (used after homing)."""
        if x is not None:
            self.x = x
        if y is not None:
            self.y = y
        if z is not None:
            self.z = z
