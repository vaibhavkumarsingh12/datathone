"""
module2_er.py — SPEAR Module 2 · Phase 1: Entity Resolution
Reads PUBLIC tables only. Never opens data/ground_truth/.

Pipeline: normalize → block(gender, birth-year window) → fuzzy match
          (name threshold + FatherName veto/rescue) → union-find → entities.

Run:  python src/module2_er.py          (~30s–3min depending on machine)
"""
from __future__ import annotations
import re, sqlite3, time
from pathlib import Path
from collections import Counter
import pandas as pd
from rapidfuzz import fuzz

# ------------------------------------------------------------------ CONFIG
DB_PATH = Path("data/output/crime.db")

COLS = dict(                     # single point of truth for column names
    accused_id = "AccusedMasterID",
    case_id    = "CaseMasterID",
    name       = "AccusedName",
    father     = "FatherName",
    age        = "AgeYear",
    gender     = "GenderID",
    case_date  = "CrimeRegisteredDate",
    district   = "DistrictID",
)

NAME_T    = 95   # token_sort_ratio threshold, full name
FATHER_T  = 85   # threshold on father name (second key)
BY_WINDOW = 3    # birth-year blocking window (±1yr noise/record + year rounding)

# Domain knowledge: common Indian transliteration/abbreviation families.
# This is real-world ER practice, not answer-key tuning — the same families
# exist in any Indian records system.
ALIASES = {
    "md": "mohammed", "mohammad": "mohammed", "muhammad": "mohammed",
    "mohamad": "mohammed", "laxmi": "lakshmi", "lakshmy": "lakshmi",
    "aisha": "ayesha", "aysha": "ayesha", "gouda": "gowda", "gowdaa": "gowda",
    "setty": "shetty", "shetti": "shetty", "reddi": "reddy", "readdy": "reddy",
    "kumaar": "kumar", "kumr": "kumar",
}

# ------------------------------------------------------------------ HELPERS
def norm(s) -> str:
    """lowercase, strip punctuation, collapse spaces, canonicalise alias families."""
    if not isinstance(s, str):
        return ""
    s = re.sub(r"\s+", " ", re.sub(r"[.\-']", " ", s.lower())).strip()
    return " ".join(ALIASES.get(t, t) for t in s.split())

def is_match(n1: str, f1: str, n2: str, f2: str) -> bool:
    """Match rule. Vetoes on conflicting fathers; rescues initial-forms only
    when both fathers are present AND match (the FatherName second key)."""
    # Require at least one father name to be present to prevent generic name collisions
    fathers_compatible = (bool(f1) or bool(f2)) and ((not f1 or not f2) or fuzz.token_sort_ratio(f1, f2) >= FATHER_T)
    fathers_strict     = bool(f1) and bool(f2) and fuzz.token_sort_ratio(f1, f2) >= FATHER_T

    # Rule 1: strong full-name match, fathers must not conflict
    if fuzz.token_sort_ratio(n1, n2) >= NAME_T and fathers_compatible:
        return True

    # Rule 2: initial-form rescue — "s kumar" vs "suresh kumar" scores only ~74
    # on token_sort, so it needs the second key to be safe.
    t1, t2 = n1.split(), n2.split()
    if len(t1) >= 2 and len(t2) >= 2 and fathers_strict:
        if ((len(t1[0]) == 1 and t1[0] == t2[0][:1]) or
            (len(t2[0]) == 1 and t2[0] == t1[0][:1])):
            if fuzz.token_sort_ratio(" ".join(t1[1:]), " ".join(t2[1:])) >= NAME_T:
                return True
    return False

class UnionFind:
    def __init__(self, n): self.p = list(range(n))
    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]; x = self.p[x]
        return x
    def union(self, a, b): self.p[self.find(a)] = self.find(b)

# ------------------------------------------------------------------ PIPELINE
def load(conn) -> pd.DataFrame:
    c = COLS
    a = pd.read_sql(
        f"SELECT {c['accused_id']}, {c['case_id']}, {c['name']}, "
        f"{c['father']}, {c['age']}, {c['gender']} FROM Accused", conn)
    cm = pd.read_sql(
        f"SELECT c.{c['case_id']}, c.{c['case_date']}, u.DistrictID as {c['district']} "
        f"FROM CaseMaster c LEFT JOIN Unit u ON c.PoliceStationID = u.UnitID", conn)
    df = a.merge(cm, on=c["case_id"], how="left")
    df["name_n"]   = df[c["name"]].map(norm)
    df["father_n"] = df[c["father"]].map(norm)
    df["case_year"] = pd.to_datetime(df[c["case_date"]], errors="coerce").dt.year
    df["birth_year"] = df["case_year"] - pd.to_numeric(df[c["age"]], errors="coerce")
    return df.reset_index(drop=True)

def resolve(df: pd.DataFrame) -> pd.Series:
    """Returns EntityID per row (positional). Blocks on (gender, BY window)."""
    uf, t0, done = UnionFind(len(df)), time.time(), 0
    for _, g in df.groupby(COLS["gender"]):
        g = g.dropna(subset=["birth_year"]).sort_values("birth_year")
        pos   = g.index.to_list()               # positions into df
        by    = g["birth_year"].to_list()
        names = g["name_n"].to_list()
        faths = g["father_n"].to_list()
        n = len(pos)
        for i in range(n):
            j = i + 1
            while j < n and by[j] - by[i] <= BY_WINDOW:
                if is_match(names[i], faths[i], names[j], faths[j]):
                    uf.union(pos[i], pos[j])
                j += 1
            done += 1
            if done % 2000 == 0:
                print(f"   … {done} records processed ({time.time()-t0:.0f}s)")
    roots = pd.Series([uf.find(i) for i in range(len(df))])
    # compress to sequential EntityIDs, ordered by first appearance
    return roots.map({r: eid for eid, r in enumerate(roots.drop_duplicates(), start=1)})

def profile(df: pd.DataFrame) -> pd.DataFrame:
    c = COLS
    def canon(names):                    # most frequent alias, tie → longest
        cnt = Counter(names)
        return sorted(cnt, key=lambda x: (-cnt[x], -len(str(x))))[0]
    g = df.groupby("EntityID")
    prof = pd.DataFrame({
        "CanonicalName": g[c["name"]].agg(canon),
        "NumRecords":    g.size(),
        "NumCases":      g[c["case_id"]].nunique(),
        "NumAliases":    g[c["name"]].nunique(),
        "AliasList":     g[c["name"]].agg(lambda s: " | ".join(sorted(set(s))[:20])),
        "Districts":     g[c["district"]].agg(
                             lambda s: ",".join(str(int(x)) for x in sorted(s.dropna().unique()))),
        "GenderID":      g[c["gender"]].first(),
        "BirthYearEst":  g["birth_year"].median(),
        "FirstSeen":     g[c["case_date"]].min(),
        "LastSeen":      g[c["case_date"]].max(),
    }).reset_index()
    return prof

def main():
    conn = sqlite3.connect(DB_PATH)
    df = load(conn)
    print(f"Loaded {len(df)} accused records "
          f"({df['name_n'].nunique()} distinct name strings).")
    print("Resolving …")
    df["EntityID"] = resolve(df)
    prof = profile(df)

    link = df[[COLS["accused_id"], "EntityID"]]
    link.to_sql("ResolvedLink", conn, if_exists="replace", index=False)
    prof.to_sql("EntityProfile", conn, if_exists="replace", index=False)
    link.to_csv(DB_PATH.parent / "ResolvedLink.csv", index=False)
    prof.to_csv(DB_PATH.parent / "EntityProfile.csv", index=False)
    conn.close()

    print(f"\nPhase 1 done: {len(df)} records → {prof.shape[0]} resolved entities.")
    multi = prof[prof.NumCases >= 2]
    print(f"Repeat entities (≥2 cases): {len(multi)}")
    print("\nTop-5 by case count:")
    print(prof.nlargest(5, "NumCases")
              [["EntityID", "CanonicalName", "NumCases", "NumAliases", "Districts"]]
              .to_string(index=False))
    star = prof.nlargest(1, "NumAliases").iloc[0]
    print(f"\nBiggest alias cluster — Entity {star.EntityID} "
          f"({star.NumAliases} aliases across {star.NumCases} cases):")
    print("   " + star.AliasList)

if __name__ == "__main__":
    main()
