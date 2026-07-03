# config.py — every tunable knob lives here, so you never hunt through code.
from pathlib import Path

SEED = 42                      # fixed seed = same data every run = reproducible demo

# ---- Volume ----
N_FIRS       = 10000           # base number of crime cases (before injected patterns)
DATE_START   = "2023-01-01"
DATE_END     = "2025-12-31"    # 36 months of history

# ---- Hidden cast list (people) ----
N_PERSONS       = 12000        # big enough that one-off offenders are truly one-off
N_REPEATERS     = 250          # designated repeat solo offenders

# ---- Planted gangs (rings) ----
N_RINGS          = 4
RING_SIZE_RANGE  = (5, 8)      # members per ring
RING_CASE_SHARE  = 0.015         # was 0.02 — slightly lower to keep max cases < 30 per member
REPEAT_SHARE    = 0.15         # unchanged
# the rest are random one-off offenders

# ---- Paths (auto-created) ----
BASE   = Path(__file__).resolve().parent
OUT    = BASE / "output"        # PUBLIC
TRUTH  = BASE / "ground_truth"  # SECRET
OUT.mkdir(exist_ok=True)
TRUTH.mkdir(exist_ok=True)

# ---- Karnataka state code ----
KARNATAKA_STATE_ID = 29
