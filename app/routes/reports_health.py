from flask import Blueprint, jsonify

bp_reports_health = Blueprint("bp_reports_health", __name__)

@bp_reports_health.get("/api/reports/health")
def reports_health():
    """
    REPORTS-QUERY-14A
    Minimal health endpoint for reports subsystem.
    Used for smoke test + UI wiring without touching business logic.
    """
    return jsonify({
        "ok": True,
        "module": "reports",
        "version": "rq14a"
    })
