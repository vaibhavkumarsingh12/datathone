# phase6_validate.py — THE FINAL EXAM for your Week 1 data.
# Run:  python phase6_validate.py
# It re-checks every problem found in validation, plus the original sanity checks,
# and prints PASS / FAIL per test with the measured numbers.
# If everything passes, the data layer is DONE and you can start Module 1.
#
# Requires: pip install rapidfuzz  (you already have pandas/numpy)

import json
import random
from collections import defaultdict

import pandas as pd
from rapidfuzz import fuzz

import config as C

random.seed(C.SEED)

PASS, FAIL, WARN = "✅ PASS", "❌ FAIL", "⚠️  WARN"
results = []

def report(name, ok, detail, warn=False):
    status = WARN if warn else (PASS if ok else FAIL)
    results.append((status, name, detail))
    print(f"{status}  {name}\n        → {detail}")

# ---------------------------------------------------------------- load
print("Loading data...\n" + "=" * 60)
cases    = pd.read_csv(C.OUT / "CaseMaster.csv")
accused  = pd.read_csv(C.OUT / "Accused.csv")
units    = pd.read_csv(C.OUT / "Unit.csv")
victims  = pd.read_csv(C.OUT / "Victim.csv")
actsec   = pd.read_csv(C.OUT / "ActSectionAssociation.csv")
persons  = pd.read_csv(C.TRUTH / "PersonMaster.csv")
truth    = pd.read_csv(C.TRUTH / "PersonCaseTruth.csv")
rings    = pd.read_csv(C.TRUTH / "PlantedPatterns_rings.csv")
planted  = pd.read_csv(C.TRUTH / "PlantedPatterns_cases.csv")

# ---------------------------------------------------------------- T1 FK integrity
orphans = (
    (~accused.CaseMasterID.isin(cases.CaseMasterID)).sum()
    + (~victims.CaseMasterID.isin(cases.CaseMasterID)).sum()
    + (~actsec.CaseMasterID.isin(cases.CaseMasterID)).sum()
    + (~cases.PoliceStationID.isin(units.UnitID)).sum()
)
no_truth = (~accused.AccusedMasterID.isin(truth.AccusedMasterID)).sum()
report("T1 · FK integrity", orphans == 0 and no_truth == 0,
       f"orphan FKs: {orphans}, accused rows missing from answer key: {no_truth} (need 0 & 0)")

# ---------------------------------------------------------------- T2 no identity leak
leak_cols = [c for c in accused.columns
             if c.lower() in ("truepersonid", "personid_true", "ring", "ringid", "offendertype")]
a1_style = accused["PersonID"].astype(str).str.match(r"^A\d+$").all() if "PersonID" in accused else True
report("T2 · No identity leak in public Accused.csv", len(leak_cols) == 0 and a1_style,
       f"suspicious columns: {leak_cols or 'none'}; PersonID is A1/A2-style labels only: {a1_style}")

# ---------------------------------------------------------------- T3 name collisions (Patch 1)
persons["full"] = (persons.FirstName.str.strip() + " " + persons.Surname.str.strip()).str.lower()
distinct = persons.full.nunique()
worst = persons.full.value_counts()
collision_ratio = distinct / len(persons)
report("T3 · Name pool (collision fix)", distinct >= 2500,
       f"{distinct} distinct canonical names for {len(persons)} people "
       f"(worst collision: '{worst.index[0]}' ×{worst.iloc[0]}; need ≥2500 distinct)")

# ---------------------------------------------------------------- T4 FatherName present (Patch 1/4)
has_father_master = "FatherName" in persons.columns
has_father_acc = "FatherName" in accused.columns
fill = accused.FatherName.notna().mean() if has_father_acc else 0
report("T4 · FatherName field (second resolution key)", has_father_master and has_father_acc and fill > 0.7,
       f"in PersonMaster: {has_father_master}, in Accused: {has_father_acc}, "
       f"filled: {fill:.0%} (need >70%)")

# ---------------------------------------------------------------- T5 offender types (Patch 2)
if "OffenderType" in persons.columns:
    tc = persons.OffenderType.value_counts().to_dict()
    merged = accused.merge(truth, on=["AccusedMasterID", "CaseMasterID"])
    non_ring = merged[merged.TrueRingID.isna()]
    per_person = non_ring.groupby("TruePersonID").size()
    repeat_ids = set(persons[persons.OffenderType == "repeat"].PersonID)
    unexpected_repeats = per_person[(per_person >= 2) & (~per_person.index.isin(repeat_ids))]
    ok = len(unexpected_repeats) <= 0.02 * len(per_person)   # ≤2% tolerance for random ring-solo overlap
    report("T5 · Offender population structure", ok,
           f"types: {tc} | non-ring people with 2+ cases NOT in repeat pool: "
           f"{len(unexpected_repeats)} (need ≈0; ≤{int(0.02*len(per_person))} tolerated)")
else:
    report("T5 · Offender population structure", False,
           "PersonMaster has no OffenderType column — Patch 2 not applied")

# ---------------------------------------------------------------- T6 ring realism (Patch 3)
cd = cases.merge(units[["UnitID", "DistrictID"]],
                 left_on="PoliceStationID", right_on="UnitID")[["CaseMasterID", "DistrictID"]]
all_ok, lines = True, []
for _, r in rings.iterrows():
    members = set(json.loads(r["members"]))
    turf = set(json.loads(r["turf"]))
    t = truth[truth.TruePersonID.isin(members)]
    per_case = t.groupby("CaseMasterID").TruePersonID.nunique()
    co_cases = int((per_case >= 2).sum())
    cpm = t.groupby("TruePersonID").size()
    ring_case_ids = t.CaseMasterID.unique()
    in_turf = cd[cd.CaseMasterID.isin(ring_case_ids)].DistrictID.isin(turf).mean()
    ok = (co_cases >= 15) and (cpm.max() <= 30) and (in_turf >= 0.6)
    all_ok &= ok
    lines.append(f"Ring {r['RingID']}: co-cases {co_cases} (≥15), "
                 f"max cases/member {cpm.max()} (≤30), in-turf {in_turf:.0%} (≥60%)")
report("T6 · Ring realism (turf + workload)", all_ok, " | ".join(lines))

# ---------------------------------------------------------------- T7 ENTITY RESOLUTION F1 (the big one)
print("\nRunning entity-resolution simulation (30-60s)...")
acc = accused.merge(truth[["AccusedMasterID", "TruePersonID"]], on="AccusedMasterID")
acc["name"] = acc.AccusedName.astype(str).str.replace(".", "", regex=False).str.lower().str.strip()
acc["father"] = (acc.FatherName.astype(str).str.replace(".", "", regex=False).str.lower().str.strip()
                 if has_father_acc else "")

parent = {}
def find(x):
    while parent.setdefault(x, x) != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x
def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb:
        parent[ra] = rb

rows = acc[["AccusedMasterID", "name", "GenderID", "AgeYear", "father"]].values.tolist()
blocks = defaultdict(list)
for r in rows:
    blocks[(r[2], int(r[3]) // 3)].append(r)

NAME_T, FATHER_T = 88, 80
for (g, band), items in blocks.items():
    pool = items + blocks.get((g, band + 1), [])
    for i in range(len(items)):
        a = items[i]
        for b in pool:
            if b[0] <= a[0] or abs(a[3] - b[3]) > 2:
                continue
            if fuzz.token_sort_ratio(a[1], b[1]) >= NAME_T:
                # father agreement required only when BOTH sides have one
                if a[4] and b[4] and a[4] != "nan" and b[4] != "nan":
                    if fuzz.ratio(a[4], b[4]) >= FATHER_T:
                        union(a[0], b[0])
                else:
                    union(a[0], b[0])

acc["cluster"] = acc.AccusedMasterID.map(find)
def pairs(s):
    return sum(n * (n - 1) // 2 for n in s.value_counts())
tp = sum(n * (n - 1) // 2 for n in acc.groupby(["cluster", "TruePersonID"]).size())
prec = tp / pairs(acc.cluster) if pairs(acc.cluster) else 0
rec = tp / pairs(acc.TruePersonID) if pairs(acc.TruePersonID) else 0
f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
report("T7 · Entity resolution recoverability", f1 >= 0.80,
       f"precision {prec:.3f} · recall {rec:.3f} · F1 {f1:.3f} (need F1 ≥ 0.80; "
       f"0.85+ is your demo-slide number)")

# ---------------------------------------------------------------- T8 ring RECOVERY end-to-end
# After resolution: do resolved clusters actually reconnect the gangs?
res_person = acc.groupby("cluster").TruePersonID.agg(lambda s: s.mode().iloc[0])
acc["resolved_pid"] = acc.cluster.map(res_person)
recovered = 0
for _, r in rings.iterrows():
    members = set(json.loads(r["members"]))
    hits = acc[acc.TruePersonID.isin(members)]
    # a ring counts as recoverable if resolution kept ≥60% of its rows correctly grouped
    correct = (hits.resolved_pid == hits.TruePersonID).mean()
    if correct >= 0.6:
        recovered += 1
report("T8 · Gang recovery after resolution", recovered == len(rings),
       f"{recovered}/{len(rings)} rings survive resolution well enough for graph detection (need all)")

# ---------------------------------------------------------------- T9 hotspots
hot_ok, hl = True, []
for (d, sh), g in planted[planted.pattern == "hotspot"].groupby(["district", "subhead"]):
    sub = cases[cases.CaseMasterID.isin(g.CaseMasterID)]
    std = (sub.latitude.std() + sub.longitude.std()) / 2
    ok = std < 0.05 and len(g) >= 80
    hot_ok &= ok
    hl.append(f"d{d}/s{sh}: {len(g)} cases, std {std:.4f}")
report("T9 · Planted hotspots intact", hot_ok, " | ".join(hl) + " (need std<0.05, n≥80)")

# ---------------------------------------------------------------- T10 spikes
cases["ym"] = pd.to_datetime(cases.CrimeRegisteredDate).dt.to_period("M").astype(str)
sp_ok, sl = True, []
for (d, sh), g in planted[planted.pattern == "spike"].groupby(["district", "subhead"]):
    monthly = cases[cases.CrimeMinorHeadID == sh].groupby("ym").size()
    ratio = monthly.max() / max(monthly.median(), 1)
    ok = ratio >= 3
    sp_ok &= ok
    sl.append(f"d{d}/s{sh}: peak {monthly.idxmax()} = {monthly.max()} vs median {int(monthly.median())} (×{ratio:.1f})")
report("T10 · Planted spikes intact", sp_ok, " | ".join(sl) + " (need peak ≥3× median)")

# ---------------------------------------------------------------- scorecard
print("\n" + "=" * 60)
fails = [r for r in results if r[0] == FAIL]
print(f"SCORECARD: {len(results) - len(fails)}/{len(results)} passed")
for status, name, _ in results:
    print(f"  {status}  {name}")
if fails:
    print("\nFix the FAILs above, re-run `python run_all.py`, then run this again.")
else:
    print("\n🎉 ALL GREEN — the data layer is DONE. Save this output; T7's F1 number")
    print("   goes straight onto your demo slide. Next stop: Module 1 (geo-hotspots).")
