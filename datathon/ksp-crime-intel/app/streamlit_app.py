# app/streamlit_app.py — KSP Crime Intelligence dashboard (Module 1).
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # make src importable

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import db
from src import module1_geo as m1

st.set_page_config(page_title="KSP Crime Intelligence", layout="wide", page_icon="🚔")
st.title("🚔 Karnataka Crime Intelligence Platform")
st.caption("Synthetic data grounded in NCRB/SCRB aggregates · prototype for KSP Datathon 2026")

# ---------------- load + sidebar filters ----------------
cases = db.load_cases()
profile = db.load_district_profile()

st.sidebar.header("Filters")
heads = ["All"] + sorted(cases["CrimeHead"].unique())
sel_head = st.sidebar.selectbox("Crime category", heads)
types = ["All"] + sorted(cases.loc[cases["CrimeHead"].eq(sel_head) if sel_head != "All"
                                   else slice(None), "CrimeType"].unique())
sel_type = st.sidebar.selectbox("Crime type", types)
dmin, dmax = cases["date"].min().date(), cases["date"].max().date()
d_from, d_to = st.sidebar.slider("Date range", dmin, dmax, (dmin, dmax))

f = cases[(cases["date"].dt.date >= d_from) & (cases["date"].dt.date <= d_to)]
if sel_head != "All":
    f = f[f["CrimeHead"] == sel_head]
if sel_type != "All":
    f = f[f["CrimeType"] == sel_type]

tab_over, tab_map, tab_hot, tab_time, tab_alert = st.tabs(
    ["📊 Overview", "🗺️ District Map", "🔥 Hotspots", "🕒 Time Patterns", "🚨 Alerts"])

# ---------------- TAB: Overview ----------------
with tab_over:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Cases (filtered)", f"{len(f):,}")
    c2.metric("Districts active", f["DistrictName"].nunique())
    c3.metric("Stations reporting", f["Station"].nunique())
    top = f["CrimeType"].mode()
    c4.metric("Top crime type", top.iloc[0] if len(top) else "—")

    monthly = f.groupby("ym").size().reset_index(name="cases")
    st.plotly_chart(px.line(monthly, x="ym", y="cases", title="Cases per month",
                            markers=True), use_container_width=True)
    st.plotly_chart(px.bar(f["CrimeType"].value_counts().head(10)[::-1],
                           orientation="h", title="Top 10 crime types"),
                    use_container_width=True)

# ---------------- TAB: District Map ----------------
with tab_map:
    per_dist = (f.groupby(["DistrictID", "DistrictName"]).size()
                  .reset_index(name="cases")
                  .merge(profile[["DistrictID", "Population"]], on="DistrictID"))
    per_dist["per_100k"] = (per_dist["cases"] / per_dist["Population"] * 100000).round(1)

    gj, prop = db.load_geojson()
    if gj:
        # Vijayanagara fallback: if the geojson lacks it, fold into Ballari for display
        gj_names = {ft["properties"][prop] for ft in gj["features"]}
        disp = per_dist.copy()
        if "Vijayanagara" not in gj_names and "Vijayanagara" in set(disp.DistrictName):
            vj = disp[disp.DistrictName == "Vijayanagara"]
            disp.loc[disp.DistrictName == "Ballari", ["cases"]] += int(vj["cases"].iloc[0])
            disp = disp[disp.DistrictName != "Vijayanagara"]
            st.caption("Note: Vijayanagara shown merged into Ballari (boundary file predates 2021 split).")
        fig = px.choropleth_mapbox(
            disp, geojson=gj, locations="DistrictName",
            featureidkey=f"properties.{prop}", color="per_100k",
            color_continuous_scale="Reds", mapbox_style="carto-positron",
            center={"lat": 14.8, "lon": 75.7}, zoom=5.6, opacity=0.75,
            hover_data={"cases": True, "per_100k": True},
            title="Crime rate per 100k population")
        fig.update_layout(height=650, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No boundary file found (assets/karnataka_districts.geojson) — showing density map.")
        fig = px.density_mapbox(f, lat="latitude", lon="longitude", radius=6,
                                center={"lat": 14.8, "lon": 75.7}, zoom=5.6,
                                mapbox_style="carto-positron", height=650)
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Drill-down: stations in a district")
    pick = st.selectbox("District", sorted(f["DistrictName"].unique()))
    stn = (f[f["DistrictName"] == pick].groupby("Station").size()
             .sort_values(ascending=False).reset_index(name="cases"))
    st.plotly_chart(px.bar(stn, x="Station", y="cases",
                           title=f"Cases by police station — {pick}"),
                    use_container_width=True)
    st.dataframe(per_dist.sort_values("per_100k", ascending=False),
                 use_container_width=True, hide_index=True)

# ---------------- TAB: Hotspots ----------------
with tab_hot:
    col1, col2 = st.columns(2)
    eps_km = col1.slider("Cluster radius (km)", 0.5, 8.0, 2.0, 0.5)
    min_s = col2.slider("Min cases per hotspot", 10, 100, 25, 5)

    clustered = m1.find_hotspots(f, eps_km=eps_km, min_samples=min_s)
    summ = m1.hotspot_summary(clustered)

    if summ.empty:
        st.warning("No hotspots at these settings — widen the radius or lower min cases.")
    else:
        st.success(f"{len(summ)} hotspot(s) detected")
        hs = clustered[clustered["cluster"] >= 0]
        fig = px.scatter_mapbox(
            hs, lat="latitude", lon="longitude", color=hs["cluster"].astype(str),
            hover_data=["DistrictName", "CrimeType"], zoom=5.6,
            center={"lat": 14.8, "lon": 75.7}, mapbox_style="carto-positron", height=600,
            title="Detected crime hotspots (each color = one cluster)")
        fig.update_layout(margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(summ.rename(columns={
            "cluster": "Hotspot #", "n_cases": "Cases", "district": "District",
            "top_crime": "Dominant crime"}), use_container_width=True, hide_index=True)

# ---------------- TAB: Time Patterns ----------------
with tab_time:
    m = m1.time_heatmap_matrix(f)
    fig = go.Figure(go.Heatmap(z=m.values, x=list(m.columns), y=list(m.index),
                               colorscale="Reds"))
    fig.update_layout(title="When does crime happen? (day × hour of incident)",
                      xaxis_title="Hour of day", yaxis_title="", height=450)
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Tip: filter to a single crime type in the sidebar — e.g. Chain Snatching "
               "glows on weekend evenings; House Burglary glows at night.")

# ---------------- TAB: Alerts ----------------
with tab_alert:
    z_t = st.slider("Alert threshold (z-score)", 1.5, 4.0, 2.0, 0.1)
    alerts = m1.spike_alerts(cases if sel_head == "All" and sel_type == "All" else f,
                             z_thresh=z_t)
    if alerts.empty:
        st.info("No spikes above threshold in the current view.")
    else:
        st.error(f"🚨 {len(alerts)} red-zone spike(s) detected")
        st.dataframe(alerts.rename(columns={
            "DistrictName": "District", "CrimeType": "Crime", "ym": "Month",
            "cases": "Cases", "baseline": "Expected", "z": "Z-score"}),
            use_container_width=True, hide_index=True)
        top = alerts.iloc[0]
        hist = (cases[(cases.DistrictName == top.DistrictName) &
                      (cases.CrimeType == top.CrimeType)]
                .groupby("ym").size().reset_index(name="cases"))
        fig = px.bar(hist, x="ym", y="cases",
                     title=f"Worst spike: {top.CrimeType} in {top.DistrictName}")
        fig.add_vline(x=top.ym, line_color="red", line_dash="dash")
        st.plotly_chart(fig, use_container_width=True)
