"""
Application entry: home machine first, then run vision (or other phases).
"""

from __future__ import annotations

import logging

from motion.homing import home_all_axes
from motion.motors import MotionController
from vision.detect import get_holes


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    motors = MotionController()
    motors.setup()
    try:
        home_all_axes(motors)
        logging.info("Starting detection after homing")

        holes = get_holes()

        logging.info("Holes found:")
        for h in holes:
            logging.info("  %s", h)
    finally:
        motors.cleanup()


if __name__ == "__main__":
    main()
