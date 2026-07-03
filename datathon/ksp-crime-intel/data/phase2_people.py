# phase2_people.py — the SECRET population + planted gangs. Writes to ground_truth/.
import random, json
import pandas as pd
import config as C
import reference_data as R
import names as N

random.seed(C.SEED + 1)

MO_TAGS = ["night_ops","vehicle","market_area","cyber","weapon","interstate","narcotics"]

def build_people():
    people = []
    for pid in range(1, C.N_PERSONS + 1):
        gender = random.choices(["M","F"], weights=[0.85, 0.15])[0]
        first, surname, father = N.make_canonical(gender)
        age = random.randint(18, 55)
        home = random.randint(1, 31)
        # a random loner-style tag or two
        tags = random.sample(MO_TAGS, k=random.randint(1, 2))
        people.append({"PersonID": pid, "FirstName": first, "Surname": surname,
                       "Gender": gender, "Age": age, "HomeDistrictID": home,
                       "RingID": None, "MOTags": ",".join(tags), "OffenderType": "oneoff", "FatherName": father})

    # designate repeat solo offenders (rings will overwrite some below — that's fine)
    for p in random.sample(people, C.N_REPEATERS):
        p["OffenderType"] = "repeat"

    # --- Plant the gangs ---
    planted = []
    used = set()
    for ring_id in range(1, C.N_RINGS + 1):
        size = random.randint(*C.RING_SIZE_RANGE)
        # a ring shares 2-3 MO tags and operates across 2-3 neighbouring districts
        ring_tags = random.sample(MO_TAGS, k=random.randint(2, 3))
        turf = random.sample(range(1, 32), k=random.randint(2, 3))
        members = []
        while len(members) < size:
            cand = random.randint(0, len(people) - 1)
            if cand in used:
                continue
            used.add(cand)
            p = people[cand]
            p["RingID"] = ring_id
            p["HomeDistrictID"] = random.choice(turf)
            p["MOTags"] = ",".join(ring_tags)
            p["OffenderType"] = "ring"
            members.append(p["PersonID"])
        planted.append({"pattern_type": "ring", "RingID": ring_id,
                        "members": json.dumps(members), "turf": json.dumps(turf),
                        "tags": json.dumps(ring_tags)})

    pd.DataFrame(people).to_csv(C.TRUTH / "PersonMaster.csv", index=False)   # SECRET
    pd.DataFrame(planted).to_csv(C.TRUTH / "PlantedPatterns_rings.csv", index=False)
    print(f"Phase 2 done: {len(people)} people, {C.N_RINGS} gangs planted (secret).")

if __name__ == "__main__":
    build_people()
