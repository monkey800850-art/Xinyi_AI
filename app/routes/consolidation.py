from flask import Blueprint, render_template

consolidation_bp = Blueprint("consolidation_pages", __name__)


@consolidation_bp.get("/system/consolidation")
def system_consolidation_page():
    return render_template("system_consolidation.html")
