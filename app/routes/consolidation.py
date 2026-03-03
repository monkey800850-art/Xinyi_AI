from flask import Blueprint, jsonify, render_template, request

from app.services.consolidation_query_service import ConsolidationQueryService

consolidation_bp = Blueprint("consolidation_pages", __name__)
consolidation_query_service = ConsolidationQueryService()


@consolidation_bp.get("/system/consolidation")
def system_consolidation_page():
    return render_template("system_consolidation.html")


@consolidation_bp.get("/consolidation/consolidated-data")
def consolidated_data():
    limit = request.args.get("limit", 20)
    try:
        payload = consolidation_query_service.get_consolidated_data(limit=int(limit))
        return jsonify({"status": "ok", **payload}), 200
    except Exception as err:
        return jsonify({"error": str(err)}), 400
