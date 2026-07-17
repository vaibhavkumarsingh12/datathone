"""
module2_network.py — SPEAR Module 2 · Phase 2: co-offense graph + Louvain + centrality
Reads: crime.db (Accused, CaseMaster, ResolvedLink, EntityProfile) — PUBLIC only.
Run:   python src/module2_network.py        (fast — the graph is small)
"""
from pathlib import Path
from collections import defaultdict, Counter
import sqlite3
import pandas as pd
import networkx as nx
from networkx.algorithms.community import louvain_communities

DB_PATH = Path("data/output/crime.db")
COLS = dict(accused_id="AccusedMasterID", case_id="CaseMasterID",
            subhead="CrimeMinorHeadID", district="DistrictID")
MIN_RING_SIZE = 4        # a "suspected ring" = community with ≥4 entities
SEED = 42                # Louvain is stochastic — seed it for reproducible demos

def try_subhead_names(conn):
    """Best-effort lookup CrimeMinorHeadID → readable name; falls back to IDs."""
    try:
        t = pd.read_sql("SELECT * FROM CrimeSubHead", conn)
        idc  = next(c for c in t.columns if c.lower().endswith("id"))
        namec = next(c for c in t.columns
                     if c != idc and t[c].dtype == object)
        return dict(zip(t[idc], t[namec]))
    except Exception:
        return {}

def main():
    conn = sqlite3.connect(DB_PATH)
    link = pd.read_sql("SELECT * FROM ResolvedLink", conn)
    acc  = pd.read_sql(f"SELECT {COLS['accused_id']}, {COLS['case_id']} FROM Accused", conn)
    cm   = pd.read_sql(f"SELECT c.{COLS['case_id']}, c.{COLS['subhead']}, "
                       f"u.DistrictID as {COLS['district']} FROM CaseMaster c "
                       f"LEFT JOIN Unit u ON c.PoliceStationID = u.UnitID", conn)
    df = acc.merge(link, on=COLS["accused_id"]).merge(cm, on=COLS["case_id"])
    sub_names = try_subhead_names(conn)

    # ---- edges: all entity pairs co-accused on the same case ----
    w = defaultdict(int)
    for _, g in df.groupby(COLS["case_id"]):
        ents = sorted(g["EntityID"].unique())
        for i in range(len(ents)):
            for j in range(i + 1, len(ents)):
                w[(ents[i], ents[j])] += 1

    G = nx.Graph()
    for (a, b), wt in w.items():
        G.add_edge(a, b, weight=wt)
    print(f"Graph: {G.number_of_nodes()} entities, {G.number_of_edges()} co-offense edges, "
          f"{nx.number_connected_components(G)} components.")

    # ---- Louvain communities (seeded) ----
    comms = louvain_communities(G, weight="weight", seed=SEED)
    comm_of = {n: cid for cid, c in enumerate(comms, start=1) for n in c}
    sizes = {cid: len(c) for cid, c in enumerate(comms, start=1)}

    # ---- centrality ----
    deg = nx.degree_centrality(G)
    btw = nx.betweenness_centrality(G, weight=None, seed=SEED)

    ec = pd.DataFrame({
        "EntityID":      list(G.nodes),
        "CommunityID":   [comm_of[n] for n in G.nodes],
        "CommunitySize": [sizes[comm_of[n]] for n in G.nodes],
        "Degree":        [round(deg[n], 4) for n in G.nodes],
        "Betweenness":   [round(btw[n], 4) for n in G.nodes],
    })
    edges = pd.DataFrame([(a, b, wt) for (a, b), wt in w.items()],
                         columns=["EntityA", "EntityB", "Weight"])

    # ---- community profiles (crime-type mix + districts, from entities' cases) ----
    df["CommunityID"] = df["EntityID"].map(comm_of)
    rows = []
    for cid, g in df.dropna(subset=["CommunityID"]).groupby("CommunityID"):
        top = Counter(g[COLS["subhead"]]).most_common(3)
        rows.append({
            "CommunityID": int(cid), "Size": sizes[int(cid)],
            "TotalCases": g[COLS["case_id"]].nunique(),
            "TopCrimeTypes": "; ".join(f"{sub_names.get(k, k)} ({v})" for k, v in top),
            "Districts": ",".join(str(int(d)) for d in
                                  sorted(g[COLS["district"]].dropna().unique())),
        })
    cp = pd.DataFrame(rows).sort_values("Size", ascending=False)

    edges.to_sql("CoOffenseEdge", conn, if_exists="replace", index=False)
    ec.to_sql("EntityCommunity", conn, if_exists="replace", index=False)
    cp.to_sql("CommunityProfile", conn, if_exists="replace", index=False)

    rings = cp[cp.Size >= MIN_RING_SIZE]
    print(f"\nCommunities: {len(comms)} total → {len(rings)} suspected rings (size ≥{MIN_RING_SIZE}):")
    print(rings.to_string(index=False))

    prof = pd.read_sql("SELECT EntityID, CanonicalName, NumCases FROM EntityProfile", conn)
    top10 = ec.nlargest(10, "Betweenness").merge(prof, on="EntityID")
    print("\nTop-10 connectors (betweenness) — likely kingpins/brokers:")
    print(top10[["EntityID", "CanonicalName", "CommunityID", "NumCases",
                 "Degree", "Betweenness"]].to_string(index=False))
    conn.close()

if __name__ == "__main__":
    main()
