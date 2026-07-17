"""
module3_risk.py — SPEAR Module 3 · Phase 1: risk scoring (district×crime×month).
Reads PUBLIC tables only. Never opens data/ground_truth/.
Run:  python src/module3_risk.py        (~30–90s)
"""
from __future__ import annotations
from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor

DB_PATH = Path("data/output/crime.db")

COLS = dict(
    case_id   = "CaseMasterID",
    case_date = "CrimeRegisteredDate",
    district  = "DistrictID",
    subhead   = "CrimeMinorHeadID",
    unit      = "PoliceStationID",
)
USE_UNIT_JOIN = True

PROFILE_COLS = dict(
    district = "DistrictID",
    pop      = "Population",
    literacy = "LiteracyRate",
    density  = "PopDensity",
    urban    = "UrbanRatio",
)

TEST_MONTHS = 6                   # temporal holdout: last 6 months
TOP_K       = 20                  # patrol budget: top-20 cells per month
SEED        = 42

# ---------------------------------------------------------------- load
def load_panel(conn) -> pd.DataFrame:
    c = COLS
    if USE_UNIT_JOIN:
        q = (f"SELECT cm.{c['case_id']}, cm.{c['case_date']}, cm.{c['subhead']}, "
             f"u.{c['district']} AS DistrictID "
             f"FROM CaseMaster cm LEFT JOIN Unit u ON cm.{c['unit']} = u.UnitID")
    else:
        q = (f"SELECT {c['case_id']}, {c['case_date']}, {c['subhead']}, "
             f"{c['district']} AS DistrictID FROM CaseMaster")
    df = pd.read_sql(q, conn)
    df["ym"] = pd.to_datetime(df[c["case_date"]], errors="coerce") \
                 .dt.to_period("M").astype(str)
    df = df.dropna(subset=["ym", "DistrictID"])
    counts = (df.groupby(["DistrictID", c["subhead"], "ym"])
                .size().rename("cases").reset_index()
                .rename(columns={c["subhead"]: "CrimeTypeID"}))

    # full grid so zero-months exist (a cell with no crime is still a prediction target)
    months  = sorted(df["ym"].unique())
    grid = pd.MultiIndex.from_product(
        [sorted(counts.DistrictID.unique()),
         sorted(counts.CrimeTypeID.unique()), months],
        names=["DistrictID", "CrimeTypeID", "ym"]).to_frame(index=False)
    panel = grid.merge(counts, how="left").fillna({"cases": 0})
    panel["t"] = panel["ym"].map({m: i for i, m in enumerate(months)})
    return panel, months

def add_features(panel: pd.DataFrame, profile: pd.DataFrame) -> pd.DataFrame:
    panel = panel.sort_values(["DistrictID", "CrimeTypeID", "t"]).reset_index(drop=True)
    g = panel.groupby(["DistrictID", "CrimeTypeID"])["cases"]
    for lag in (1, 2, 3, 12):
        panel[f"lag{lag}"] = g.shift(lag)
    panel["roll3"] = panel.groupby(["DistrictID", "CrimeTypeID"])["lag1"].rolling(3).mean().values
    panel["roll6"] = panel.groupby(["DistrictID", "CrimeTypeID"])["lag1"].rolling(6).mean().values
    month_num = panel["ym"].str[-2:].astype(int)
    panel["m_sin"] = np.sin(2 * np.pi * month_num / 12)
    panel["m_cos"] = np.cos(2 * np.pi * month_num / 12)
    p = PROFILE_COLS
    prof = profile.rename(columns={p["district"]: "DistrictID"})
    keep = ["DistrictID"] + [p[k] for k in ("pop", "literacy", "density", "urban")
                             if p[k] in prof.columns]
    panel = panel.merge(prof[keep], on="DistrictID", how="left")
    panel["type_hist_mean"] = g.transform(lambda s: s.shift(1).expanding().mean())
    return panel

FEATURES_BASE = ["lag1", "lag2", "lag3", "lag12", "roll3", "roll6",
                 "m_sin", "m_cos", "type_hist_mean"]

def main():
    conn = sqlite3.connect(DB_PATH)
    profile = pd.read_sql("SELECT * FROM DistrictProfile", conn)
    panel, months = load_panel(conn)
    panel = add_features(panel, profile)

    cov = [PROFILE_COLS[k] for k in ("literacy", "density", "urban")
           if PROFILE_COLS[k] in panel.columns]
    FEATURES = FEATURES_BASE + cov

    cutoff_t = len(months) - TEST_MONTHS
    train = panel[(panel.t < cutoff_t) & panel[FEATURES].notna().all(axis=1)]
    print(f"Panel: {len(panel):,} cells over {len(months)} months "
          f"({panel.DistrictID.nunique()} districts × "
          f"{panel.CrimeTypeID.nunique()} crime types)")
    print(f"Training on t < {cutoff_t} ({len(train):,} rows), "
          f"testing on last {TEST_MONTHS} months.")

    model = GradientBoostingRegressor(random_state=SEED, n_estimators=300,
                                      max_depth=3, learning_rate=0.05)
    model.fit(train[FEATURES], train["cases"])

    scored = panel[panel[FEATURES].notna().all(axis=1)].copy()
    scored["pred"] = np.clip(model.predict(scored[FEATURES]), 0, None)

    # percentile → bands, within each month
    scored["risk_pct"] = scored.groupby("ym")["pred"].rank(pct=True)
    scored["RiskBand"] = pd.cut(scored["risk_pct"], [0, .70, .90, 1.0],
                                labels=["Low", "Medium", "High"])

    # ---- backtest: precision@K per held-out month ----
    rows = []
    for t in range(cutoff_t, len(months)):
        mth = scored[scored.t == t]
        top_pred   = set(map(tuple, mth.nlargest(TOP_K, "pred")
                             [["DistrictID", "CrimeTypeID"]].values))
        top_actual = set(map(tuple, mth.nlargest(TOP_K, "cases")
                             [["DistrictID", "CrimeTypeID"]].values))
        prev = scored[scored.t == t - 1]
        top_prev = set(map(tuple, prev.nlargest(TOP_K, "cases")
                           [["DistrictID", "CrimeTypeID"]].values))
        n_cells = mth.shape[0]
        rows.append(dict(ym=months[t],
                         hit_rate=len(top_pred & top_actual) / TOP_K,
                         baseline_persistence=len(top_prev & top_actual) / TOP_K,
                         random_expectation=TOP_K / n_cells))
    bt = pd.DataFrame(rows)

    fi = (pd.DataFrame({"feature": FEATURES,
                        "importance": model.feature_importances_.round(4)})
            .sort_values("importance", ascending=False))

    scored[["DistrictID", "CrimeTypeID", "ym", "cases", "pred",
            "risk_pct", "RiskBand"]].to_sql("RiskScore", conn,
                                            if_exists="replace", index=False)
    bt.to_sql("RiskBacktest", conn, if_exists="replace", index=False)
    fi.to_sql("RiskFeatureImportance", conn, if_exists="replace", index=False)
    conn.close()

    print("\nBacktest (held-out months):")
    print(bt.round(3).to_string(index=False))
    print(f"\nMean hit-rate @ top-{TOP_K}: {bt.hit_rate.mean():.1%}  "
          f"(persistence baseline {bt.baseline_persistence.mean():.1%}, "
          f"random {bt.random_expectation.mean():.2%})")
    print("\nTop feature importances:")
    print(fi.head(8).to_string(index=False))

if __name__ == "__main__":
    main()
