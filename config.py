"""
Hardware and motion calibration — tune on the Raspberry Pi.

Pins match the legacy try.py prototype (BCM numbering).
"""

# this section is for the GPIO: step / direction (BCM) 
X_STEP_PIN = 17
X_DIR_PIN = 27
Y_STEP_PIN = 22
Y_DIR_PIN = 23
Z_STEP_PIN = 24
Z_DIR_PIN = 25

# these are  Limit switches (BCM), inputs with pull-up; active when LOW 
X_MIN_PIN = 5
X_MAX_PIN = 6
Y_MIN_PIN = 13
Y_MAX_PIN = 19
Z_HOME_PIN = 26

# Pulse timing (seconds each half-period of one step pulse)
STEP_DELAY_S = 0.0015

# Homing: DIR pin level used while moving toward the switch (see motors pulse semantics)
X_HOME_DIR_HIGH = False
Y_HOME_DIR_HIGH = False
Z_HOME_DIR_HIGH = True

# Back off after first switch hit, then slow re-approach (steps)
HOMING_BACKOFF_STEPS = 800

# Safety: abort homing if switch never trips (steps limit per seek phase)
HOMING_MAX_SEEK_STEPS = 200_000

# Slow re-approach uses a longer delay for gentler contact
HOMING_SLOW_STEP_DELAY_S = 0.003

# ---------------------------------------------------------------------------
# Software limits & safe motion (steps, signed position from home origin)
# Origin after homing: X=0, Y=0, Z=0 at limit-defined home (see homing module).
# Tune Z_* once you measure travel on hardware.
# ---------------------------------------------------------------------------

# When DIR is HIGH, position delta per pulse (+1 or -1). Flip if an axis runs backward.
X_POSITION_DELTA_DIR_HIGH = 1
Y_POSITION_DELTA_DIR_HIGH = 1
Z_POSITION_DELTA_DIR_HIGH = -1

# Maximum downward travel from Z home (0); refuse pulses that would exceed this.
# You do not need to feed us a number before first bring-up: these defaults are guesses.
# After homing, jog Z down slowly toward the plate, note steps at safe contact, then set
# Z_MAX_DOWN_STEPS slightly below that. Same idea for Z_SAFE_FOR_XY_STEPS = “high enough
# to skim X/Y without hitting the part.”
Z_MAX_DOWN_STEPS = 7_650
Z_SAFE_FOR_XY_STEPS = 3_500

# Interactive Z calibration (motion/z_calibration.py — Pi only, supervised)
Z_CALIBRATION_NUDGE_STEPS = 50
Z_CALIBRATION_MARGIN_STEPS = 200  # subtract from measured z for Z_MAX_DOWN_STEPS suggestion
Z_CALIBRATION_ABS_CEILING_STEPS = 50_000  # refuse probing deeper than this (safety net)

# continuous_slow_probe_down(): extra pause after each downward step (seconds)
Z_CALIBRATION_SLOW_EXTRA_DELAY_S = 0.03
# If non-empty, append one "z" integer per line while probing (e.g. "z_probe_log.txt")
Z_CALIBRATION_SLOW_LOG_PATH = ""

# Jog step size for X/Y inside motion/z_calibration.py (steps per keypress)
XY_CALIBRATION_NUDGE_STEPS = 50

# XY software envelope (steps). After homing, X and Y are >= 0 at MIN limits.
# Set to integers when you know usable travel; None = do not enforce in software yet
# (physical MAX limits still apply in hardware).
X_MAX_SOFT_STEPS = None
Y_MAX_SOFT_STEPS = None

# Optional: mock GPIO when developing off-Pi (RPi.GPIO missing)
MOCK_GPIO = False

# ---------------------------------------------------------------------------
# Camera pixels → machine steps (for plotting / visiting holes)
# Set VISION_TO_MACHINE_READY True only after you measure these on the real rig.
# ---------------------------------------------------------------------------
VISION_TO_MACHINE_READY = False
VISION_ORIGIN_PIXEL_U = 0  # image pixel where machine X=0 reference sits
VISION_ORIGIN_PIXEL_V = 0  # image pixel where machine Y=0 reference sits
VISION_STEPS_PER_PIXEL_X = 1.0
VISION_STEPS_PER_PIXEL_Y = 1.0

# ---------------------------------------------------------------------------
# Plate distance sensor — NOT INSTALLED YET (team wiring later).
# Uncomment and wire when hardware exists:
#
# PLATE_DISTANCE_SENSOR_ENABLED = False
# PLATE_DISTANCE_I2C_BUS = 1
# PLATE_DISTANCE_I2C_ADDR = 0x29
# PLATE_DISTANCE_TRIG_PIN = None
# PLATE_DISTANCE_ECHO_PIN = None
# PLATE_DISTANCE_MM_PER_UNIT = 1.0
# PLATE_DISTANCE_OFFSET_MM = 0.0
# ---------------------------------------------------------------------------
