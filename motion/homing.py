"""
Homing sequence: Z first (lift tool), then X, then Y.

Uses backoff + slow second touch like the legacy prototype, with a hard step cap per phase.
"""

from __future__ import annotations

import logging

import config as cfg
from motion.motors import MotionController

_LOG = logging.getLogger(__name__)


def _seek_until_pressed(
    controller: MotionController,
    *,
    step_pin: int,
    dir_pin: int,
    toward_switch_dir_high: bool,
    switch_pin: int,
    max_steps: int,
    step_delay_s: float | None = None,
) -> int:
    """
    Step until switch becomes pressed (active LOW). Returns step count.
    Raises RuntimeError if max_steps exceeded.
    """
    controller.set_dir_level(dir_pin, toward_switch_dir_high)
    steps = 0
    while not controller.switch_pressed(switch_pin):
        controller.pulse_raw(step_pin, dir_pin, toward_switch_dir_high, step_delay_s=step_delay_s)
        steps += 1
        if steps >= max_steps:
            raise RuntimeError(
                f"Homing seek timeout: switch on pin {switch_pin} not reached after {max_steps} steps."
            )
    return steps


def _pulse_fixed(
    controller: MotionController,
    *,
    step_pin: int,
    dir_pin: int,
    dir_high: bool,
    count: int,
    step_delay_s: float | None = None,
) -> None:
    for _ in range(count):
        controller.pulse_raw(step_pin, dir_pin, dir_high, step_delay_s=step_delay_s)


def _home_one_axis(
    controller: MotionController,
    name: str,
    *,
    step_pin: int,
    dir_pin: int,
    switch_pin: int,
    home_dir_high: bool,
    backoff_steps: int,
) -> None:
    _LOG.info("Homing %s...", name)

    if controller._mock:
        _LOG.info("(mock) %s homed", name)
        return

    # First approach until switch trips
    _seek_until_pressed(
        controller,
        step_pin=step_pin,
        dir_pin=dir_pin,
        toward_switch_dir_high=home_dir_high,
        switch_pin=switch_pin,
        max_steps=cfg.HOMING_MAX_SEEK_STEPS,
        step_delay_s=None,
    )
    _LOG.info("%s hit switch", name)

    # Back off (reverse direction)
    away_high = not home_dir_high
    _pulse_fixed(
        controller,
        step_pin=step_pin,
        dir_pin=dir_pin,
        dir_high=away_high,
        count=backoff_steps,
        step_delay_s=None,
    )

    # Slow second touch
    _seek_until_pressed(
        controller,
        step_pin=step_pin,
        dir_pin=dir_pin,
        toward_switch_dir_high=home_dir_high,
        switch_pin=switch_pin,
        max_steps=cfg.HOMING_MAX_SEEK_STEPS,
        step_delay_s=cfg.HOMING_SLOW_STEP_DELAY_S,
    )
    _LOG.info("%s homed (second touch)", name)


def home_all_axes(controller: MotionController) -> None:
    """
    Full machine homing. Order: Z -> X -> Y.

    Sets software position to X=0, Y=0, Z=0 at the mechanical home reference.
    """
    _LOG.info("Starting homing sequence")

    if controller._mock:
        controller.set_position(0, 0, 0)
        _LOG.info("Homing complete (mock). Position X=0 Y=0 Z=0")
        return

    # --- Z first ---
    _home_one_axis(
        controller,
        "Z",
        step_pin=cfg.Z_STEP_PIN,
        dir_pin=cfg.Z_DIR_PIN,
        switch_pin=cfg.Z_HOME_PIN,
        home_dir_high=cfg.Z_HOME_DIR_HIGH,
        backoff_steps=cfg.HOMING_BACKOFF_STEPS,
    )
    controller.set_position(z=0)

    # --- X ---
    _home_one_axis(
        controller,
        "X",
        step_pin=cfg.X_STEP_PIN,
        dir_pin=cfg.X_DIR_PIN,
        switch_pin=cfg.X_MIN_PIN,
        home_dir_high=cfg.X_HOME_DIR_HIGH,
        backoff_steps=cfg.HOMING_BACKOFF_STEPS,
    )
    controller.set_position(x=0)

    # --- Y ---
    _home_one_axis(
        controller,
        "Y",
        step_pin=cfg.Y_STEP_PIN,
        dir_pin=cfg.Y_DIR_PIN,
        switch_pin=cfg.Y_MIN_PIN,
        home_dir_high=cfg.Y_HOME_DIR_HIGH,
        backoff_steps=cfg.HOMING_BACKOFF_STEPS,
    )
    controller.set_position(y=0)

    _LOG.info("Homing complete. Position X=%s Y=%s Z=%s", controller.x, controller.y, controller.z)
