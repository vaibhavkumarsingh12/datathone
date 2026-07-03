# phase3_cases.py — the crimes. Writes public CaseMaster + victims/complainants/sections,
# and a SECRET offender plan (who really did each case).
import random, json
from datetime import datetime, timedelta
import pandas as pd
import config as C
import reference_data as R
import names as N

random.seed(C.SEED + 2)

# ---------- helpers ----------
DIST = {d[0]: d for d in R.DISTRICTS}          # district_id -> full tuple
SUB  = {s[0]: s for s in R.CRIME_SUBHEADS}     # subhead_id  -> full tuple
D0   = datetime.strptime(C.DATE_START, "%Y-%m-%d")
D1   = datetime.strptime(C.DATE_END,   "%Y-%m-%d")
SPAN = (D1 - D0).days

def sample_district():
    ids  = [d[0] for d in R.DISTRICTS]
    wts  = [d[4] for d in R.DISTRICTS]          # weight by population
    return random.choices(ids, weights=wts)[0]

def sample_subhead(district_id):
    lit = DIST[district_id][5]                  # literacy
    ids, wts = [], []
    for sid, hid, nm, base, hot, tb in R.CRIME_SUBHEADS:
        w = base
        if hid == 2:                            # property crime up where literacy is lower
            w *= (1.6 - lit)                    # low literacy -> bigger multiplier
        ids.append(sid); wts.append(max(w, 0.1))
    return random.choices(ids, weights=wts)[0]

def sample_datetime(time_bias):
    day = D0 + timedelta(days=random.randint(0, SPAN))
    if time_bias == "weekend_evening":
        # push toward Fri/Sat/Sun, 18:00-23:00
        shift = (5 - day.weekday()) % 7
        if random.random() < 0.6: day += timedelta(days=shift)
        hour = random.randint(18, 23)
    elif time_bias == "night":
        hour = random.choice([0,1,2,3,22,23])
    elif time_bias == "daytime":
        hour = random.randint(9, 17)
    else:
        hour = random.randint(0, 23)
    return day.replace(hour=hour, minute=random.randint(0, 59))

def jitter_coords(lat, lon, spread=0.12):
    return round(lat + random.uniform(-spread, spread), 5), \
           round(lon + random.uniform(-spread, spread), 5)



# ---------- planted hotspots & spikes ----------
# Hotspot: pick a (district, subhead) and force tight clustering + weekend-evening time.
HOTSPOTS = [
    {"district": 1,  "subhead": 203, "n": 220, "spread": 0.02},  # Chain Snatching, Bengaluru
    {"district": 3,  "subhead": 204, "n": 160, "spread": 0.02},  # Vehicle Theft, Mysuru
    {"district": 8,  "subhead": 205, "n": 120, "spread": 0.02},  # Robbery, Ballari
]
# Spike: pick a (district, subhead, year-month) and inject a burst.
SPIKES = [
    {"district": 5,  "subhead": 601, "ym": "2024-11", "n": 140},  # Drug spike, Kalaburagi
    {"district": 14, "subhead": 202, "ym": "2025-06", "n": 130},  # Theft spike, Raichur
]

def build_cases():
    # --- load people ONCE at top of build_cases() ---
    people_df = pd.read_csv(C.TRUTH / "PersonMaster.csv")
    oneoff_ids = people_df[people_df.OffenderType == "oneoff"].PersonID.sample(
        frac=1.0, random_state=C.SEED).tolist()          # shuffled queue, popped once each
    repeat_df  = people_df[people_df.OffenderType == "repeat"]
    repeat_ids = repeat_df.PersonID.tolist()
    repeat_home = dict(zip(repeat_df.PersonID, repeat_df.HomeDistrictID))

    def choose_offenders(rings):
        """Returns (person_ids, profile, forced_district_or_None)."""
        r = random.random()
        if r < C.RING_CASE_SHARE and rings:
            ring = random.choice(rings)
            members = json.loads(ring["members"])
            turf = json.loads(ring["turf"])
            k = min(len(members), random.randint(2, 4))
            # 80% of ring cases happen inside their turf
            district = random.choice(turf) if random.random() < 0.8 else None
            return random.sample(members, k), "ring", district
        elif r < C.RING_CASE_SHARE + C.REPEAT_SHARE:
            pid = random.choice(repeat_ids)
            # 60% of a repeater's crimes happen in their home district
            district = repeat_home[pid] if random.random() < 0.6 else None
            return [pid], "repeat", district
        else:
            pid = oneoff_ids.pop() if oneoff_ids else random.choice(repeat_ids)
            return [pid], "oneoff", None

    rings = pd.read_csv(C.TRUTH / "PlantedPatterns_rings.csv").to_dict("records")
    stations = pd.read_csv(C.OUT / "Unit.csv")
    st_by_dist = stations.groupby("DistrictID")["UnitID"].apply(list).to_dict()

    cases, offender_plan, victims, complainants, actsec, planted = [], [], [], [], [], []
    serial = {}                                 # (unit, category, year) -> running number
    cid = 1

    def make_case(district_id, subhead_id=None, forced_dt=None, forced_coords=None, tag=None, offenders=None, profile=None):
        nonlocal cid
        if subhead_id is None:
            subhead_id = sample_subhead(district_id)
        _, hid, nm, base, hot, tb = SUB[subhead_id]
        dt = forced_dt or sample_datetime(tb)
        lat0, lon0 = DIST[district_id][2], DIST[district_id][3]
        lat, lon = forced_coords or jitter_coords(lat0, lon0)
        cat = random.choices([1,2,3,4], weights=[0.85,0.06,0.05,0.04])[0]  # mostly FIR
        code = {1:1,2:3,3:4,4:8}[cat]
        unit = random.choice(st_by_dist[district_id])
        yr = dt.year
        key = (unit, cat, yr)
        serial[key] = serial.get(key, 0) + 1
        crime_no = f"{code}{district_id:04d}{unit:04d}{yr}{serial[key]:05d}"
        case_no  = f"{yr}{serial[key]:05d}"
        gravity = 1 if subhead_id in (101,102,105,205,206,602) else 2
        status  = random.choices([1,2,3,4,5], weights=[0.35,0.30,0.10,0.20,0.05])[0]

        cases.append({
            "CaseMasterID": cid, "CrimeNo": crime_no, "CaseNo": case_no,
            "CrimeRegisteredDate": dt.date().isoformat(),
            "PolicePersonID": random.randint(1, 50), "PoliceStationID": unit,
            "CaseCategoryID": cat, "GravityOffenceID": gravity,
            "CrimeMajorHeadID": hid, "CrimeMinorHeadID": subhead_id,
            "CaseStatusID": status, "CourtID": None,
            "IncidentFromDate": dt.isoformat(),
            "IncidentToDate": dt.isoformat(),
            "InfoReceivedPSDate": (dt + timedelta(hours=random.randint(1, 48))).isoformat(),
            "latitude": lat, "longitude": lon,
            "BriefFacts": f"{nm} reported in district {district_id}.",
        })

        # sections
        for sec in R.SUBHEAD_SECTIONS.get(subhead_id, []):
            actsec.append({"CaseMasterID": cid, "ActID": "IPC", "SectionID": sec})

        # victims (0-2)
        for _ in range(random.randint(0, 2)):
            g = random.choice(["M","F"])
            vf, vs, _ = N.make_canonical(g)
            victims.append({"CaseMasterID": cid, "VictimName": f"{vf} {vs}",
                            "AgeYear": random.randint(16, 70), "GenderID": g})
        # one complainant (religion/caste intentionally left blank)
        cf, cs, _ = N.make_canonical(random.choice(["M","F"]))
        complainants.append({"CaseMasterID": cid, "ComplainantName": f"{cf} {cs}",
                             "AgeYear": random.randint(20, 65),
                             "OccupationID": random.randint(1, 10),
                             "ReligionID": None, "CasteID": None})

        # who did it (SECRET plan)
        for pid in offenders:
            offender_plan.append({"CaseMasterID": cid, "PersonID": pid, "profile": profile})

        if tag:
            planted.append({"CaseMasterID": cid, "pattern": tag,
                            "district": district_id, "subhead": subhead_id})
        cid += 1

    # 1) base cases — offender first, district second
    for _ in range(C.N_FIRS):
        offs, prof, forced_d = choose_offenders(rings)
        district = forced_d or sample_district()
        make_case(district, offenders=offs, profile=prof)

    # 2) hotspot injections — petty crime, one-off offenders
    for h in HOTSPOTS:
        lat0, lon0 = DIST[h["district"]][2], DIST[h["district"]][3]
        for _ in range(h["n"]):
            coords = jitter_coords(lat0, lon0, h["spread"])
            offs = [oneoff_ids.pop()] if oneoff_ids else [random.choice(repeat_ids)]
            make_case(h["district"], h["subhead"], forced_coords=coords,
                      tag="hotspot", offenders=offs, profile="oneoff")

    # 3) spikes — same pattern, forced dates
    for s in SPIKES:
        y, m = map(int, s["ym"].split("-"))
        for _ in range(s["n"]):
            day = datetime(y, m, random.randint(1, 28), random.randint(0, 23), 0)
            offs = [oneoff_ids.pop()] if oneoff_ids else [random.choice(repeat_ids)]
            make_case(s["district"], s["subhead"], forced_dt=day,
                      tag="spike", offenders=offs, profile="oneoff")

    # write PUBLIC tables
    pd.DataFrame(cases).to_csv(C.OUT / "CaseMaster.csv", index=False)
    pd.DataFrame(victims).to_csv(C.OUT / "Victim.csv", index=False)
    pd.DataFrame(complainants).to_csv(C.OUT / "ComplainantDetails.csv", index=False)
    pd.DataFrame(actsec).to_csv(C.OUT / "ActSectionAssociation.csv", index=False)
    # write SECRET tables
    pd.DataFrame(offender_plan).to_csv(C.TRUTH / "OffenderPlan.csv", index=False)
    pd.DataFrame(planted).to_csv(C.TRUTH / "PlantedPatterns_cases.csv", index=False)

    print(f"Phase 3 done: {len(cases)} cases "
          f"({C.N_FIRS} base + {sum(h['n'] for h in HOTSPOTS)} hotspot "
          f"+ {sum(s['n'] for s in SPIKES)} spike).")

if __name__ == "__main__":
    build_cases()
