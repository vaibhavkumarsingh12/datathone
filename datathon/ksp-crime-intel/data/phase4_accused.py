# phase4_accused.py — public Accused (messy) + SECRET PersonCaseTruth (clean answer key).
import random
import pandas as pd
import config as C
import names as N

random.seed(C.SEED + 3)

def build_accused():
    people = pd.read_csv(C.TRUTH / "PersonMaster.csv").set_index("PersonID")
    plan   = pd.read_csv(C.TRUTH / "OffenderPlan.csv")

    accused, truth = [], []
    amid = 1
    # keep accused of the same case grouped, labelled A1, A2, ...
    for cid, grp in plan.groupby("CaseMasterID"):
        for i, (_, row) in enumerate(grp.iterrows(), start=1):
            pid = int(row["PersonID"])
            p = people.loc[pid]
            messy_name = N.smudge(p["FirstName"], p["Surname"])   # <-- corruption happens here
            age_noise = int(p["Age"]) + random.choice([-1, 0, 0, 1])
            accused.append({
                "AccusedMasterID": amid, "CaseMasterID": int(cid),
                "AccusedName": messy_name,           # smudged
                "AgeYear": age_noise,                # noisy
                "GenderID": p["Gender"],
                "FatherName": N.smudge(p["FatherName"], p["Surname"]).split(" ")[0]
                              if random.random() > 0.15 else None,   # occasionally missing
                "PersonID": f"A{i}",                 # per-case sort label ONLY (not identity!)
            })
            # the ANSWER KEY: this AccusedMasterID is really this true PersonID
            truth.append({"AccusedMasterID": amid, "CaseMasterID": int(cid),
                          "TruePersonID": pid, "TrueRingID": p["RingID"]})
            amid += 1

    # ArrestSurrender for ~50% of accused
    arr = []
    for a in accused:
        if random.random() < 0.5:
            arr.append({"ArrestSurrenderID": len(arr) + 1,
                        "CaseMasterID": a["CaseMasterID"],
                        "AccusedMasterID": a["AccusedMasterID"],
                        "ArrestSurrenderTypeID": random.choice([1, 2]),
                        "ArrestSurrenderDistrictId": random.randint(1, 31),
                        "IOID": random.randint(1, 50)})

    pd.DataFrame(accused).to_csv(C.OUT / "Accused.csv", index=False)          # PUBLIC (messy)
    pd.DataFrame(arr).to_csv(C.OUT / "ArrestSurrender.csv", index=False)      # PUBLIC
    pd.DataFrame(truth).to_csv(C.TRUTH / "PersonCaseTruth.csv", index=False)  # SECRET key
    print(f"Phase 4 done: {len(accused)} accused rows (smudged), "
          f"answer key saved with {len(truth)} true links.")

if __name__ == "__main__":
    build_accused()
