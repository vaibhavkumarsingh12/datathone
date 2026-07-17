"""
main.py — SPEAR on Catalyst AppSail.

Boots in <0.5s (10s AppSail budget). Every route answers in <50ms (30s budget).
Runtime deps: Flask + Waitress only — both pure Python, vendored in ./lib.
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "lib"))      # vendored deps first

from flask import Flask, jsonify, render_template, request   # noqa: E402
import queries as q                                          # noqa: E402

app = Flask(__name__, static_folder="static", template_folder="templates")


def flt():
    return {
        "head": request.args.get("head", "All"),
        "type": request.args.get("type", "All"),
        "from": request.args.get("from"),
        "to":   request.args.get("to"),
    }


# ---------------------------------------------------------------- pages
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/healthz")
def healthz():
    return jsonify(status="ok", cases=q.summary({})["n_cases"])


# ---------------------------------------------------------------- api
@app.route("/api/bootstrap")
def api_bootstrap():
    return jsonify(meta=q.meta(), options=q.filter_options(),
                   hotspot_params=q.hotspot_params())


@app.route("/api/overview")
def api_overview():
    f = flt()
    s = q.summary(f)
    s["top_crime"] = q.top_crime(f)
    return jsonify(summary=s, monthly=q.monthly(f), top_types=q.top_types(f))


@app.route("/api/districts")
def api_districts():
    return jsonify(q.districts(flt()))


@app.route("/api/stations")
def api_stations():
    return jsonify(q.stations(flt(), request.args.get("district", "")))


@app.route("/api/hotspots")
def api_hotspots():
    return jsonify(q.hotspots(request.args.get("scope", "All"),
                              float(request.args.get("eps", 2.0)),
                              int(request.args.get("mins", 25))))


@app.route("/api/heatmap")
def api_heatmap():
    return jsonify(q.heatmap(flt()))


@app.route("/api/alerts")
def api_alerts():
    return jsonify(q.alerts(flt(), request.args.get("z", 2.5)))


@app.route("/api/alert-history")
def api_alert_history():
    return jsonify(q.alert_history(request.args.get("district", ""),
                                   request.args.get("type", "")))


@app.route("/api/network")
def api_network():
    return jsonify(graph=q.network(request.args.get("min_size", 4),
                                   request.args.get("community", "All")),
                   kingpins=q.kingpins(),
                   communities=q.communities(),
                   aliases=q.alias_entities())


@app.route("/api/risk")
def api_risk():
    return jsonify(kpis=q.risk_kpis(), months=q.risk_months(),
                   backtest=q.risk_backtest(),
                   corr=q.socio_corr(), regression=q.socio_regression())


@app.route("/api/risk-surface")
def api_risk_surface():
    return jsonify(q.risk_surface(request.args.get("month", "")))


@app.route("/api/anomalies")
def api_anomalies():
    return jsonify(kpis=q.anomaly_kpis(), cases=q.case_anomalies(),
                   cells=q.cell_scatter())


@app.route("/api/validation")
def api_validation():
    m = q.meta()
    return jsonify({k: v for k, v in m.items() if k.endswith("_metrics")})


# ---------------------------------------------------------------- boot
if __name__ == "__main__":
    port = int(os.getenv("X_ZOHO_CATALYST_LISTEN_PORT", 9000))
    try:
        from waitress import serve
        print(f"SPEAR · waitress on :{port}", flush=True)
        serve(app, host="0.0.0.0", port=port, threads=8)
    except ImportError:
        print(f"SPEAR · flask dev server on :{port}", flush=True)
        app.run(host="0.0.0.0", port=port, threaded=True)
