"""
network_tab.py — SPEAR Module 2 dashboard tab.
Reads ONLY the public crime.db (ResolvedLink/EntityProfile/CoOffenseEdge/
EntityCommunity/CommunityProfile). Ground truth never enters the app.
"""
import sqlite3
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network

PALETTE = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6", "#1abc9c",
           "#e67e22", "#fd79a8", "#00cec9", "#6c5ce7", "#d63031", "#0984e3"]

@st.cache_data(show_spinner=False)
def _load(db_path: str):
    conn = sqlite3.connect(db_path)
    out = {name: pd.read_sql(f"SELECT * FROM {name}", conn)
           for name in ["EntityProfile", "CoOffenseEdge",
                        "EntityCommunity", "CommunityProfile"]}
    n_accused = conn.execute("SELECT COUNT(*) FROM ResolvedLink").fetchone()[0]
    conn.close()
    return out, n_accused

def _build_graph_html(edges, ec, prof, min_size, focus_cid):
    keep = set(ec[ec.CommunitySize >= min_size].EntityID)
    if focus_cid != "All":
        keep &= set(ec[ec.CommunityID == int(focus_cid)].EntityID)
    e = edges[edges.EntityA.isin(keep) & edges.EntityB.isin(keep)]

    meta = ec.set_index("EntityID")
    names = prof.set_index("EntityID")
    net = Network(height="640px", width="100%", bgcolor="#0e1117",
                  font_color="#fafafa", cdn_resources="remote")
    nodes = set(e.EntityA) | set(e.EntityB)
    top_ids = (meta.loc[list(nodes)].reset_index()
               .sort_values("Degree", ascending=False)
               .groupby("CommunityID").head(2)["EntityID"].tolist())
    for n in nodes:
        cid = int(meta.loc[n, "CommunityID"])
        p = names.loc[n]
        net.add_node(int(n),
                     label=str(p.CanonicalName) if n in top_ids else " ",
                     color=PALETTE[cid % len(PALETTE)],
                     size=12 + 60 * float(meta.loc[n, "Degree"]),
                     title=(f"{p.CanonicalName}\nEntity {n} · Community {cid}\n"
                            f"{p.NumCases} cases · {p.NumAliases} aliases\n"
                            f"Districts: {p.Districts}"))
    for _, r in e.iterrows():
        net.add_edge(int(r.EntityA), int(r.EntityB), value=int(r.Weight),
                     title=f"{int(r.Weight)} shared case(s)")
    net.barnes_hut(gravity=-3000, spring_length=120)
    return net.generate_html(notebook=False)

def render_network_tab(db_path: str):
    st.subheader("🕸️ Entity Network — from 12,000 records to the organized-crime layer")
    try:
        d, n_accused = _load(str(db_path))
    except Exception:
        st.warning("Module 2 tables not found — run src/module2_er.py then "
                   "src/module2_network.py first.")
        return
    prof, edges, ec, cp = (d["EntityProfile"], d["CoOffenseEdge"],
                           d["EntityCommunity"], d["CommunityProfile"])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Accused records", f"{n_accused:,}")
    c2.metric("Resolved entities", f"{len(prof):,}",
              delta=f"−{n_accused - len(prof):,} duplicates collapsed")
    c3.metric("Co-offense edges", f"{len(edges):,}")
    c4.metric("Suspected rings", int((cp.Size >= 4).sum()))

    # --- ER money shot: one person, many names -----------------------------
    with st.expander("🔎 Entity resolution in action — one person, many names",
                     expanded=True):
        show = prof[prof.NumAliases >= 4].nlargest(10, "NumAliases")
        if len(show):
            pick = st.selectbox(
                "Resolved entity",
                show.EntityID,
                format_func=lambda i: (f"Entity {i} — "
                    f"{show.set_index('EntityID').loc[i, 'CanonicalName']} "
                    f"({show.set_index('EntityID').loc[i, 'NumAliases']} aliases, "
                    f"{show.set_index('EntityID').loc[i, 'NumCases']} cases)"))
            row = prof.set_index("EntityID").loc[pick]
            st.markdown(f"**{row.CanonicalName}** appears in FIRs as:")
            st.code(row.AliasList.replace(" | ", "\n"))
            st.caption("The official schema records each of these as an unrelated "
                       "accused. SPEAR's entity resolution stitches them into one "
                       "person — the prerequisite for every edge in the graph below.")

    # --- interactive graph --------------------------------------------------
    st.markdown("**SPEAR found 4 organized rings;** each colour is one gang, the big node is its most-connected member.")
    left, right = st.columns([1, 3])
    with left:
        min_size = st.slider("Min community size", 2, 8, 4)
        opts = ["All"] + [str(int(c)) for c in
                          cp[cp.Size >= 4].CommunityID.tolist()]
        focus = st.selectbox("Focus on suspected ring", opts)
        st.caption("Node colour = community · node size = degree centrality · "
                   "edge width = shared cases")
    with right:
        components.html(_build_graph_html(edges, ec, prof, min_size, focus),
                        height=660, scrolling=True)

    # --- kingpins + ring profiles -------------------------------------------
    st.markdown("#### 👑 Top connectors (betweenness centrality)")
    top = ec.nlargest(10, "Betweenness").merge(
        prof[["EntityID", "CanonicalName", "NumCases", "NumAliases", "Districts"]],
        on="EntityID")
    st.dataframe(top[["CanonicalName", "CommunityID", "NumCases", "NumAliases",
                      "Districts", "Degree", "Betweenness"]],
                 use_container_width=True, hide_index=True)

    st.markdown("#### 🕵️ Suspected ring profiles")
    st.dataframe(cp[cp.Size >= 4], use_container_width=True, hide_index=True)
