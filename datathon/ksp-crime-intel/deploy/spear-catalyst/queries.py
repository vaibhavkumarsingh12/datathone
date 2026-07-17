"""
queries.py — every SQL statement SPEAR serves. Standard library only:
no pandas, no numpy, no sklearn. A fresh read-only connection per request
(sqlite3 opens in microseconds and read-only means zero lock contention).
"""
import json, os, sqlite3

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "spear.db")


def conn():
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def rows(sql, args=()):
    with conn() as c:
        return [dict(r) for r in c.execute(sql, args)]


def one(sql, args=()):
    r = rows(sql, args)
    return r[0] if r else {}


# ---------------------------------------------------------------- filters
def _where(f):
    """Build the shared WHERE clause from the global filter dict."""
    sql, args = [], []
    if f.get("head") and f["head"] != "All":
        sql.append("CrimeHead = ?"); args.append(f["head"])
    if f.get("type") and f["type"] != "All":
        sql.append("CrimeType = ?"); args.append(f["type"])
    if f.get("from"):
        sql.append("date >= ?"); args.append(f["from"])
    if f.get("to"):
        sql.append("date <= ?"); args.append(f["to"])
    return (" WHERE " + " AND ".join(sql)) if sql else "", args


# ---------------------------------------------------------------- meta
def meta():
    return {r["key"]: json.loads(r["value"]) for r in rows("SELECT * FROM Meta")}


def filter_options():
    return {
        "heads": [r["CrimeHead"] for r in
                  rows('SELECT DISTINCT CrimeHead FROM "Case" ORDER BY 1')],
        "types": rows('SELECT DISTINCT CrimeHead, CrimeType FROM "Case" ORDER BY 1,2'),
        "date_min": one('SELECT MIN(date) d FROM "Case"')["d"],
        "date_max": one('SELECT MAX(date) d FROM "Case"')["d"],
    }


# ---------------------------------------------------------------- overview
def summary(f):
    w, a = _where(f)
    return one(f'''SELECT COUNT(*) n_cases,
                          COUNT(DISTINCT DistrictName) n_districts,
                          COUNT(DISTINCT Station) n_stations
                   FROM "Case"{w}''', a)


def top_crime(f):
    w, a = _where(f)
    r = rows(f'SELECT CrimeType, COUNT(*) n FROM "Case"{w} '
             f'GROUP BY 1 ORDER BY 2 DESC LIMIT 1', a)
    return r[0]["CrimeType"] if r else "—"


def monthly(f):
    w, a = _where(f)
    return rows(f'SELECT ym, COUNT(*) n FROM "Case"{w} GROUP BY 1 ORDER BY 1', a)


def top_types(f, limit=10):
    w, a = _where(f)
    return rows(f'SELECT CrimeType, COUNT(*) n FROM "Case"{w} '
                f'GROUP BY 1 ORDER BY 2 DESC LIMIT {int(limit)}', a)


# ---------------------------------------------------------------- map
def districts(f):
    w, a = _where(f)
    return rows(f'''SELECT c.DistrictName, c.DistrictID, COUNT(*) n_cases,
                           p.Population,
                           ROUND(COUNT(*) * 100000.0 / p.Population, 1) per_100k
                    FROM "Case" c
                    JOIN DistrictProfile p ON p.DistrictID = c.DistrictID
                    {w.replace("WHERE", "WHERE") if w else ""}
                    GROUP BY 1,2,4 ORDER BY per_100k DESC''', a)


def stations(f, district):
    w, a = _where(f)
    w = (w + " AND " if w else " WHERE ") + "DistrictName = ?"
    return rows(f'SELECT Station, COUNT(*) n FROM "Case"{w} '
                f'GROUP BY 1 ORDER BY 2 DESC', a + [district])


# ---------------------------------------------------------------- hotspots
def hotspot_params():
    return rows("SELECT * FROM HotspotParam ORDER BY scope, eps_km, min_samples")


def hotspots(scope, eps, mins):
    p = one("SELECT param_id FROM HotspotParam "
            "WHERE scope=? AND eps_km=? AND min_samples=?", (scope, eps, mins))
    if not p:
        return {"points": [], "summary": [], "param_id": None}
    pid = p["param_id"]
    return {
        "param_id": pid,
        "points": rows('''SELECT c.latitude, c.longitude, c.DistrictName,
                                 c.CrimeType, h.cluster
                          FROM HotspotAssign h JOIN "Case" c ON c.CaseID = h.CaseID
                          WHERE h.param_id = ?''', (pid,)),
        "summary": rows("SELECT * FROM HotspotSummary WHERE param_id=?", (pid,)),
    }


# ---------------------------------------------------------------- time
def heatmap(f):
    w, a = _where(f)
    return rows(f'SELECT dow, hour, COUNT(*) n FROM "Case"{w} GROUP BY 1,2', a)


# ---------------------------------------------------------------- alerts
def alerts(f, z):
    sql, args = ["z >= ?"], [float(z)]
    if f.get("type") and f["type"] != "All":
        sql.append("CrimeType = ?"); args.append(f["type"])
    return rows("SELECT * FROM Alert WHERE " + " AND ".join(sql) +
                " ORDER BY z DESC", args)


def alert_history(district, crime_type):
    return rows('SELECT ym, COUNT(*) n FROM "Case" '
                'WHERE DistrictName=? AND CrimeType=? GROUP BY 1 ORDER BY 1',
                (district, crime_type))


# ---------------------------------------------------------------- network
def network(min_size=4, community=None):
    ec = ("SELECT EntityID FROM EntityCommunity WHERE CommunitySize >= ?", [int(min_size)])
    if community and community != "All":
        ec = (ec[0] + " AND CommunityID = ?", ec[1] + [int(community)])
    keep = {r["EntityID"] for r in rows(*ec)}
    if not keep:
        return {"nodes": [], "edges": []}
    ph = ",".join("?" * len(keep))
    ids = list(keep)
    edges = rows(f"SELECT EntityA, EntityB, Weight FROM CoOffenseEdge "
                 f"WHERE EntityA IN ({ph}) AND EntityB IN ({ph})", ids + ids)
    used = {e["EntityA"] for e in edges} | {e["EntityB"] for e in edges}
    if not used:
        return {"nodes": [], "edges": []}
    ph2 = ",".join("?" * len(used))
    uid = list(used)
    nodes = rows(f'''SELECT p.EntityID, p.CanonicalName, p.NumCases, p.NumAliases,
                            p.Districts, e.CommunityID, e.Degree, e.Betweenness
                     FROM EntityProfile p JOIN EntityCommunity e USING(EntityID)
                     WHERE p.EntityID IN ({ph2})''', uid)
    return {"nodes": nodes, "edges": edges}


def kingpins(limit=10):
    return rows(f'''SELECT p.CanonicalName, e.CommunityID, p.NumCases, p.NumAliases,
                           p.Districts, e.Degree, e.Betweenness
                    FROM EntityCommunity e JOIN EntityProfile p USING(EntityID)
                    ORDER BY e.Betweenness DESC LIMIT {int(limit)}''')


def communities(min_size=4):
    return rows("SELECT * FROM CommunityProfile WHERE Size >= ? ORDER BY Size DESC",
                (int(min_size),))


def alias_entities(min_aliases=4, limit=10):
    return rows('''SELECT EntityID, CanonicalName, NumAliases, NumCases, AliasList,
                          Districts
                   FROM EntityProfile WHERE NumAliases >= ?
                   ORDER BY NumAliases DESC LIMIT ?''', (int(min_aliases), int(limit)))


def er_counts():
    return {
        "records": one("SELECT COUNT(*) n FROM EntityProfile")["n"],
        "entities": one("SELECT COUNT(*) n FROM EntityProfile")["n"],
        "edges": one("SELECT COUNT(*) n FROM CoOffenseEdge")["n"],
        "rings": one("SELECT COUNT(*) n FROM CommunityProfile WHERE Size >= 4")["n"],
    }


# ---------------------------------------------------------------- module 3: risk
def risk_kpis():
    bt = one("SELECT AVG(hit_rate) hr, AVG(random_expectation) re FROM RiskBacktest")
    hi = one("SELECT COUNT(*) n FROM RiskScore WHERE RiskBand='High'")
    n_months = one("SELECT COUNT(*) n FROM RiskBacktest")
    top = one("SELECT feature FROM RiskFeatureImportance ORDER BY importance DESC LIMIT 1")
    hr = bt.get("hr") or 0
    re = bt.get("re") or 1
    return {
        "hit_rate": hr,
        "n_months": n_months.get("n", 0),
        "lift": (hr / re) if re else 0,
        "high_cells": hi.get("n", 0),
        "top_feature": top.get("feature", "—"),
    }


def risk_months():
    return [r["ym"] for r in rows("SELECT DISTINCT ym FROM RiskScore ORDER BY ym")]


def risk_surface(month):
    """Return the district × crime-type risk_pct grid for one month."""
    r = rows("SELECT DistrictID, CrimeTypeID, risk_pct FROM RiskScore WHERE ym=?", (month,))
    districts = sorted({x["DistrictID"] for x in r})
    types = sorted({x["CrimeTypeID"] for x in r})
    di = {d: i for i, d in enumerate(districts)}
    ti = {t: i for i, t in enumerate(types)}
    z = [[None] * len(types) for _ in districts]
    for x in r:
        z[di[x["DistrictID"]]][ti[x["CrimeTypeID"]]] = round(x["risk_pct"], 4)
    return {"districts": [str(d) for d in districts],
            "types": [str(t) for t in types], "z": z}


def risk_backtest():
    return rows("SELECT ym, hit_rate, baseline_persistence, random_expectation "
                "FROM RiskBacktest ORDER BY ym")


def socio_corr():
    r = rows("SELECT * FROM SocioEconCorr")
    if not r:
        return {"labels": [], "z": []}
    idx_col = list(r[0].keys())[0]                 # 'index'
    labels = [x[idx_col] for x in r]
    z = [[round(x[c], 3) for c in labels] for x in r]
    return {"labels": labels, "z": z}


def socio_regression():
    return rows("SELECT * FROM SocioEconRegression")


# ---------------------------------------------------------------- module 3: anomalies
def anomaly_kpis():
    scored = one("SELECT COUNT(*) n FROM AnomalyScore")
    flagged = one("SELECT COUNT(*) n FROM AnomalyScore WHERE flag=1")
    worst = one("SELECT MAX(z) z FROM CellAnomaly")
    return {"scored": scored.get("n", 0), "flagged": flagged.get("n", 0),
            "worst_z": worst.get("z", 0)}


def case_anomalies(limit=25):
    return rows("SELECT CaseMasterID, DistrictID, CrimeMinorHeadID, ym, "
                "ROUND(anomaly_score,3) anomaly_score, reason "
                "FROM AnomalyScore WHERE flag=1 "
                f"ORDER BY anomaly_score DESC LIMIT {int(limit)}")


def cell_scatter(limit=200):
    return rows("SELECT DistrictID, CrimeMinorHeadID, ym, cases, ROUND(z,2) z "
                f"FROM CellAnomaly ORDER BY z DESC LIMIT {int(limit)}")
