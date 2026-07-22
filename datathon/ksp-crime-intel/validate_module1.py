# validate_module1.py — PASS/FAIL exam for Module 1 analytics against planted truth.
# Run from repo root:  python validate_module1.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import json
import sqlite3
import pandas as pd
from src import module1_geo as m1

OUT = Path("data/output"); TRUTH = Path("data/ground_truth")
REPORTS = Path("reports"); REPORTS.mkdir(exist_ok=True)
PASS, FAIL = "✅ PASS", "❌ FAIL"
results = []
metrics = {}          # written to reports/module1_metrics.json — the dashboard quotes this
def report(name, ok, detail):
    results.append(PASS if ok else FAIL)
    print(f"{PASS if ok else FAIL}  {name}\n        → {detail}")

conn = sqlite3.connect(OUT / "crime.db")
df = pd.read_sql("""SELECT c.CaseMasterID,c.latitude,c.longitude,c.CrimeRegisteredDate,
 c.IncidentFromDate,c.CrimeMinorHeadID,d.DistrictName,d.DistrictID,
 s.CrimeHeadName AS CrimeType FROM CaseMaster c
 JOIN Unit u ON u.UnitID=c.PoliceStationID
 JOIN District d ON d.DistrictID=u.DistrictID
 JOIN CrimeSubHead s ON s.CrimeSubHeadID=c.CrimeMinorHeadID""",
 conn, parse_dates=["IncidentFromDate"])
df["ym"] = pd.to_datetime(df.CrimeRegisteredDate).dt.to_period("M").astype(str)
planted = pd.read_csv(TRUTH / "PlantedPatterns_cases.csv")

# ---- V1: DBSCAN recovers all 3 planted hotspots ----
clustered = m1.find_hotspots(df, eps_km=2.0, min_samples=25)
recovered, details = 0, []
for (d, sh), g in planted[planted.pattern == "hotspot"].groupby(["district", "subhead"]):
    lbl = clustered[clustered.CaseMasterID.isin(g.CaseMasterID)]["cluster"]
    in_cluster = lbl[lbl >= 0]
    # recovered = ≥70% of planted cases land in ONE cluster
    share = (in_cluster.value_counts().iloc[0] / len(g)) if len(in_cluster) else 0
    ok = share >= 0.7
    recovered += ok
    details.append(f"d{d}/s{sh}: {share:.0%} in one cluster")
report("V1 · DBSCAN recovers planted hotspots", recovered == 3,
       f"{recovered}/3 recovered | " + " | ".join(details))

# ---- V2: hotspot precision (not drowning in fakes) ----
summ = m1.hotspot_summary(clustered)
report("V2 · Hotspot precision", 0 < len(summ) <= 8,
       f"{len(summ)} clusters found at default settings (want ≤8; planted 3 + a few "
       f"organic density clusters is fine — 40 means eps is too loose)")

# ---- V3: alerts fire on both planted spikes ----
alerts = m1.spike_alerts(df, z_thresh=2.5)
hits = 0
spike_truth = [("Kalaburagi", "2024-11"), ("Raichur", "2025-06")]
akey = set(zip(alerts.DistrictName, alerts.ym))
for dist, ym in spike_truth:
    if (dist, ym) in akey:
        hits += 1
report("V3 · Alerts fire on planted spikes", hits == 2,
       f"{hits}/2 planted spikes flagged at z≥2")

# ---- V4: alerts aren't spammy ----
n_al = len(alerts)
report("V4 · Alert precision", n_al <= 25,
       f"{n_al} total alerts at z≥2.5 across 36 months × 31 districts × 22 types "
       f"(≤25 keeps the tab credible; hundreds = threshold too low)")

# ---- V5: planted time bias visible ----
cs = df[df.CrimeType == "Chain Snatching"].copy()
cs["is_we_eve"] = (cs.IncidentFromDate.dt.dayofweek >= 4) & (cs.IncidentFromDate.dt.hour >= 18)
share = cs.is_we_eve.mean()
report("V5 · Weekend-evening bias visible (Chain Snatching)", share >= 0.35,
       f"{share:.0%} of chain snatching in Fri-Sun evenings (uniform would be ~11%)")

metrics.update({
    "hotspots": {"planted": 3, "recovered": int(recovered),
                 "clusters_found": int(len(summ))},
    "alerts": {"planted_spikes": 2, "flagged": int(hits),
               "total_alerts_at_z2.5": int(n_al)},
    "time_bias": {"crime_type": "Chain Snatching",
                  "weekend_evening_share": round(float(share), 4),
                  "uniform_baseline": 0.11},
    "scorecard": f"{results.count(PASS)}/{len(results)}",
})
(REPORTS / "module1_metrics.json").write_text(
    json.dumps(metrics, indent=2), encoding="utf-8")

print("\n" + "=" * 60)
print(f"SCORECARD: {results.count(PASS)}/{len(results)} passed")
print("Metrics written → reports/module1_metrics.json")
if FAIL in results:
    print("Tune the failing knob (eps/min_samples/z) and re-run.")
else:
    print("🎉 MODULE 1 VERIFIED — screenshots + these numbers go in the deck.")
    print("   Next: Module 2 (entity resolution + gang network graph).")
