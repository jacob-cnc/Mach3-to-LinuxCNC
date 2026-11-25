"""Machine constants for the 3040 mill, in machine units (inch).

These mirror config/mill-sim.ini. They are PLACEHOLDERS until the Phase 1
survey (see config/README.md); keep both files in step when values change.
The mock backend uses them for offline development; the live backend reads
limits from LinuxCNC itself.
"""

# Soft limits (machine coordinates). X and Y home at their minimum end,
# Z at the top.
X_MIN_LIMIT = 0.0
X_MAX_LIMIT = 15.5
Y_MIN_LIMIT = 0.0
Y_MAX_LIMIT = 11.5
Z_MIN_LIMIT = -3.0
Z_MAX_LIMIT = 0.0

X_HOME = 0.0
Y_HOME = 0.0
Z_HOME = 0.0

LIMITS = (
    (X_MIN_LIMIT, X_MAX_LIMIT),
    (Y_MIN_LIMIT, Y_MAX_LIMIT),
    (Z_MIN_LIMIT, Z_MAX_LIMIT),
)
HOMES = (X_HOME, Y_HOME, Z_HOME)

# Velocities (units/sec) and acceleration (units/sec^2)
MAX_VELOCITY = 0.65
MAX_ACCELERATION = 15.0
DEFAULT_JOG_VELOCITY = 0.25
MAX_JOG_VELOCITY = MAX_VELOCITY

# On-screen jog step choices (machine units). 0 = continuous (hold to move).
JOG_INCREMENTS_INCH = (0.0, 0.0001, 0.001, 0.01, 0.1)
JOG_INCREMENTS_MM = (0.0, 0.001, 0.01, 0.1, 1.0)   # in mm; converted on use
DEFAULT_JOG_INCREMENT_INDEX = 0

# Spindle (VFD, no encoder)
SPINDLE_MIN_RPM = 6000
SPINDLE_MAX_RPM = 24000
SPINDLE_DEFAULT_RPM = 12000
SPINUP_DELAY_S = 3.0

# Work coordinate systems, index = G10 L20 P number
WCS_NAMES = ("", "G54", "G55", "G56", "G57", "G58", "G59", "G59.1", "G59.2", "G59.3")
