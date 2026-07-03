# src/module1_geo.py — Module 1 analytics: DBSCAN hotspots, time heatmap, z-score alerts.
import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN

EARTH_KM = 6371.0

# ---------------------------------------------------------------- hotspots
def find_hotspots(df: pd.DataFrame, eps_km: float = 2.0, min_samples: int = 25) -> pd.DataFrame:
    """DBSCAN on lat/lon with a haversine metric.
    Returns df with a 'cluster' column (-1 = noise) plus a summary per cluster."""
    pts = np.radians(df[["latitude", "longitude"]].to_numpy())
    labels = DBSCAN(eps=eps_km / EARTH_KM, min_samples=min_samples,
                    metric="haversine").fit_predict(pts)
    out = df.copy()
    out["cluster"] = labels
    return out

def hotspot_summary(clustered: pd.DataFrame) -> pd.DataFrame:
    hs = clustered[clustered["cluster"] >= 0]
    if hs.empty:
        return pd.DataFrame()
    return (hs.groupby("cluster")
              .agg(n_cases=("CaseMasterID", "count"),
                   lat=("latitude", "mean"), lon=("longitude", "mean"),
                   district=("DistrictName", lambda s: s.mode().iloc[0]),
                   top_crime=("CrimeType", lambda s: s.mode().iloc[0]))
              .sort_values("n_cases", ascending=False)
              .reset_index())

# ---------------------------------------------------------------- time heatmap
WEEKDAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

def time_heatmap_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """weekday x hour count matrix (rows ordered Mon..Sun)."""
    m = (df.groupby(["weekday", "hour"]).size().unstack(fill_value=0)
           .reindex(WEEKDAY_ORDER).fillna(0))
    return m.reindex(columns=range(24), fill_value=0)

# ---------------------------------------------------------------- z-score alerts
def spike_alerts(df: pd.DataFrame, z_thresh: float = 2.0, window: int = 6,
                 min_history: int = 4) -> pd.DataFrame:
    """Per (district, crime type, month): z = (count - rolling_mean) / rolling_std
    over the PREVIOUS `window` months. Returns all month-cells with z >= threshold."""
    monthly = (df.groupby(["DistrictName", "CrimeType", "ym"])
                 .size().rename("n").reset_index())
    # complete the month grid so silent months count as 0
    all_months = sorted(df["ym"].unique())
    rows = []
    for (dist, ct), g in monthly.groupby(["DistrictName", "CrimeType"]):
        s = g.set_index("ym")["n"].reindex(all_months, fill_value=0)
        mean = s.shift(1).rolling(window, min_periods=min_history).mean()
        std = s.shift(1).rolling(window, min_periods=min_history).std().replace(0, np.nan)
        for ym in mean.dropna().index:
            count = s[ym]
            zval = None
            if pd.notna(std[ym]) and std[ym] > 0:
                zval = (count - mean[ym]) / std[ym]

            is_eruption = count >= 15 and count >= 3 * max(mean[ym], 1)
            is_surge = (count >= 8 and mean[ym] >= 3
                        and zval is not None and zval >= z_thresh)

            if is_eruption or is_surge:
                rows.append({"DistrictName": dist, "CrimeType": ct, "ym": ym,
                             "cases": int(count), "baseline": round(float(mean[ym]), 1),
                             "z": round(float(zval), 2) if zval is not None else None,
                             "kind": "eruption" if is_eruption else "surge"})
    return (pd.DataFrame(rows).sort_values("z", ascending=False).reset_index(drop=True)
            if rows else pd.DataFrame(columns=["DistrictName","CrimeType","ym","cases","baseline","z", "kind"]))
