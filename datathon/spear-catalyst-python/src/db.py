# src/db.py — single source of truth for reading crime.db (cached for Streamlit).
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "output" / "crime.db"

# ---- GeoJSON config (set after step 0.3) ----
GEOJSON_PATH = Path(__file__).resolve().parents[1] / "assets" / "karnataka_districts.geojson"
GEOJSON_NAME_PROP = "DISTRICT"        # <-- CHANGED to 'DISTRICT' which we saw in the GeoJSON

# old-spelling -> our DistrictName
NAME_FIX = {
    "Bangalore": "Bengaluru Urban", "Bangalore Urban": "Bengaluru Urban",
    "Bangalore Rural": "Bengaluru Rural", "Mysore": "Mysuru", "Belgaum": "Belagavi",
    "Gulbarga": "Kalaburagi", "Bijapur": "Vijayapura", "Tumkur": "Tumakuru",
    "Shimoga": "Shivamogga", "Bellary": "Ballari", "Chikmagalur": "Chikkamagaluru",
    "Chikballapur": "Chikkaballapur", "Davangere": "Davanagere",
    "Chamrajnagar": "Chamarajanagar", "Uttar Kannad": "Uttara Kannada",
    "Dakshin Kannad": "Dakshina Kannada",
}

@st.cache_resource
def _conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

@st.cache_data
def load_cases() -> pd.DataFrame:
    """CaseMaster enriched with district, crime names, and time features."""
    q = """
    SELECT c.CaseMasterID, c.CrimeNo, c.CrimeRegisteredDate, c.IncidentFromDate,
           c.latitude, c.longitude, c.PoliceStationID, c.CaseStatusID,
           c.CrimeMajorHeadID, c.CrimeMinorHeadID,
           u.UnitName AS Station, u.DistrictID,
           d.DistrictName,
           h.CrimeGroupName AS CrimeHead,
           s.CrimeHeadName  AS CrimeType
    FROM CaseMaster c
    JOIN Unit u          ON u.UnitID = c.PoliceStationID
    JOIN District d      ON d.DistrictID = u.DistrictID
    JOIN CrimeHead h     ON h.CrimeHeadID = c.CrimeMajorHeadID
    JOIN CrimeSubHead s  ON s.CrimeSubHeadID = c.CrimeMinorHeadID
    """
    df = pd.read_sql(q, _conn(), parse_dates=["IncidentFromDate"])
    df["date"] = pd.to_datetime(df["CrimeRegisteredDate"])
    df["ym"] = df["date"].dt.to_period("M").astype(str)
    df["hour"] = df["IncidentFromDate"].dt.hour
    df["weekday"] = df["IncidentFromDate"].dt.day_name()
    return df

@st.cache_data
def load_district_profile() -> pd.DataFrame:
    prof = pd.read_sql("SELECT * FROM DistrictProfile", _conn())
    dist = pd.read_sql("SELECT DistrictID, DistrictName FROM District", _conn())
    return prof.merge(dist, on="DistrictID")

@st.cache_data
def load_geojson():
    """Return (geojson, name_property) or (None, None) if file missing/unreadable."""
    import json
    try:
        gj = json.loads(GEOJSON_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None, None
    fixed = []
    for feat in gj.get("features", []):
        name = str(feat["properties"].get(GEOJSON_NAME_PROP, "")).strip()
        name = NAME_FIX.get(name, name)
        feat["properties"]["_name"] = name
        fixed.append(feat)
    gj["features"] = fixed
    return gj, "_name"
