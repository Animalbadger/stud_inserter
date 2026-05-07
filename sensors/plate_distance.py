"""
Plate-distance sensing — NOT INSTALLED YET.

Keep this stub so import paths stay stable; `read_mm()` always returns None until
the team wires hardware and uncomments the sensor section in config.py.
"""

from __future__ import annotations


class PlateDistanceSensor:
    """Reserved for arm-mount → plate ranging (not pen tip)."""

    def read_mm(self) -> float | None:
        return None