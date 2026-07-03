# phase5_sanity.py — verify the planted structure exists. Prints a report + 2 charts.
import json
import pandas as pd
import matplotlib
matplotlib.use("Agg")            # save charts to file, no popup needed
import matplotlib.pyplot as plt
import config as C

def check():
    cases   = pd.read_csv(C.OUT / "CaseMaster.csv")
    accused = pd.read_csv(C.OUT / "Accused.csv")
    truth   = pd.read_csv(C.TRUTH / "PersonCaseTruth.csv")
    rings   = pd.read_csv(C.TRUTH / "PlantedPatterns_rings.csv").to_dict("records")
    planted = pd.read_csv(C.TRUTH / "PlantedPatterns_cases.csv")

    print("=" * 55)
    print("SANITY REPORT")
    print("=" * 55)
    print(f"Cases: {len(cases):,} | Accused rows: {len(accused):,} | "
          f"Districts: {cases['CrimeMinorHeadID'].nunique()} sub-heads used")

    # 1) GANGS: do ring members actually co-appear on shared cases?
    print("\n[1] GANGS (rings) — co-offending check")
    for r in rings:
        members = set(json.loads(r["members"]))
        # cases where >=2 of this ring's members are the true offenders
        t = truth[truth["TruePersonID"].isin(members)]
        shared = t.groupby("CaseMasterID")["TruePersonID"].nunique()
        co_cases = (shared >= 2).sum()
        print(f"  Ring {r['RingID']}: {len(members)} members, "
              f"{co_cases} cases with >=2 members together  "
              f"{'OK' if co_cases > 0 else 'MISSING!'}")

    # 2) ENTITY RESOLUTION is needed: same true person, many name spellings
    print("\n[2] SMUDGING — one true person shows up as many names")
    merged = accused.merge(truth, on=["AccusedMasterID", "CaseMasterID"])
    sample = merged.groupby("TruePersonID")["AccusedName"].nunique().sort_values(ascending=False)
    top = sample.index[0]
    names_seen = merged[merged["TruePersonID"] == top]["AccusedName"].unique()[:6]
    print(f"  Person {top} appears under {sample.iloc[0]} different name spellings, e.g.:")
    print("   ", list(names_seen))

    # 3) HOTSPOTS: injected clusters have much tighter coordinates than average
    print("\n[3] HOTSPOTS — spatial tightness check")
    hot = planted[planted["pattern"] == "hotspot"]
    for (d, sh), g in hot.groupby(["district", "subhead"]):
        ids = g["CaseMasterID"]
        sub = cases[cases["CaseMasterID"].isin(ids)]
        std = (sub["latitude"].std() + sub["longitude"].std()) / 2
        print(f"  District {d}, sub-head {sh}: {len(ids)} cases, "
              f"coord std={std:.4f} (small = tight cluster)")

    # 4) SPIKES: injected month should tower over the baseline
    print("\n[4] SPIKES — monthly burst check")
    cases["ym"] = pd.to_datetime(cases["CrimeRegisteredDate"]).dt.to_period("M").astype(str)
    for (d, sh), g in planted[planted["pattern"] == "spike"].groupby(["district", "subhead"]):
        sub = cases[(cases["CrimeMinorHeadID"] == sh)]
        monthly = sub.groupby("ym").size()
        peak = monthly.idxmax()
        print(f"  District {d}, sub-head {sh}: peak month = {peak} "
              f"({monthly.max()} cases vs median {int(monthly.median())})")

    # ---- charts ----
    fig, ax = plt.subplots(figsize=(9, 4))
    monthly_all = cases.groupby("ym").size()
    monthly_all.plot(ax=ax, title="Cases per month (spikes should stick out)")
    fig.tight_layout(); fig.savefig(C.OUT / "check_monthly.png"); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(cases["longitude"], cases["latitude"], s=1, alpha=0.2)
    hot_ids = planted[planted["pattern"] == "hotspot"]["CaseMasterID"]
    hc = cases[cases["CaseMasterID"].isin(hot_ids)]
    ax.scatter(hc["longitude"], hc["latitude"], s=3, color="red")
    ax.set_title("All cases (grey) vs planted hotspots (red)")
    fig.tight_layout(); fig.savefig(C.OUT / "check_hotspots.png"); plt.close(fig)

    print("\nCharts saved: output/check_monthly.png, output/check_hotspots.png")
    print("=" * 55)

if __name__ == "__main__":
    check()
