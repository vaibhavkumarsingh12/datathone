"""
deploy/verify_build.py — deployment exam. Run BEFORE every upload.
Run from repo root:  python deploy/verify_build.py
"""
import json, os, sqlite3, subprocess, sys, time
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
APP  = ROOT / "deploy" / "spear-catalyst"
DB   = APP / "data" / "spear.db"

results = []
def check(name, ok, detail):
    results.append(ok)
    print(f"{'✅ PASS' if ok else '❌ FAIL'} {name} → {detail}")

# ---- D1 · structure ---------------------------------------------------------
need = ["main.py", "queries.py", "app-config.json", "templates/index.html",
        "static/css/spear.css", "static/js/spear.js", "static/js/plotly.min.js",
        "static/js/vis-network.min.js", "data/spear.db", "lib"]
missing = [f for f in need if not (APP / f).exists()]
check("D1 · Build structure", not missing,
      "all required files present" if not missing else f"missing {missing}")

# ---- D2 · no Windows binaries ----------------------------------------------
bad = list((APP/"lib").rglob("*.pyd")) + list((APP/"lib").rglob("*.dll"))
check("D2 · Linux-clean vendored deps", not bad,
      "no .pyd/.dll in lib/" if not bad else f"{len(bad)} Windows binaries — rerun vendor.py")

# ---- D3 · no science stack at runtime --------------------------------------
banned = {"pandas", "numpy", "sklearn", "scipy", "plotly", "networkx",
          "statsmodels", "pyvis", "rapidfuzz", "streamlit", "pygwalker"}
src = (APP/"main.py").read_text(encoding='utf-8') + (APP/"queries.py").read_text(encoding='utf-8')
leaked = sorted(b for b in banned if f"import {b}" in src)
present = sorted(b for b in banned if (APP/"lib"/b).exists())
check("D3 · Runtime is stdlib + Flask only", not leaked and not present,
      "no heavy imports, no heavy packages vendored"
      if not (leaked or present) else f"imports={leaked} vendored={present}")

# ---- D4 · app-config sanity -------------------------------------------------
cfg = json.loads((APP/"app-config.json").read_text(encoding='utf-8'))
ok4 = ("python" in cfg.get("stack","").lower() and "3" in cfg.get("stack","")
       and "main.py" in cfg.get("command",""))
check("D4 · app-config.json", ok4,
      f"stack={cfg.get('stack')} command={cfg.get('command')!r} memory={cfg.get('memory')}")

# ---- D5 · disk budget -------------------------------------------------------
size = sum(f.stat().st_size for f in APP.rglob("*") if f.is_file()) / 1e6
check("D5 · Build size under disk budget", size < 200,
      f"{size:.1f} MB (256 MB default disk; raise in console if >200)")

# ---- D6 · db integrity + required tables -----------------------------------
conn = sqlite3.connect(DB)
try:
    have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
except sqlite3.OperationalError:
    have = set()
req = {"Case","DistrictProfile","HotspotParam","HotspotSummary","HotspotAssign",
       "Alert","EntityProfile","CoOffenseEdge","EntityCommunity","CommunityProfile","Meta"}
miss = req - have
try:
    cases = conn.execute('SELECT COUNT(*) FROM "Case"').fetchone()[0]
except:
    cases = 0
check("D6 · spear.db complete", not miss,
      f"{len(have)} tables, {cases} cases"
      if not miss else f"missing tables {sorted(miss)}")

# ---- D7 · cold boot inside 10s ---------------------------------------------
env = dict(os.environ, X_ZOHO_CATALYST_LISTEN_PORT="9137")
p = subprocess.Popen([sys.executable, "-u", "main.py"], cwd=APP, env=env,
                     stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
t0, booted = time.time(), False
while time.time() - t0 < 10:
    try:
        urlopen("http://127.0.0.1:9137/healthz", timeout=1).read()
        booted = True; break
    except Exception:
        time.sleep(0.2)
boot_t = time.time() - t0

# ---- D8 · every route inside 30s (and honestly, 200ms) ---------------------
routes, slow = ["/", "/healthz", "/api/bootstrap", "/api/overview", "/api/districts",
                "/api/hotspots?scope=All&eps=2.0&mins=25", "/api/heatmap",
                "/api/alerts?z=2.5", "/api/network?min_size=4", "/api/risk",
                "/api/anomalies", "/api/validation"], []
if booted:
    for r in routes:
        t = time.time()
        try:
            urlopen("http://127.0.0.1:9137" + r, timeout=30).read()
            ms = (time.time()-t)*1000
            if ms > 1000: slow.append(f"{r} {ms:.0f}ms")
        except Exception as e:
            slow.append(f"{r} ERROR {e}")
p.terminate()

check("D7 · Cold boot under 10s (AppSail hard limit)", booted,
      f"listening in {boot_t:.2f}s" if booted else "never bound the port in 10s")
check("D8 · All routes fast and healthy", booted and not slow,
      f"{len(routes)} routes OK, all under 1s" if booted and not slow
      else f"problems: {slow}")

print(f"\nDEPLOY SCORECARD: {sum(results)}/{len(results)} passed"
      + (" 🎉 SAFE TO UPLOAD" if all(results) else " — fix ❌ before deploying"))
sys.exit(0 if all(results) else 1)
