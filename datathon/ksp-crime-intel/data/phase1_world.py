# phase1_world.py — the fixed backdrop. Writes lookup tables as CSVs.
import random
import pandas as pd
import config as C
import reference_data as R

random.seed(C.SEED)

def build_world():
    # --- State ---
    pd.DataFrame([{"StateID": C.KARNATAKA_STATE_ID, "StateName": "Karnataka", "Active": 1}]) \
        .to_csv(C.OUT / "State.csv", index=False)

    # --- District (+ a socio-econ profile extension table for Module 3) ---
    drows, prows = [], []
    for did, name, lat, lon, pop, lit, urb in R.DISTRICTS:
        drows.append({"DistrictID": did, "DistrictName": name,
                      "StateID": C.KARNATAKA_STATE_ID, "Active": 1})
        # socio_econ_index: simple composite (higher = better-off) — for the regression demo
        socio = round(0.5 * lit + 0.3 * urb + 0.2 * (pop / 9600000), 3)
        prows.append({"DistrictID": did, "Population": pop, "LiteracyRate": lit,
                      "UrbanRatio": urb, "PopDensityRank": did, "SocioEconIndex": socio,
                      "CentroidLat": lat, "CentroidLon": lon})
    pd.DataFrame(drows).to_csv(C.OUT / "District.csv", index=False)
    pd.DataFrame(prows).to_csv(C.OUT / "DistrictProfile.csv", index=False)  # EXTENSION table

    # --- UnitType ---
    pd.DataFrame([{"UnitTypeID": i, "UnitTypeName": n} for i, n in R.UNIT_TYPES]) \
        .to_csv(C.OUT / "UnitType.csv", index=False)

    # --- Unit (police stations) ---
    units, uid = [], 1
    for did, name, lat, lon, *_ in R.DISTRICTS:
        n = random.randint(*R.STATIONS_PER_DISTRICT)
        for s in range(n):
            units.append({"UnitID": uid, "UnitName": f"{name} PS-{s+1}",
                          "TypeID": 1, "StateID": C.KARNATAKA_STATE_ID,
                          "DistrictID": did, "ParentUnit": None, "Active": 1})
            uid += 1
    pd.DataFrame(units).to_csv(C.OUT / "Unit.csv", index=False)

    # --- Crime classification ---
    pd.DataFrame([{"CrimeHeadID": i, "CrimeGroupName": n, "Active": 1}
                  for i, n in R.CRIME_HEADS]).to_csv(C.OUT / "CrimeHead.csv", index=False)
    pd.DataFrame([{"CrimeSubHeadID": sid, "CrimeHeadID": hid, "CrimeHeadName": nm}
                  for sid, hid, nm, *_ in R.CRIME_SUBHEADS]) \
        .to_csv(C.OUT / "CrimeSubHead.csv", index=False)

    # --- Acts & Sections (kept small for the demo) ---
    pd.DataFrame([{"ActCode": "IPC", "ActDescription": "Indian Penal Code",
                   "ShortName": "IPC", "Active": 1}]).to_csv(C.OUT / "Act.csv", index=False)
    sections = sorted({s for secs in R.SUBHEAD_SECTIONS.values() for s in secs})
    pd.DataFrame([{"ActCode": "IPC", "SectionCode": s, "SectionDescription": f"IPC {s}",
                   "Active": 1} for s in sections]).to_csv(C.OUT / "Section.csv", index=False)

    # --- Small lookups ---
    pd.DataFrame([{"CaseCategoryID": i, "CodeDigit": d, "LookupValue": n}
                  for i, d, n in R.CASE_CATEGORIES]).to_csv(C.OUT / "CaseCategory.csv", index=False)
    pd.DataFrame([{"GravityOffenceID": i, "LookupValue": n}
                  for i, n in R.GRAVITY]).to_csv(C.OUT / "GravityOffence.csv", index=False)
    pd.DataFrame([{"CaseStatusID": i, "CaseStatusName": n}
                  for i, n in R.CASE_STATUS]).to_csv(C.OUT / "CaseStatusMaster.csv", index=False)
    pd.DataFrame([{"OccupationID": i, "OccupationName": n}
                  for i, n in R.OCCUPATIONS]).to_csv(C.OUT / "OccupationMaster.csv", index=False)

    # --- Employee stub (so CaseMaster.PolicePersonID / IOID resolve) ---
    emp = [{"EmployeeID": i, "FirstName": f"Officer{i}", "DistrictID": random.randint(1, 31),
            "UnitID": random.randint(1, len(units)), "RankID": 1, "DesignationID": 1}
           for i in range(1, 51)]
    pd.DataFrame(emp).to_csv(C.OUT / "Employee.csv", index=False)

    print(f"Phase 1 done: 31 districts, {len(units)} stations, "
          f"{len(R.CRIME_SUBHEADS)} crime sub-heads written to output/")

if __name__ == "__main__":
    build_world()
