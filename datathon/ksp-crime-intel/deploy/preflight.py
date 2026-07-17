"""
deploy/preflight.py — inventory crime.db + confirm the local helpers Phase 1 needs.
Run from repo root:  python deploy/preflight.py
"""
import sqlite3, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DB = ROOT / "data" / "output" / "crime.db"      # ← adjust if yours differs

def main():
    if not DB.exists():
        sys.exit(f"✗ {DB} not found — fix DB at the top of this file.")
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    print(f"crime.db tables ({len(rows)}):\n")
    for (t,) in rows:
        n = conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{t}")')]
        print(f"  {t:<24} {n:>7} rows   {cols}")

    print("\n--- local helper check ---")
    ok = True
    try:
        from src import db
        cases = db.load_cases()
        print(f"✓ src.db.load_cases() → {len(cases)} rows, columns: {list(cases.columns)}")
    except Exception as e:
        print(f"✗ src.db.load_cases() failed: {e}"); ok = False
    try:
        from src import module1_geo as m1
        for fn in ["find_hotspots", "hotspot_summary", "spike_alerts", "time_heatmap_matrix"]:
            mark = "✓" if hasattr(m1, fn) else "✗"
            print(f"{mark} src.module1_geo.{fn}")
            ok &= hasattr(m1, fn)
    except Exception as e:
        print(f"✗ src.module1_geo import failed: {e}"); ok = False

    print("\n--- reports/ ---")
    for f in sorted((ROOT / "reports").glob("*.json")) if (ROOT/"reports").exists() else []:
        print(f"  ✓ {f.name}")

    print("\nPREFLIGHT:", "PASS — proceed to Phase 1" if ok else "FAIL — fix ✗ items")

if __name__ == "__main__":
    main()
