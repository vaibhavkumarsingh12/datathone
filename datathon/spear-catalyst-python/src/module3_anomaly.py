"""
module3_anomaly.py — SPEAR Module 3 · Phase 2: anomalies + socio-econ.
Reads PUBLIC tables only.
Run:  python src/module3_anomaly.py       (~20–60s)
"""
from __future__ import annotations
from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
import statsmodels.api as sm

DB_PATH = Path("data/output/crime.db")

COLS = dict(
    case_id     = "CaseMasterID",
    case_date   = "CrimeRegisteredDate",
    report_date = "InfoReceivedPSDate",   # set to None if it doesn't exist
    district    = "DistrictID",
    subhead     = "CrimeMinorHeadID",
    unit        = "PoliceStationID",
    lat         = "latitude",
    lon         = "longitude",
)
USE_UNIT_JOIN = True
PROFILE_COLS = dict(district="DistrictID", pop="Population",
                    literacy="LiteracyRate", density="PopDensity",
                    urban="UrbanRatio")

CONTAMINATION = 0.01      # flag ~1% of cases — a real analyst's triage budget
SEED = 42

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
    a = np.sin(dp/2)**2 + np.cos(p1)*np.cos(p2)*np.sin(dl/2)**2
    return 2*R*np.arcsin(np.sqrt(a))

def load_cases(conn):
    c = COLS
    want = [c["case_id"], c["case_date"], c["subhead"], c["lat"], c["lon"]]
    if c["report_date"]:
        want.append(c["report_date"])
    if USE_UNIT_JOIN:
        sel = ", ".join(f"cm.{w}" for w in want)
        q = (f"SELECT {sel}, u.{c['district']} AS DistrictID FROM CaseMaster cm "
             f"LEFT JOIN Unit u ON cm.{c['unit']} = u.UnitID")
    else:
        sel = ", ".join(want)
        q = f"SELECT {sel}, {c['district']} AS DistrictID FROM CaseMaster"
    df = pd.read_sql(q, conn)
    df["dt"] = pd.to_datetime(df[c["case_date"]], errors="coerce")
    df["ym"] = df["dt"].dt.to_period("M").astype(str)
    df["hour"], df["dow"] = df["dt"].dt.hour, df["dt"].dt.dayofweek
    return df.dropna(subset=["dt", "DistrictID"]).reset_index(drop=True)

def case_features(df):
    c = COLS
    # circular hour deviation from the crime type's own typical hour
    ang = 2*np.pi*df["hour"]/24
    df["h_sin"], df["h_cos"] = np.sin(ang), np.cos(ang)
    typ = df.groupby(c["subhead"])[["h_sin", "h_cos"]].transform("mean")
    df["hour_dev"] = np.sqrt((df.h_sin - typ.h_sin)**2 + (df.h_cos - typ.h_cos)**2)
    # weekday deviation from type profile
    dow_rate = (df.groupby([c["subhead"], "dow"]).size()
                  / df.groupby(c["subhead"]).size())
    df["dow_rarity"] = 1 - df.set_index([c["subhead"], "dow"]).index.map(dow_rate).values
    # spatial deviation: km from the district's own case centroid
    cen = df.groupby("DistrictID")[[c["lat"], c["lon"]]].transform("mean")
    df["dist_km"] = haversine_km(df[c["lat"]], df[c["lon"]],
                                 cen[c["lat"]], cen[c["lon"]])
    # crime-type rarity within district
    rar = (df.groupby(["DistrictID", c["subhead"]]).size()
             / df.groupby("DistrictID").size())
    df["type_rarity"] = 1 - df.set_index(["DistrictID", c["subhead"]]).index.map(rar).values
    feats = ["hour_dev", "dow_rarity", "dist_km", "type_rarity"]
    # reporting delay (planted bonus anomaly signal)
    if COLS["report_date"] and COLS["report_date"] in df.columns:
        rep = pd.to_datetime(df[COLS["report_date"]], errors="coerce")
        df["report_delay_d"] = (rep - df["dt"]).dt.days.clip(lower=0)
        feats.append("report_delay_d")
    return df, feats

def top_reason(row, feats, z):
    j = int(np.argmax(z))
    labels = dict(hour_dev="unusual time of day for this crime type",
                  dow_rarity="unusual day of week for this crime type",
                  dist_km="far from where this district's cases concentrate",
                  type_rarity="crime type rarely seen in this district",
                  report_delay_d="abnormally long delay before reporting")
    return labels.get(feats[j], feats[j])

def main():
    conn = sqlite3.connect(DB_PATH)
    df = load_cases(conn)
    df, feats = case_features(df)
    X = df[feats].fillna(df[feats].median())

    iso = IsolationForest(contamination=CONTAMINATION, random_state=SEED,
                          n_estimators=300)
    df["anomaly_score"] = -iso.fit(X).score_samples(X)     # higher = weirder
    df["flag"] = (df["anomaly_score"]
                  >= df["anomaly_score"].quantile(1 - CONTAMINATION)).astype(int)
    Z = ((X - X.mean()) / X.std()).abs().values
    df["reason"] = [top_reason(r, feats, Z[i]) if f else ""
                    for i, (r, f) in enumerate(zip(df.itertuples(), df["flag"]))]

    out = df[[COLS["case_id"], "DistrictID", COLS["subhead"], "ym",
              "anomaly_score", "flag", "reason"]]
    out.to_sql("AnomalyScore", conn, if_exists="replace", index=False)
    print(f"Case-level: {len(df):,} cases scored, {int(df.flag.sum())} flagged "
          f"({CONTAMINATION:.0%} budget).")
    print("Top-5 flagged:")
    print(df.nlargest(5, "anomaly_score")
            [[COLS["case_id"], "DistrictID", "ym", "anomaly_score", "reason"]]
            .round(3).to_string(index=False))

    # ---- cell-level volume anomalies (continuous z, all history) ----
    cell = (df.groupby(["DistrictID", COLS["subhead"], "ym"]).size()
              .rename("cases").reset_index())
    cell = cell.sort_values("ym")
    g = cell.groupby(["DistrictID", COLS["subhead"]])["cases"]
    mu, sd = g.transform(lambda s: s.shift(1).expanding().mean()), \
             g.transform(lambda s: s.shift(1).expanding().std())
    cell["z"] = ((cell["cases"] - mu) / sd.replace(0, np.nan)).fillna(0).round(2)
    cell.to_sql("CellAnomaly", conn, if_exists="replace", index=False)
    print(f"\nCell-level: {len(cell):,} district×type×month cells scored; "
          f"max z = {cell.z.max():.1f}")

    # ---- socio-econ correlation + regression ----
    p = PROFILE_COLS
    prof = pd.read_sql("SELECT * FROM DistrictProfile", conn) \
             .rename(columns={p["district"]: "DistrictID"})
    rate = (df.groupby("DistrictID").size().rename("total_cases").reset_index()
              .merge(prof, on="DistrictID"))
    rate["per_100k"] = rate["total_cases"] / rate[p["pop"]] * 1e5
    covs = [p[k] for k in ("literacy", "density", "urban") if p[k] in rate.columns]

    corr = rate[["per_100k"] + covs].corr().round(3)
    corr.to_sql("SocioEconCorr", conn, if_exists="replace")
    X = sm.add_constant(rate[covs].astype(float))
    ols = sm.OLS(rate["per_100k"], X).fit()
    reg = pd.DataFrame({"term": X.columns, "coef": ols.params.round(3),
                        "p_value": ols.pvalues.round(4)})
    reg.to_sql("SocioEconRegression", conn, if_exists="replace", index=False)
    conn.close()

    print("\nSocio-econ correlations with crime per 100k:")
    print(corr["per_100k"].drop("per_100k").to_string())
    print(f"\nOLS R² = {ols.rsquared:.2f}")
    print(reg.to_string(index=False))

if __name__ == "__main__":
    main()
