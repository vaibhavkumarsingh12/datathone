# app/streamlit_app_spear.py — KSP Crime Intelligence dashboard (Module 1)
# SPEAR-themed version. Original streamlit_app.py is untouched.
#
# Run from the repo root:   streamlit run app/streamlit_app_spear.py
# Requires .streamlit/config.toml (SPEAR dark theme) at the repo root.

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # make src importable

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import json
import sqlite3
import src.db as db
from network_tab import render_network_tab
from risk_anomaly_tab import render_risk_tab, render_anomaly_tab

from src import module1_geo as m1

# ============================================================
# SPEAR design tokens (dark "command-center" theme)
# ============================================================
T = {
    "bg_app":        "#090F17",
    "bg_surface":    "#111A26",
    "bg_surface_2":  "#16212F",
    "bg_inset":      "#0C141E",
    "bg_hover":      "#1B2836",
    "border_subtle": "#1B2735",
    "border":        "#26364A",
    "border_strong": "#35485F",
    "text":          "#E8EDF2",
    "text_2":        "#A4B2C1",
    "muted":         "#6C7D90",
    "accent":        "#4C87D8",
    "accent_soft":   "rgba(76,135,216,0.16)",
    "critical":      "#EC7468",
    "warning":       "#E3B94A",
    "success":       "#57C58C",
}
# Categorical series colors (brightened for dark ground)
SERIES = ["#5A9BE6", "#4FC48B", "#E3B94A", "#EC7468",
          "#A98BD6", "#45C0B2", "#D08A5E", "#7E97B0"]
# SWD rule 4 — "everything else" colour. One accent per chart; the rest is slate.
SLATE = "#3A4C63"
# Sequential ramp for choropleth / heatmaps (inset → critical red)
HEAT_SCALE = [
    [0.0, "#16212F"], [0.25, "#3A4C63"], [0.5, "#8A5A46"],
    [0.75, "#C05C3A"], [1.0, "#EC7468"],
]

st.set_page_config(page_title="SPEAR — KSP Crime Intelligence",
                   layout="wide", page_icon="🛡️")

# ============================================================
# Global CSS — IBM Plex + SPEAR chrome
# ============================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans+Condensed:wght@500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');

html, body, [class*="css"], .stApp, .stMarkdown, p, div, span, label {
  font-family: 'IBM Plex Sans', sans-serif;
}
.stApp { background: #090F17; }

/* ---- hide default Streamlit chrome ---- */
#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; height: 0; }
.block-container { padding-top: 1.4rem; padding-bottom: 2rem; max-width: 1500px; }

/* ---- sidebar ---- */
section[data-testid="stSidebar"] {
  background: #111A26;
  border-right: 1px solid #1B2735;
}
section[data-testid="stSidebar"] .stMarkdown p { color: #A4B2C1; }
section[data-testid="stSidebar"] label {
  font-family: 'IBM Plex Sans Condensed', sans-serif !important;
  font-size: 11px !important; font-weight: 600 !important;
  letter-spacing: 0.08em; text-transform: uppercase; color: #6C7D90 !important;
}

/* ---- SPEAR brand block ---- */
.spear-brand { display:flex; align-items:center; gap:10px; padding:2px 0 10px; }
.spear-mark {
  width:34px; height:34px; border-radius:7px; background:#4C87D8;
  display:flex; align-items:center; justify-content:center;
  color:#08111E; font:700 15px 'IBM Plex Mono', monospace;
}
.spear-brand-name { font:600 15px 'IBM Plex Sans', sans-serif; color:#E8EDF2; line-height:1.15; }
.spear-brand-sub {
  font:500 9.5px 'IBM Plex Sans Condensed', sans-serif; letter-spacing:0.1em;
  text-transform:uppercase; color:#6C7D90;
}

/* ---- page header ---- */
.spear-eyebrow {
  font:600 11px 'IBM Plex Sans Condensed', sans-serif; letter-spacing:0.12em;
  text-transform:uppercase; color:#4C87D8; margin:0 0 4px;
}
.spear-h1 { font:600 26px/1.2 'IBM Plex Sans', sans-serif; color:#E8EDF2; margin:0; }
.spear-caption { font:400 13px 'IBM Plex Sans', sans-serif; color:#6C7D90; margin:4px 0 0; }

/* ---- stat cards ---- */
.spear-stat {
  position:relative; background:#111A26; border:1px solid #26364A;
  border-radius:10px; padding:14px 16px 13px 18px; overflow:hidden;
}
.spear-stat::before {
  content:''; position:absolute; left:0; top:0; bottom:0; width:3px;
  background:var(--stat-accent, #4C87D8);
}
.spear-stat-label {
  font:600 10.5px 'IBM Plex Sans Condensed', sans-serif; letter-spacing:0.09em;
  text-transform:uppercase; color:#6C7D90; margin-bottom:6px;
}
.spear-stat-value {
  font:600 26px/1.1 'IBM Plex Sans', sans-serif; color:#E8EDF2;
  font-variant-numeric: tabular-nums lining-nums;
}
.spear-stat-sub { font:400 11.5px 'IBM Plex Sans', sans-serif; color:#A4B2C1; margin-top:3px; }

/* ---- tabs ---- */
.stTabs [data-baseweb="tab-list"] {
  gap: 2px; background:#0C141E; padding:4px; border-radius:8px;
  border:1px solid #1B2735; width:fit-content;
}
.stTabs [data-baseweb="tab"] {
  font:500 13px 'IBM Plex Sans', sans-serif; color:#A4B2C1;
  border-radius:6px; padding:7px 16px; background:transparent;
}
.stTabs [aria-selected="true"] {
  background:#1B2836 !important; color:#E8EDF2 !important;
}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display:none; }

/* ---- cards around charts (st.container(border=True)) ---- */
div[data-testid="stVerticalBlockBorderWrapper"] {
  background:#111A26; border:1px solid #26364A !important; border-radius:10px;
}

/* ---- dataframes ---- */
div[data-testid="stDataFrame"] {
  border:1px solid #26364A; border-radius:10px; overflow:hidden;
}

/* ---- alerts / info boxes ---- */
div[data-testid="stAlert"] { border-radius:8px; }

/* ---- section subheaders ---- */
h3 { font:600 17px 'IBM Plex Sans', sans-serif !important; color:#E8EDF2 !important; }

/* ---- sliders / selects accent ---- */
div[data-baseweb="select"] > div { background:#0C141E; border-color:#26364A; }
</style>
""", unsafe_allow_html=True)


# ============================================================
# Plotly theming helper — call on EVERY figure before st.plotly_chart
# ============================================================
def spear_fig(fig, height=None, title=None):
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Sans, sans-serif", color=T["text_2"], size=12),
        title_font=dict(family="IBM Plex Sans, sans-serif", size=15, color=T["text"]),
        margin=dict(l=10, r=10, t=42 if (title or fig.layout.title.text) else 16, b=10),
        colorway=SERIES,
        hoverlabel=dict(bgcolor=T["bg_surface_2"], bordercolor=T["border"],
                        font=dict(family="IBM Plex Sans, sans-serif", color=T["text"], size=12)),
        legend=dict(font=dict(color=T["text_2"], size=11), bgcolor="rgba(0,0,0,0)"),
    )
    if title:
        fig.update_layout(title_text=title)
    if height:
        fig.update_layout(height=height)
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=T["border"],
                     tickfont=dict(color=T["muted"], size=11), title_font=dict(color=T["muted"], size=11))
    fig.update_yaxes(showgrid=True, gridcolor=T["border_subtle"], zeroline=False,
                     linecolor="rgba(0,0,0,0)",
                     tickfont=dict(color=T["muted"], size=11), title_font=dict(color=T["muted"], size=11))
    return fig


@st.cache_data(show_spinner=False)
def load_metrics():
    """SWD rule 6 / Module 4: action titles quote the SEALED exam files —
    they are never recomputed here. Missing file = empty dict, titles degrade
    gracefully to plain labels."""
    out = {}
    rep = Path(__file__).resolve().parents[1] / "reports"
    for name in ["module1_metrics", "module2_metrics", "module3_metrics"]:
        p = rep / f"{name}.json"
        try:
            out[name] = json.loads(p.read_text())
        except Exception:
            out[name] = {}
    return out


M = load_metrics()


def stat_card(col, label, value, sub="", accent="#4C87D8"):
    col.markdown(
        f"""<div class="spear-stat" style="--stat-accent:{accent}">
              <div class="spear-stat-label">{label}</div>
              <div class="spear-stat-value">{value}</div>
              <div class="spear-stat-sub">{sub}</div>
            </div>""",
        unsafe_allow_html=True)


# ============================================================
# Data + sidebar filters
# ============================================================
cases = db.load_cases()
profile = db.load_district_profile()

with st.sidebar:
    st.markdown("""
      <div class="spear-brand">
        <div class="spear-mark">S</div>
        <div>
          <div class="spear-brand-name">SPEAR</div>
          <div class="spear-brand-sub">Crime Intelligence</div>
        </div>
      </div>""", unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("**Filters**")

    heads = ["All"] + sorted(cases["CrimeHead"].unique())
    sel_head = st.selectbox("Crime category", heads)
    types = ["All"] + sorted(cases.loc[cases["CrimeHead"].eq(sel_head) if sel_head != "All"
                                       else slice(None), "CrimeType"].unique())
    sel_type = st.selectbox("Crime type", types)
    dmin, dmax = cases["date"].min().date(), cases["date"].max().date()
    d_from, d_to = st.slider("Date range", dmin, dmax, (dmin, dmax))

f = cases[(cases["date"].dt.date >= d_from) & (cases["date"].dt.date <= d_to)]
if sel_head != "All":
    f = f[f["CrimeHead"] == sel_head]
if sel_type != "All":
    f = f[f["CrimeType"] == sel_type]

# ---- page header ----
st.markdown("""
  <div class="spear-eyebrow">Module 1 · Spatial &amp; Temporal Analytics</div>
  <div class="spear-h1">Karnataka Crime Intelligence Platform</div>
  <div class="spear-caption">Synthetic data grounded in NCRB/SCRB aggregates · prototype for KSP Datathon 2026</div>
""", unsafe_allow_html=True)
st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

tab_over, tab_map, tab_hot, tab_time, tab_alert, tab_network, tab_risk, tab_anom = st.tabs(
    ["Overview", "District Map", "Hotspots", "Time Patterns", "Alerts", "🕸️ Network", "🎯 Risk", "🚨 Anomalies"])

# ---------------- TAB: Overview ----------------
with tab_over:
    c1, c2, c3, c4 = st.columns(4)
    top = f["CrimeType"].mode()
    stat_card(c1, "Cases (filtered)", f"{len(f):,}", "in current view", "#4C87D8")
    stat_card(c2, "Districts active", f["DistrictName"].nunique(), "of 31 districts", "#57C58C")
    stat_card(c3, "Stations reporting", f["Station"].nunique(), "police stations", "#E3B94A")
    stat_card(c4, "Top crime type", top.iloc[0] if len(top) else "—", "most frequent", "#EC7468")

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    monthly = f.groupby("ym").size().reset_index(name="cases")
    with st.container(border=True):
        # SWD rule 6 — action title written by the data itself
        if len(monthly):
            med = int(monthly["cases"].median())
            pk = monthly.loc[monthly["cases"].idxmax()]
            t_month = (f"Caseload holds near {med:,} cases/month — "
                       f"peaking at {int(pk['cases']):,} in {pk['ym']}")
        else:
            t_month = "Cases per month"
        fig = px.line(monthly, x="ym", y="cases", markers=True)
        fig.update_traces(line=dict(width=2.2, color=SERIES[0]),
                          marker=dict(size=6, color=SERIES[0]))
        fig.update_layout(xaxis_title=None, yaxis_title=None)  # declutter: title says it
        st.plotly_chart(spear_fig(fig, height=340, title=t_month),
                        use_container_width=True)

    with st.container(border=True):
        vc = f["CrimeType"].value_counts().head(10)
        if len(vc):
            share = 100 * int(vc.iloc[0]) / max(len(f), 1)
            t_types = (f"{vc.index[0]} leads at {int(vc.iloc[0]):,} cases — "
                       f"{share:.0f}% of all crime in this view")
        else:
            t_types = "Top 10 crime types"
        vc_asc = vc[::-1]                     # Plotly draws bottom-up
        # SWD rule 4 — ONE accent: the leader is accented, everything else slate
        bar_colors = [SERIES[0] if i == len(vc_asc) - 1 else SLATE
                      for i in range(len(vc_asc))]
        fig = px.bar(vc_asc, orientation="h")
        fig.update_traces(marker_color=bar_colors,
                          hovertemplate="%{y}: %{x} cases<extra></extra>")
        fig.update_layout(showlegend=False, xaxis_title=None, yaxis_title=None)
        st.plotly_chart(spear_fig(fig, height=380, title=t_types),
                        use_container_width=True)

# ---------------- TAB: District Map ----------------
with tab_map:
    per_dist = (f.groupby(["DistrictID", "DistrictName"]).size()
                  .reset_index(name="cases")
                  .merge(profile[["DistrictID", "Population"]], on="DistrictID"))
    per_dist["per_100k"] = (per_dist["cases"] / per_dist["Population"] * 100000).round(1)

    gj, prop = db.load_geojson()
    if gj:
        gj_names = {ft["properties"][prop] for ft in gj["features"]}
        disp = per_dist.copy()
        if "Vijayanagara" not in gj_names and "Vijayanagara" in set(disp.DistrictName):
            vj = disp[disp.DistrictName == "Vijayanagara"]
            disp.loc[disp.DistrictName == "Ballari", ["cases"]] += int(vj["cases"].iloc[0])
            disp = disp[disp.DistrictName != "Vijayanagara"]
            st.caption("Note: Vijayanagara shown merged into Ballari (boundary file predates 2021 split).")
        with st.container(border=True):
            fig = px.choropleth_mapbox(
                disp, geojson=gj, locations="DistrictName",
                featureidkey=f"properties.{prop}", color="per_100k",
                color_continuous_scale=HEAT_SCALE, mapbox_style="carto-darkmatter",
                center={"lat": 14.8, "lon": 75.7}, zoom=5.6, opacity=0.78,
                hover_data={"cases": True, "per_100k": True})
            _t3 = disp.nlargest(3, "per_100k")
            fig.update_layout(title_text=(
                f"{', '.join(_t3.DistrictName.tolist())} carry Karnataka's heaviest "
                f"per-capita load — up to {_t3.per_100k.max():,.0f} cases per 100k"))
            fig.update_layout(height=650,
                              coloraxis_colorbar=dict(
                                  tickfont=dict(color=T["muted"], size=11),
                                  title_font=dict(color=T["muted"], size=11)))
            st.plotly_chart(spear_fig(fig, height=650), use_container_width=True)
    else:
        st.info("No boundary file found (assets/karnataka_districts.geojson) — showing density map.")
        with st.container(border=True):
            fig = px.density_mapbox(f, lat="latitude", lon="longitude", radius=6,
                                    center={"lat": 14.8, "lon": 75.7}, zoom=5.6,
                                    mapbox_style="carto-darkmatter", height=650)
            st.plotly_chart(spear_fig(fig, height=650), use_container_width=True)

    st.subheader("Drill-down: stations in a district")
    pick = st.selectbox("District", sorted(f["DistrictName"].unique()))
    stn = (f[f["DistrictName"] == pick].groupby("Station").size()
             .sort_values(ascending=False).reset_index(name="cases"))
    with st.container(border=True):
        if len(stn):
            _sh = 100 * int(stn.iloc[0]["cases"]) / max(int(stn["cases"].sum()), 1)
            t_stn = (f"{stn.iloc[0]['Station']} alone handles {_sh:.0f}% of "
                     f"{pick}'s caseload ({int(stn.iloc[0]['cases']):,} cases)")
        else:
            t_stn = f"Cases by police station — {pick}"
        # SWD rule 4 — accent the busiest station only
        stn_colors = [SERIES[0] if i == 0 else SLATE for i in range(len(stn))]
        fig = px.bar(stn, x="Station", y="cases")
        fig.update_traces(marker_color=stn_colors)
        fig.update_layout(xaxis_title=None, yaxis_title=None)
        st.plotly_chart(spear_fig(fig, height=360, title=t_stn),
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
        _share = 100 * len(hs) / max(len(f), 1)
        t_hot = (f"DBSCAN isolates {len(summ)} patrol-sized hotspots holding "
                 f"{_share:.0f}% of cases in view — zones, not pixel noise")
        with st.container(border=True):
            fig = px.scatter_mapbox(
                hs, lat="latitude", lon="longitude", color=hs["cluster"].astype(str),
                hover_data=["DistrictName", "CrimeType"], zoom=5.6,
                center={"lat": 14.8, "lon": 75.7}, mapbox_style="carto-darkmatter",
                height=600)
            st.plotly_chart(spear_fig(fig, height=600, title=t_hot),
                            use_container_width=True)
        st.dataframe(summ.rename(columns={
            "cluster": "Hotspot #", "n_cases": "Cases", "district": "District",
            "top_crime": "Dominant crime"}), use_container_width=True, hide_index=True)

# ---------------- TAB: Time Patterns ----------------
with tab_time:
    m = m1.time_heatmap_matrix(f)
    # SWD rule 6 — name the peak window, don't just label the axes
    t_time = "When does crime happen? (day × hour of incident)"
    try:
        total = float(m.values.sum())
        if total > 0:
            peak_day = m.max(axis=1).idxmax()
            peak_hour = int(m.loc[peak_day].idxmax())
            wk = [d for d in m.index if str(d).lower().startswith(("sat", "sun"))]
            eve = [c for c in m.columns if 18 <= int(c) <= 23]
            we = (100 * float(m.loc[wk, eve].values.sum()) / total) if (wk and eve) else 0
            label = sel_type if sel_type != "All" else "Crime"
            t_time = (f"{label} peaks {peak_day} around {peak_hour}:00 — "
                      f"weekend evenings carry {we:.0f}% of all incidents")
    except Exception:
        pass
    with st.container(border=True):
        fig = go.Figure(go.Heatmap(z=m.values, x=list(m.columns), y=list(m.index),
                                   colorscale=HEAT_SCALE,
                                   hovertemplate="%{y} %{x}:00 · %{z} cases<extra></extra>"))
        fig.update_layout(xaxis_title="Hour of day", yaxis_title="", height=450)
        fig.update_yaxes(showgrid=False)
        st.plotly_chart(spear_fig(fig, height=450, title=t_time),
                        use_container_width=True)
    st.caption("Tip: filter to a single crime type in the sidebar — e.g. Chain Snatching "
               "glows on weekend evenings; House Burglary glows at night.")

# ---------------- TAB: Alerts ----------------
with tab_alert:
    z_t = st.slider("Alert threshold (z-score)", 1.5, 4.0, 2.5, 0.1)
    alerts = m1.spike_alerts(cases if sel_head == "All" and sel_type == "All" else f,
                             z_thresh=z_t)
    if alerts.empty:
        st.info("No spikes above threshold in the current view.")
    else:
        st.error(f"{len(alerts)} red-zone spike(s) detected")
        st.dataframe(alerts.rename(columns={
            "DistrictName": "District", "CrimeType": "Crime", "ym": "Month",
            "cases": "Cases", "baseline": "Expected", "z": "Z-score"}),
            use_container_width=True, hide_index=True)
        top = alerts.iloc[0]
        hist = (cases[(cases.DistrictName == top.DistrictName) &
                      (cases.CrimeType == top.CrimeType)]
                .groupby("ym").size().reset_index(name="cases"))
        t_spike = (f"{top.DistrictName}: {top.CrimeType} ran {top.z:.1f}σ above its own "
                   f"baseline in {top.ym} — {int(top.cases)} cases vs ~{top.baseline:.0f} "
                   f"expected")
        with st.container(border=True):
            # SWD rule 4 — ONE accent: the spike month is red, its history is slate
            hist_colors = [T["critical"] if ym == top.ym else SLATE
                           for ym in hist["ym"]]
            fig = px.bar(hist, x="ym", y="cases")
            fig.update_traces(marker_color=hist_colors)
            fig.update_layout(xaxis_title=None, yaxis_title=None)
            st.plotly_chart(spear_fig(fig, height=380, title=t_spike),
                            use_container_width=True)

# ---------------- TAB: Network ----------------
with tab_network:
    render_network_tab(db.DB_PATH)

# ---------------- TAB: Risk ----------------
with tab_risk:
    render_risk_tab(db.DB_PATH, spear_fig, stat_card, HEAT_SCALE)

# ---------------- TAB: Anomalies ----------------
with tab_anom:
    render_anomaly_tab(db.DB_PATH, spear_fig, stat_card)