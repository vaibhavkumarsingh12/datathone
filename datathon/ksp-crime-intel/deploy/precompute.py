"""
deploy/precompute.py — SPEAR intelligence factory → serving database.

Reads crime.db (+ Module 2/3 result tables + reports/*.json), runs the Module 1
analytics across a fixed parameter grid, and writes deploy/spear-catalyst/data/spear.db
— a denormalised, indexed, READ-ONLY database the Flask app serves with the standard
library alone.

Run from repo root:   python deploy/precompute.py        (~2–6 min)
"""
from __future__ import annotations
import json, sqlite3, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
from src import db
from src import module1_geo as m1

SRC_DB = ROOT / "data" / "output" / "crime.db"
OUT_DB = ROOT / "deploy" / "spear-catalyst" / "data" / "spear.db"
GEOJSON_OUT = ROOT / "deploy" / "spear-catalyst" / "static" / "karnataka.geojson"

# ---- hotspot parameter grid -------------------------------------------------
# 4 × 3 = 12 param sets per scope. Shrink if the build is slow or spear.db > 80 MB.
EPS_GRID  = [1.0, 2.0, 3.5, 5.0]
MINS_GRID = [15, 25, 40]
MIN_SCOPE_CASES = 200          # only precompute per-crime-type scopes this busy

# ---- alerts -----------------------------------------------------------------
ALERT_Z_FLOOR = 1.5            # precompute floor; UI slider min must match

# ---- Module 2/3 tables copied verbatim --------------------------------------
# ⚠️ EDIT: replace the Module 3 names with what Phase 0 printed.
COPY_TABLES = [
    "EntityProfile", "CoOffenseEdge", "EntityCommunity", "CommunityProfile",
    "RiskScore", "RiskBacktest", "RiskFeatureImportance",
    "AnomalyScore", "CellAnomaly", "SocioEconCorr", "SocioEconRegression",
]

METRIC_FILES = ["module1_metrics.json", "module2_metrics.json", "module3_metrics.json"]


# ============================================================ helpers
def log(msg): print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def build_cases() -> pd.DataFrame:
    """Flat presentation table. CaseID is positional and becomes the join key
    for everything downstream — assigned once, here, deterministically."""
    c = db.load_cases().reset_index(drop=True)
    c.insert(0, "CaseID", range(len(c)))
    c["date"] = pd.to_datetime(c["date"])
    # Time-of-day patterns must come from the INCIDENT time, not the registration
    # date (which is midnight → hour always 0). load_cases() already computes an
    # incident-based 'hour'; derive dow from IncidentFromDate for the same reason.
    inc = pd.to_datetime(c["IncidentFromDate"], errors="coerce")
    hour = c["hour"] if "hour" in c.columns else inc.dt.hour
    hour = pd.to_numeric(hour, errors="coerce").fillna(inc.dt.hour) \
             .fillna(c["date"].dt.hour).fillna(0).astype(int)
    dow = inc.dt.dayofweek.fillna(c["date"].dt.dayofweek).fillna(0).astype(int)
    out = pd.DataFrame({
        "CaseID":       c["CaseID"],
        "DistrictID":   c["DistrictID"],
        "DistrictName": c["DistrictName"],
        "Station":      c["Station"],
        "CrimeHead":    c["CrimeHead"],
        "CrimeType":    c["CrimeType"],
        "date":         c["date"].dt.strftime("%Y-%m-%d"),
        "ym":           c["ym"].astype(str),
        "hour":         hour,
        "dow":          dow,                             # 0=Mon, from incident time
        "latitude":     c["latitude"].round(5),
        "longitude":    c["longitude"].round(5),
    })
    return c, out          # c keeps native dtypes for m1.*; out is what we store


def build_hotspots(cases: pd.DataFrame):
    """Returns (HotspotParam, HotspotSummary, HotspotAssign)."""
    scope_counts = cases["CrimeType"].value_counts()
    scopes = ["All"] + [t for t, n in scope_counts.items() if n >= MIN_SCOPE_CASES]
    log(f"hotspot scopes: {scopes}")

    params, summaries, assigns, pid = 0, [], [], 0 # WAIT, there was a bug in user code `params, summaries, assigns, pid = [], [], [], 0`! I will fix.
    params = []
    summaries = []
    assigns = []
    pid = 0
    for scope in scopes:
        sub = cases if scope == "All" else cases[cases["CrimeType"] == scope]
        for eps in EPS_GRID:
            for ms in MINS_GRID:
                if len(sub) < ms:
                    continue
                clustered = m1.find_hotspots(sub, eps_km=eps, min_samples=ms)
                hit = clustered[clustered["cluster"] >= 0]
                if hit.empty:
                    continue
                pid += 1
                params.append(dict(param_id=pid, scope=scope, eps_km=eps,
                                   min_samples=ms, n_hotspots=int(hit["cluster"].nunique()),
                                   n_cases=int(len(hit))))
                s = m1.hotspot_summary(clustered).copy()
                s.insert(0, "param_id", pid)
                summaries.append(s)
                a = hit[["CaseID", "cluster"]].copy()
                a.insert(0, "param_id", pid)
                assigns.append(a)
        log(f"  scope '{scope}' done → {pid} param sets so far")

    return (pd.DataFrame(params),
            pd.concat(summaries, ignore_index=True) if summaries else pd.DataFrame(),
            pd.concat(assigns, ignore_index=True) if assigns else pd.DataFrame())


def build_alerts(cases: pd.DataFrame) -> pd.DataFrame:
    """z is a per-(district × crime-type × month) statistic, so precomputing on the
    full dataset and filtering rows afterwards is mathematically identical to
    filtering the input first. No fidelity is lost."""
    a = m1.spike_alerts(cases, z_thresh=ALERT_Z_FLOOR).copy()
    a["ym"] = a["ym"].astype(str)
    return a


def copy_tables(src: sqlite3.Connection, dst: sqlite3.Connection):
    have = {r[0] for r in src.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    for t in COPY_TABLES:
        if t not in have:
            log(f"  ⚠ skipping '{t}' — not in crime.db (edit COPY_TABLES)")
            continue
        df = pd.read_sql(f'SELECT * FROM "{t}"', src)
        df.to_sql(t, dst, if_exists="replace", index=False)
        log(f"  ✓ copied {t} ({len(df)} rows)")


def build_meta(dst: sqlite3.Connection, cases_out: pd.DataFrame):
    meta = {
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "n_cases": len(cases_out),
        "date_min": cases_out["date"].min(),
        "date_max": cases_out["date"].max(),
        "alert_z_floor": ALERT_Z_FLOOR,
        "eps_grid": EPS_GRID,
        "mins_grid": MINS_GRID,
    }
    rep = ROOT / "reports"
    for f in METRIC_FILES:
        p = rep / f
        if p.exists():
            meta[f.replace(".json", "")] = json.loads(p.read_text())
            log(f"  ✓ folded in {f}")
        else:
            log(f"  ⚠ {f} missing — Validation tab will show a gap")
    dst.execute("CREATE TABLE IF NOT EXISTS Meta (key TEXT PRIMARY KEY, value TEXT)")
    dst.execute("DELETE FROM Meta")
    dst.executemany("INSERT INTO Meta VALUES (?,?)",
                    [(k, json.dumps(v)) for k, v in meta.items()])


def build_geojson():
    gj, prop = db.load_geojson()
    if not gj:
        log("  ⚠ no geojson — map falls back to point density")
        return
    GEOJSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    # keep the property key discoverable by the frontend
    GEOJSON_OUT.write_text(json.dumps({"featureidkey": prop, **gj}))
    mb = GEOJSON_OUT.stat().st_size / 1e6
    log(f"  ✓ geojson written ({mb:.1f} MB)"
        + ("  ⚠ >5 MB — consider simplifying with mapshaper.org" if mb > 5 else ""))


# ============================================================ main
def main():
    OUT_DB.parent.mkdir(parents=True, exist_ok=True)
    if OUT_DB.exists():
        OUT_DB.unlink()

    log("loading cases …")
    cases_native, cases_out = build_cases()
    log(f"  {len(cases_out)} cases, {cases_out.date.min()} → {cases_out.date.max()}")

    log("running hotspot grid (this is the slow part) …")
    hp, hs, ha = build_hotspots(cases_native)
    log(f"  {len(hp)} param sets · {len(hs)} hotspot rows · {len(ha)} assignments")

    log("computing spike alerts …")
    al = build_alerts(cases_native)
    log(f"  {len(al)} alert cells at z ≥ {ALERT_Z_FLOOR}")

    log("writing spear.db …")
    dst = sqlite3.connect(OUT_DB)
    cases_out.to_sql("Case", dst, index=False)
    db.load_district_profile().to_sql("DistrictProfile", dst, index=False)
    hp.to_sql("HotspotParam", dst, index=False)
    hs.to_sql("HotspotSummary", dst, index=False)
    ha.to_sql("HotspotAssign", dst, index=False)
    al.to_sql("Alert", dst, index=False)

    log("copying Module 2/3 tables …")
    src = sqlite3.connect(SRC_DB)
    copy_tables(src, dst)
    src.close()

    log("folding in validation metrics …")
    build_meta(dst, cases_out)

    log("indexing …")
    for stmt in [
        'CREATE UNIQUE INDEX ix_case_id ON "Case"(CaseID)',
        'CREATE INDEX ix_case_ym    ON "Case"(ym)',
        'CREATE INDEX ix_case_type  ON "Case"(CrimeType)',
        'CREATE INDEX ix_case_head  ON "Case"(CrimeHead)',
        'CREATE INDEX ix_case_dist  ON "Case"(DistrictName)',
        'CREATE INDEX ix_case_date  ON "Case"(date)',
        'CREATE INDEX ix_assign_pid ON HotspotAssign(param_id)',
        'CREATE INDEX ix_hs_pid     ON HotspotSummary(param_id)',
        'CREATE INDEX ix_param_look ON HotspotParam(scope, eps_km, min_samples)',
        'CREATE INDEX ix_alert_z    ON Alert(z)',
        'CREATE INDEX ix_edge_a     ON CoOffenseEdge(EntityA)',
        'CREATE INDEX ix_ec_comm    ON EntityCommunity(CommunityID)',
    ]:
        try:
            dst.execute(stmt)
        except sqlite3.OperationalError as e:
            log(f"  ⚠ index skipped: {e}")
    dst.commit()
    dst.execute("VACUUM")
    dst.close()

    log("writing geojson …")
    build_geojson()

    mb = OUT_DB.stat().st_size / 1e6
    log(f"\n✅ spear.db built: {mb:.1f} MB")
    if mb > 80:
        log("⚠ over 80 MB — trim EPS_GRID/MINS_GRID or raise MIN_SCOPE_CASES and rerun")

if __name__ == "__main__":
    main()
