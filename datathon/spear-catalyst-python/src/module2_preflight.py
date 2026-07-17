"""
module2_preflight.py — verifies crime.db has everything Module 2 needs.
Run:  python src/module2_preflight.py
"""
import sqlite3, sys
from pathlib import Path

DB_PATH = Path("data/output/crime.db")   # ← adjust if your db lives elsewhere

REQUIRED = {
    "Accused":    ["AccusedMasterID", "CaseMasterID", "AccusedName",
                   "FatherName", "AgeYear", "GenderID"],
    "CaseMaster": ["CaseMasterID", "CrimeRegisteredDate", "CrimeMinorHeadID", "PoliceStationID"],
    "Unit":       ["UnitID", "DistrictID"],
}

def main():
    if not DB_PATH.exists():
        sys.exit(f"✗ {DB_PATH} not found — fix DB_PATH at the top of this file.")
    conn = sqlite3.connect(DB_PATH)
    ok = True
    for table, cols in REQUIRED.items():
        try:
            have = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        except sqlite3.OperationalError:
            print(f"✗ table {table} missing"); ok = False; continue
        missing = [c for c in cols if c not in have]
        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        mark = "✓" if not missing else "✗"
        print(f"{mark} {table}: {n} rows | columns present: {have}")
        if missing:
            print(f"   MISSING: {missing} — fix the COLS dict in module2_er.py")
            ok = False
    try:
        import rapidfuzz, networkx, pyvis
        print(f"✓ libs: rapidfuzz {rapidfuzz.__version__}, "
              f"networkx {networkx.__version__}, pyvis {pyvis.__version__}")
    except ImportError as e:
        print(f"✗ missing library: {e}"); ok = False
    print("\nPREFLIGHT:", "PASS — proceed to Phase 1" if ok else "FAIL — fix the ✗ items first")

if __name__ == "__main__":
    main()
