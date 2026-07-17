"""
module3_preflight.py — verifies crime.db + libs, and DISCOVERS ground-truth files.
Run:  python src/module3_preflight.py
"""
import sqlite3, sys
from pathlib import Path
import pandas as pd

DB_PATH    = Path("data/output/crime.db")
TRUTH_DIR  = Path("data/ground_truth")

REQUIRED_TABLES = ["CaseMaster", "DistrictProfile"]

def main():
    ok = True
    if not DB_PATH.exists():
        sys.exit(f"✗ {DB_PATH} not found")
    conn = sqlite3.connect(DB_PATH)

    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")]
    print("Tables in crime.db:", ", ".join(sorted(tables)), "\n")

    for t in REQUIRED_TABLES:
        if t not in tables:
            print(f"✗ table {t} missing"); ok = False; continue
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({t})")]
        n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"✓ {t}: {n} rows")
        print(f"   columns: {cols}\n")

    # Module 2 artifacts (risk tab links entities later; not strictly required)
    for t in ["EntityProfile", "ResolvedLink"]:
        print(("✓" if t in tables else "•"), t,
              "(present)" if t in tables else "(absent — fine, M3 doesn't need it)")

    print("\n--- ground_truth/ discovery (exam will need these) ---")
    if not TRUTH_DIR.exists():
        print("✗ data/ground_truth/ not found"); ok = False
    else:
        for f in sorted(TRUTH_DIR.glob("*.csv")):
            try:
                head = pd.read_csv(f, nrows=3)
                print(f"\n📄 {f.name}  ({len(pd.read_csv(f))} rows)")
                print("   columns:", list(head.columns))
                print(head.to_string(index=False))
            except Exception as e:
                print(f"✗ could not read {f.name}: {e}"); ok = False

    try:
        import sklearn, statsmodels
        print(f"\n✓ libs: scikit-learn {sklearn.__version__}, "
              f"statsmodels {statsmodels.__version__}")
    except ImportError as e:
        print(f"\n✗ missing library: {e}"); ok = False

    print("\nPREFLIGHT:", "PASS — proceed to Phase 1" if ok else "FAIL — fix ✗ items")

if __name__ == "__main__":
    main()
