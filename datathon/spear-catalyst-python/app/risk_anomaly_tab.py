"""
risk_anomaly_tab.py — SPEAR Module 3 dashboard tabs.
Reads ONLY public crime.db tables written by module3_risk / module3_anomaly.
"""
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

@st.cache_data(show_spinner=False)
def _load(db_path: str):
    conn = sqlite3.connect(db_path)
    d = {}
    for t in ["RiskScore", "RiskBacktest", "RiskFeatureImportance",
              "AnomalyScore", "CellAnomaly", "SocioEconCorr", "SocioEconRegression"]:
        try:
            d[t] = pd.read_sql(f"SELECT * FROM {t}", conn)
        except Exception:
            d[t] = None
    # readable names if lookup tables exist
    for t, key in [("DistrictMaster", "district"), ("CrimeSubHead", "subhead")]:
        try:
            d[t] = pd.read_sql(f"SELECT * FROM {t}", conn)
        except Exception:
            d[t] = None
    conn.close()
    return d

def render_risk_tab(db_path, spear_fig, stat_card, heat_scale):
    st.subheader("🎯 Predictive Risk — where should patrols be next month?")
    d = _load(str(db_path))
    if d["RiskScore"] is None:
        st.warning("Run src/module3_risk.py first."); return
    rs, bt, fi = d["RiskScore"], d["RiskBacktest"], d["RiskFeatureImportance"]

    c1, c2, c3, c4 = st.columns(4)
    stat_card(c1, "Backtest hit-rate", f"{bt.hit_rate.mean():.0%}",
              f"top-20 cells · {len(bt)} held-out months", "#4C87D8")
    stat_card(c2, "vs random patrols", f"{bt.hit_rate.mean()/bt.random_expectation.mean():.0f}×",
              "lift over chance", "#57C58C")
    stat_card(c3, "High-risk cells", f"{(rs.RiskBand=='High').sum():,}",
              "top decile each month", "#EC7468")
    stat_card(c4, "Top signal", fi.iloc[0]["feature"],
              "strongest predictor", "#E3B94A")

    months = sorted(rs.ym.unique())
    pick = st.selectbox("Month", months, index=len(months)-1)
    mth = rs[rs.ym == pick]
    piv = mth.pivot_table(index="DistrictID", columns="CrimeTypeID",
                          values="risk_pct", aggfunc="first")
    with st.container(border=True):
        fig = go.Figure(go.Heatmap(z=piv.values, x=[str(c) for c in piv.columns],
                                   y=[str(i) for i in piv.index],
                                   colorscale=heat_scale,
                                   hovertemplate="District %{y} · Type %{x} · "
                                                 "risk %{z:.0%}<extra></extra>"))
        st.plotly_chart(spear_fig(fig, height=560,
                        title=f"Risk surface — {pick} (district × crime type)"),
                        use_container_width=True)

    with st.container(border=True):
        fig = px.line(bt, x="ym", y=["hit_rate", "baseline_persistence",
                                     "random_expectation"], markers=True)
        st.plotly_chart(spear_fig(fig, height=340,
                        title="Backtest: model vs persistence vs random"),
                        use_container_width=True)

    st.markdown("#### 📚 The why behind the where — socio-economic drivers")
    l, r = st.columns(2)
    if d["SocioEconCorr"] is not None:
        with l, st.container(border=True):
            corr = d["SocioEconCorr"].set_index(d["SocioEconCorr"].columns[0])
            fig = px.imshow(corr, text_auto=True, color_continuous_scale=heat_scale)
            st.plotly_chart(spear_fig(fig, height=340,
                            title="Correlation matrix"), use_container_width=True)
    if d["SocioEconRegression"] is not None:
        with r:
            st.dataframe(d["SocioEconRegression"], use_container_width=True,
                         hide_index=True)
            st.caption("OLS: crime per 100k on district covariates. "
                       "Literacy's negative, significant coefficient is the "
                       "'why' the risk model quietly uses.")

def render_anomaly_tab(db_path, spear_fig, stat_card):
    st.subheader("🚨 Anomalies — the incidents that don't fit")
    d = _load(str(db_path))
    if d["AnomalyScore"] is None:
        st.warning("Run src/module3_anomaly.py first."); return
    a, cell = d["AnomalyScore"], d["CellAnomaly"]

    c1, c2, c3 = st.columns(3)
    stat_card(c1, "Cases scored", f"{len(a):,}", "IsolationForest", "#4C87D8")
    stat_card(c2, "Flagged for review", f"{int(a.flag.sum()):,}",
              "1% triage budget", "#EC7468")
    stat_card(c3, "Worst volume spike", f"z = {cell.z.max():.1f}",
              "district×type×month", "#E3B94A")

    st.markdown("#### Case-level: top anomalous incidents (with reasons)")
    st.dataframe(a[a.flag == 1].nlargest(25, "anomaly_score"),
                 use_container_width=True, hide_index=True)

    st.markdown("#### Cell-level: volume anomalies over time")
    hot = cell.nlargest(200, "z")
    with st.container(border=True):
        fig = px.scatter(hot, x="ym", y="z", color="DistrictID",
                         hover_data=[cell.columns[1]])
        fig.add_hline(y=2.5, line_dash="dash", line_color="#EC7468")
        st.plotly_chart(spear_fig(fig, height=380,
                        title="Highest-z cells (dashed line = alert threshold)"),
                        use_container_width=True)
    st.caption("Every point above the line is a month where a district×crime cell "
               "erupted beyond its own history — the continuous version of the "
               "Module 1 alert system.")
