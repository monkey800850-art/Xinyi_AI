import io
import sys

from flask import Flask, jsonify, render_template, request, send_file

from app.config import DatabaseConfigError, load_env
from app.db import test_db_connection
from app.services.ar_ap_service import ArApError, get_aging_report, get_due_warnings, get_warning_summary
from app.services.asset_service import (
    AssetError,
    create_asset,
    create_category,
    get_asset_detail,
    list_assets,
    list_categories,
    set_asset_enabled,
    set_category_enabled,
    update_asset,
    update_category,
)
from app.services.aux_reports_service import AuxReportError, get_aux_balance, get_aux_ledger
from app.services.autocomplete_service import AutocompleteError, autocomplete
from app.services.bank_import_service import BankImportError, import_bank_transactions, list_bank_transactions
from app.services.bank_reconcile_service import (
    ReconcileError,
    auto_match,
    cancel_match,
    confirm_match,
    get_reconcile_report,
    list_reconciliation_items,
)
from app.services.book_service import BookCreateError, create_book_with_subject_init
from app.services.dashboard_service import DashboardError, get_boss_metrics, get_workbench_metrics
from app.services.depreciation_service import (
    DepreciationError,
    get_batch_detail,
    list_batches,
    preview_depreciation,
    run_depreciation,
)
from app.services.asset_change_service import AssetChangeError, create_change, list_changes
from app.services.asset_reports_service import (
    AssetReportError,
    get_asset_ledger,
    get_depreciation_detail,
    get_depreciation_summary,
)
from app.services.export_service import ExportError, export_report
from app.services.audit_service import log_audit
from app.services.system_service import (
    SystemError,
    create_or_update_role,
    create_or_update_user,
    list_audit_logs,
    list_roles,
    list_rules,
    list_users,
    set_role_permissions,
    set_user_enabled,
    set_user_roles,
    upsert_rule,
)
from app.services.ledger_service import LedgerError, get_subject_ledger, get_voucher_detail
from app.services.payment_service import (
    PaymentError,
    approve_payment,
    create_or_update_payment,
    execute_payment,
    get_payment_detail,
    list_payments,
    reject_payment,
    submit_payment,
)
from app.services.reimbursement_service import (
    ReimbursementError,
    approve_reimbursement,
    create_or_update_reimbursement,
    get_reimbursement_detail,
    get_reimbursement_stats,
    list_reimbursements,
    reject_reimbursement,
    submit_reimbursement,
)
from app.services.tax_service import (
    TaxError,
    build_tax_alerts,
    create_tax_rule,
    get_tax_summary,
    import_invoices,
    list_invoices,
    list_tax_alerts,
    list_tax_rules,
    validate_tax,
)
from app.services.trial_balance_service import TrialBalanceError, get_trial_balance
from app.services.voucher_service import VoucherValidationError, save_voucher
from app.services.voucher_status_service import VoucherStatusError, change_voucher_status


def _get_operator_from_headers():
    operator = request.headers.get("X-User", "").strip()
    role = request.headers.get("X-Role", "").strip()
    return operator, role


def create_app() -> Flask:
    load_env()

    try:
        host, port, name = test_db_connection()
        print(f"Database connection ok: host={host}, port={port}, db_name={name}")
    except DatabaseConfigError as err:
        print(str(err), file=sys.stderr)
        sys.exit(1)
    except Exception as err:
        print(str(err), file=sys.stderr)
        sys.exit(1)

    app = Flask(__name__)

    @app.get("/")
    def health():
        return {"status": "ok"}

    @app.get("/dashboard")
    def dashboard_page():
        return render_template("dashboard.html")

    @app.get("/dashboard/boss")
    def boss_dashboard_page():
        return render_template("boss_dashboard.html")

    @app.get("/demo/autocomplete")
    def demo_autocomplete():
        return render_template("demo_autocomplete.html")

    @app.get("/demo/filters")
    def demo_filters():
        return render_template("autocomplete_filters.html")

    @app.get("/voucher/entry")
    def voucher_entry():
        return render_template("voucher_entry.html")

    @app.get("/reports/trial_balance")
    def trial_balance_page():
        return render_template("trial_balance.html")

    @app.get("/reports/subject_ledger")
    def subject_ledger_page():
        return render_template("subject_ledger.html")

    @app.get("/reports/aux_reports")
    def aux_reports_page():
        return render_template("aux_reports.html")

    @app.get("/reports/ar_ap")
    def ar_ap_page():
        return render_template("ar_ap_aging.html")

    @app.get("/reimbursements")
    def reimbursements_list_page():
        return render_template("reimbursements_list.html")

    @app.get("/reimbursements/new")
    def reimbursements_new_page():
        return render_template("reimbursements_detail.html", reimbursement_id="")

    @app.get("/reimbursements/<int:reimbursement_id>")
    def reimbursements_detail_page(reimbursement_id: int):
        return render_template(
            "reimbursements_detail.html", reimbursement_id=reimbursement_id
        )

    @app.get("/payments")
    def payments_list_page():
        return render_template("payments_list.html")

    @app.get("/payments/new")
    def payments_new_page():
        return render_template("payments_detail.html", payment_id="")

    @app.get("/payments/<int:payment_id>")
    def payments_detail_page(payment_id: int):
        return render_template("payments_detail.html", payment_id=payment_id)

    @app.get("/banks/import")
    def bank_import_page():
        return render_template("bank_import.html")

    @app.get("/banks/reconcile")
    def bank_reconcile_page():
        return render_template("bank_reconcile.html")

    @app.get("/tax/rules")
    def tax_rules_page():
        return render_template("tax_rules.html")

    @app.get("/tax/invoices")
    def tax_invoices_page():
        return render_template("tax_invoices.html")

    @app.get("/tax/summary")
    def tax_summary_page():
        return render_template("tax_summary.html")

    @app.get("/assets/categories")
    def asset_categories_page():
        return render_template("asset_categories.html")

    @app.get("/assets/depreciation")
    def asset_depreciation_page():
        return render_template("asset_depreciation.html")

    @app.get("/assets/changes")
    def asset_changes_page():
        return render_template("asset_changes.html")

    @app.get("/assets/reports/ledger")
    def asset_ledger_page():
        return render_template("asset_ledger.html")

    @app.get("/assets/reports/depreciation")
    def asset_depreciation_report_page():
        return render_template("asset_depreciation_reports.html")

    @app.get("/system/users")
    def system_users_page():
        return render_template("system_users.html")

    @app.get("/system/roles")
    def system_roles_page():
        return render_template("system_roles.html")

    @app.get("/system/rules")
    def system_rules_page():
        return render_template("system_rules.html")

    @app.get("/system/audit")
    def system_audit_page():
        return render_template("audit_logs.html")

    @app.get("/assets")
    def assets_list_page():
        return render_template("assets_list.html")

    @app.get("/assets/new")
    def assets_new_page():
        return render_template("assets_detail.html", asset_id="")

    @app.get("/assets/<int:asset_id>")
    def assets_detail_page(asset_id: int):
        return render_template("assets_detail.html", asset_id=asset_id)

    @app.post("/books")
    def create_book():
        payload = request.get_json(silent=True) or {}
        try:
            result = create_book_with_subject_init(payload)
            return jsonify(result), 201
        except BookCreateError as err:
            app.logger.error("book_create_error: %s", err)
            return jsonify({"error": str(err)}), 400
        except Exception as err:
            app.logger.exception("book_create_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.get("/api/dashboard/workbench")
    def api_dashboard_workbench():
        try:
            result = get_workbench_metrics(request.args)
            return jsonify(result), 200
        except DashboardError as err:
            return jsonify({"error": str(err)}), 400

    @app.get("/api/dashboard/boss")
    def api_dashboard_boss():
        role = request.headers.get("X-Role", "").strip()
        if role not in ("boss", "admin"):
            return jsonify({"error": "forbidden"}), 403
        try:
            result = get_boss_metrics(request.args)
            return jsonify(result), 200
        except DashboardError as err:
            return jsonify({"error": str(err)}), 400

    @app.get("/api/autocomplete")
    def api_autocomplete():
        try:
            result = autocomplete(request.args)
            return jsonify({"items": result}), 200
        except AutocompleteError as err:
            app.logger.error("autocomplete_error: %s", err)
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("autocomplete_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.get("/api/trial_balance")
    def api_trial_balance():
        try:
            result = get_trial_balance(request.args)
            return jsonify(result), 200
        except TrialBalanceError as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("trial_balance_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.get("/api/subject_ledger")
    def api_subject_ledger():
        try:
            result = get_subject_ledger(request.args)
            return jsonify(result), 200
        except LedgerError as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("subject_ledger_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.get("/api/aux_balance")
    def api_aux_balance():
        try:
            result = get_aux_balance(request.args)
            return jsonify(result), 200
        except AuxReportError as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("aux_balance_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.get("/api/aux_ledger")
    def api_aux_ledger():
        try:
            result = get_aux_ledger(request.args)
            return jsonify(result), 200
        except AuxReportError as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("aux_ledger_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.get("/api/ar_ap/summary")
    def api_ar_ap_summary():
        try:
            result = get_warning_summary(request.args)
            return jsonify(result), 200
        except ArApError as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("ar_ap_summary_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.get("/api/ar_ap/warnings")
    def api_ar_ap_warnings():
        try:
            result = get_due_warnings(request.args)
            return jsonify(result), 200
        except ArApError as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("ar_ap_warnings_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.get("/api/ar_ap/aging")
    def api_ar_ap_aging():
        try:
            result = get_aging_report(request.args)
            return jsonify(result), 200
        except ArApError as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("ar_ap_aging_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.get("/api/assets/categories")
    def api_asset_categories():
        try:
            result = list_categories(request.args)
            return jsonify(result), 200
        except AssetError as err:
            return jsonify({"error": str(err)}), 400

    @app.post("/api/assets/categories")
    def api_asset_categories_create():
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        try:
            result = create_category(payload)
            log_audit("asset", "category_create", "asset_category", result.get("id"), operator, role, payload)
            return jsonify(result), 201
        except AssetError as err:
            return jsonify({"error": str(err)}), 400

    @app.post("/api/assets/categories/<int:category_id>")
    def api_asset_categories_update(category_id: int):
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        try:
            result = update_category(category_id, payload)
            log_audit("asset", "category_update", "asset_category", category_id, operator, role, payload)
            return jsonify(result), 200
        except AssetError as err:
            return jsonify({"error": str(err)}), 400

    @app.post("/api/assets/categories/<int:category_id>/enabled")
    def api_asset_categories_enabled(category_id: int):
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        try:
            result = set_category_enabled(category_id, int(payload.get("is_enabled", 1)))
            log_audit(
                "asset",
                "category_enabled",
                "asset_category",
                category_id,
                operator,
                role,
                {"is_enabled": payload.get("is_enabled", 1)},
            )
            return jsonify(result), 200
        except AssetError as err:
            return jsonify({"error": str(err)}), 400

    @app.get("/api/assets")
    def api_assets_list():
        try:
            result = list_assets(request.args)
            return jsonify(result), 200
        except AssetError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.get("/api/assets/<int:asset_id>")
    def api_assets_detail(asset_id: int):
        try:
            result = get_asset_detail(asset_id)
            return jsonify(result), 200
        except AssetError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.post("/api/assets")
    def api_assets_create():
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        try:
            result = create_asset(payload)
            log_audit("asset", "asset_create", "fixed_asset", result.get("id"), operator, role, payload)
            return jsonify(result), 201
        except AssetError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.post("/api/assets/<int:asset_id>")
    def api_assets_update(asset_id: int):
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        try:
            result = update_asset(asset_id, payload)
            log_audit("asset", "asset_update", "fixed_asset", asset_id, operator, role, payload)
            return jsonify(result), 200
        except AssetError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.post("/api/assets/<int:asset_id>/enabled")
    def api_assets_enabled(asset_id: int):
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        try:
            result = set_asset_enabled(asset_id, int(payload.get("is_enabled", 1)))
            log_audit(
                "asset",
                "asset_enabled",
                "fixed_asset",
                asset_id,
                operator,
                role,
                {"is_enabled": payload.get("is_enabled", 1)},
            )
            return jsonify(result), 200
        except AssetError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.get("/api/assets/depreciation/preview")
    def api_depreciation_preview():
        try:
            result = preview_depreciation(request.args)
            return jsonify(result), 200
        except DepreciationError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.post("/api/assets/depreciation")
    def api_depreciation_run():
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        payload["operator"] = operator
        payload["operator_role"] = role
        try:
            result = run_depreciation(payload)
            return jsonify(result), 201
        except DepreciationError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.get("/api/assets/depreciation")
    def api_depreciation_batches():
        try:
            result = list_batches(request.args)
            return jsonify(result), 200
        except DepreciationError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.get("/api/assets/depreciation/<int:batch_id>")
    def api_depreciation_detail(batch_id: int):
        try:
            result = get_batch_detail(batch_id)
            return jsonify(result), 200
        except DepreciationError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.post("/api/assets/<int:asset_id>/change")
    def api_asset_change(asset_id: int):
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        payload["operator"] = operator
        try:
            result = create_change(asset_id, payload)
            log_audit(
                "asset",
                f"asset_{payload.get('change_type', '').lower()}",
                "fixed_asset",
                asset_id,
                operator,
                role,
                payload,
            )
            return jsonify(result), 200
        except AssetChangeError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.get("/api/assets/changes")
    def api_asset_changes_list():
        try:
            result = list_changes(request.args)
            return jsonify(result), 200
        except AssetChangeError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.get("/api/assets/ledger")
    def api_asset_ledger():
        try:
            result = get_asset_ledger(request.args)
            return jsonify(result), 200
        except AssetReportError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.get("/api/assets/depreciation/detail")
    def api_asset_depreciation_detail():
        try:
            result = get_depreciation_detail(request.args)
            return jsonify(result), 200
        except AssetReportError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.get("/api/assets/depreciation/summary")
    def api_asset_depreciation_summary():
        try:
            result = get_depreciation_summary(request.args)
            return jsonify(result), 200
        except AssetReportError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.get("/api/exports/<report_key>")
    def api_export_report(report_key: str):
        operator, _ = _get_operator_from_headers()
        try:
            content, file_name = export_report(report_key, request.args, operator)
            return send_file(
                io.BytesIO(content),
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name=file_name,
            )
        except ExportError as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("export_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.get("/api/exports/assets/<report_key>")
    def api_export_asset_report(report_key: str):
        operator, _ = _get_operator_from_headers()
        report_map = {
            "ledger": "asset_ledger",
            "depreciation_detail": "asset_depreciation_detail",
            "depreciation_summary": "asset_depreciation_summary",
        }
        mapped = report_map.get(report_key)
        if not mapped:
            return jsonify({"error": "unsupported_report"}), 400
        try:
            content, file_name = export_report(mapped, request.args, operator)
            return send_file(
                io.BytesIO(content),
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name=file_name,
            )
        except ExportError as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("export_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.post("/api/auth/login")
    def api_auth_login():
        payload = request.get_json(silent=True) or {}
        username = payload.get("username") or ""
        operator = (payload.get("operator") or username or "").strip()
        role = (payload.get("role") or "").strip()
        log_audit("auth", "login", "user", None, operator, role, {"username": username})
        return jsonify({"status": "ok"}), 200

    @app.post("/api/auth/logout")
    def api_auth_logout():
        payload = request.get_json(silent=True) or {}
        username = payload.get("username") or ""
        operator = (payload.get("operator") or username or "").strip()
        role = (payload.get("role") or "").strip()
        log_audit("auth", "logout", "user", None, operator, role, {"username": username})
        return jsonify({"status": "ok"}), 200

    @app.get("/api/system/users")
    def api_system_users():
        try:
            result = list_users(request.args)
            return jsonify(result), 200
        except SystemError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.post("/api/system/users")
    def api_system_users_save():
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        try:
            result = create_or_update_user(payload, operator, role)
            return jsonify(result), 200
        except SystemError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.post("/api/system/users/<int:user_id>/enabled")
    def api_system_user_enabled(user_id: int):
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        try:
            result = set_user_enabled(user_id, int(payload.get("is_enabled", 1)), operator, role)
            return jsonify(result), 200
        except SystemError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.post("/api/system/users/<int:user_id>/roles")
    def api_system_user_roles(user_id: int):
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        role_ids = payload.get("role_ids") or []
        try:
            result = set_user_roles(user_id, [int(r) for r in role_ids], operator, role)
            return jsonify(result), 200
        except (ValueError, SystemError) as err:
            return jsonify({"error": str(err)}), 400

    @app.get("/api/system/roles")
    def api_system_roles():
        try:
            result = list_roles(request.args)
            return jsonify(result), 200
        except SystemError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.post("/api/system/roles")
    def api_system_roles_save():
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        try:
            result = create_or_update_role(payload, operator, role)
            return jsonify(result), 200
        except SystemError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.post("/api/system/roles/<int:role_id>/permissions")
    def api_system_role_permissions(role_id: int):
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        perms = payload.get("permissions") or []
        try:
            result = set_role_permissions(role_id, [str(p) for p in perms], operator, role)
            return jsonify(result), 200
        except SystemError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.get("/api/system/rules")
    def api_system_rules():
        try:
            result = list_rules(request.args)
            return jsonify(result), 200
        except SystemError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.post("/api/system/rules")
    def api_system_rules_save():
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        try:
            result = upsert_rule(payload, operator, role)
            return jsonify(result), 200
        except SystemError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.get("/api/system/audit")
    def api_system_audit():
        try:
            result = list_audit_logs(request.args)
            return jsonify(result), 200
        except SystemError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.get("/api/reimbursements")
    def api_reimbursements_list():
        try:
            result = list_reimbursements(request.args)
            return jsonify(result), 200
        except ReimbursementError as err:
            return jsonify({"error": str(err)}), 400

    @app.get("/api/reimbursements/stats")
    def api_reimbursements_stats():
        try:
            result = get_reimbursement_stats(request.args)
            return jsonify(result), 200
        except ReimbursementError as err:
            return jsonify({"error": str(err)}), 400

    @app.get("/api/reimbursements/<int:reimbursement_id>")
    def api_reimbursement_detail(reimbursement_id: int):
        try:
            result = get_reimbursement_detail(reimbursement_id)
            return jsonify(result), 200
        except ReimbursementError as err:
            return jsonify({"error": str(err)}), 400

    @app.post("/api/reimbursements")
    def api_reimbursement_save():
        payload = request.get_json(silent=True) or {}
        try:
            result = create_or_update_reimbursement(payload)
            return jsonify(result), 201
        except ReimbursementError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.post("/api/reimbursements/<int:reimbursement_id>/submit")
    def api_reimbursement_submit(reimbursement_id: int):
        operator, role = _get_operator_from_headers()
        try:
            result = submit_reimbursement(reimbursement_id, operator, role)
            return jsonify(result), 200
        except ReimbursementError as err:
            return jsonify({"error": str(err)}), 400

    @app.post("/api/reimbursements/<int:reimbursement_id>/approve")
    def api_reimbursement_approve(reimbursement_id: int):
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        try:
            result = approve_reimbursement(
                reimbursement_id, operator, role, payload.get("comment")
            )
            log_audit(
                "reimbursement",
                "approve",
                "reimbursement",
                reimbursement_id,
                operator,
                role,
                {"comment": payload.get("comment") or ""},
            )
            return jsonify(result), 200
        except ReimbursementError as err:
            return jsonify({"error": str(err)}), 400

    @app.post("/api/reimbursements/<int:reimbursement_id>/reject")
    def api_reimbursement_reject(reimbursement_id: int):
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        try:
            result = reject_reimbursement(
                reimbursement_id, operator, role, payload.get("reason")
            )
            log_audit(
                "reimbursement",
                "reject",
                "reimbursement",
                reimbursement_id,
                operator,
                role,
                {"reason": payload.get("reason") or ""},
            )
            return jsonify(result), 200
        except ReimbursementError as err:
            return jsonify({"error": str(err)}), 400

    @app.get("/api/payments")
    def api_payments_list():
        try:
            result = list_payments(request.args)
            return jsonify(result), 200
        except PaymentError as err:
            return jsonify({"error": str(err)}), 400

    @app.get("/api/payments/<int:payment_id>")
    def api_payment_detail(payment_id: int):
        try:
            result = get_payment_detail(payment_id)
            return jsonify(result), 200
        except PaymentError as err:
            return jsonify({"error": str(err)}), 400

    @app.post("/api/payments")
    def api_payment_save():
        payload = request.get_json(silent=True) or {}
        try:
            result = create_or_update_payment(payload)
            return jsonify(result), 201
        except PaymentError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.post("/api/payments/<int:payment_id>/submit")
    def api_payment_submit(payment_id: int):
        operator, role = _get_operator_from_headers()
        try:
            result = submit_payment(payment_id, operator, role)
            log_audit("payment", "submit", "payment", payment_id, operator, role, {})
            return jsonify(result), 200
        except PaymentError as err:
            return jsonify({"error": str(err)}), 400

    @app.post("/api/payments/<int:payment_id>/approve")
    def api_payment_approve(payment_id: int):
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        try:
            result = approve_payment(payment_id, operator, role, payload.get("comment"))
            log_audit(
                "payment",
                "approve",
                "payment",
                payment_id,
                operator,
                role,
                {"comment": payload.get("comment") or ""},
            )
            return jsonify(result), 200
        except PaymentError as err:
            return jsonify({"error": str(err)}), 400

    @app.post("/api/payments/<int:payment_id>/reject")
    def api_payment_reject(payment_id: int):
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        try:
            result = reject_payment(payment_id, operator, role, payload.get("reason"))
            log_audit(
                "payment",
                "reject",
                "payment",
                payment_id,
                operator,
                role,
                {"reason": payload.get("reason") or ""},
            )
            return jsonify(result), 200
        except PaymentError as err:
            return jsonify({"error": str(err)}), 400

    @app.post("/api/payments/<int:payment_id>/execute")
    def api_payment_execute(payment_id: int):
        operator, role = _get_operator_from_headers()
        try:
            result = execute_payment(payment_id, operator, role)
            log_audit("payment", "execute", "payment", payment_id, operator, role, {})
            return jsonify(result), 200
        except PaymentError as err:
            return jsonify({"error": str(err)}), 400

    @app.post("/api/bank_transactions/import")
    def api_bank_import():
        try:
            book_id = int(request.form.get("book_id", ""))
            bank_account_id = int(request.form.get("bank_account_id", ""))
            file = request.files.get("file")
            if not file:
                return jsonify({"error": "file required"}), 400
            data = import_bank_transactions(
                book_id, bank_account_id, file.filename, file.read()
            )
            return jsonify(data), 200
        except (ValueError, BankImportError) as err:
            return jsonify({"error": str(err)}), 400

    @app.get("/api/bank_transactions")
    def api_bank_list():
        try:
            result = list_bank_transactions(request.args)
            return jsonify(result), 200
        except BankImportError as err:
            return jsonify({"error": str(err)}), 400

    @app.get("/api/reconcile/list")
    def api_reconcile_list():
        try:
            result = list_reconciliation_items(request.args)
            return jsonify(result), 200
        except ReconcileError as err:
            return jsonify({"error": str(err)}), 400

    @app.post("/api/reconcile/auto")
    def api_reconcile_auto():
        try:
            result = auto_match(request.args)
            return jsonify(result), 200
        except ReconcileError as err:
            return jsonify({"error": str(err)}), 400

    @app.post("/api/reconcile/confirm")
    def api_reconcile_confirm():
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        try:
            result = confirm_match(
                int(payload.get("bank_transaction_id")),
                int(payload.get("voucher_id")),
                operator,
                role,
            )
            log_audit(
                "bank_reconcile",
                "confirm",
                "bank_transaction",
                int(payload.get("bank_transaction_id")),
                operator,
                role,
                {"voucher_id": payload.get("voucher_id")},
            )
            return jsonify(result), 200
        except (ValueError, ReconcileError) as err:
            return jsonify({"error": str(err)}), 400

    @app.post("/api/reconcile/cancel")
    def api_reconcile_cancel():
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        try:
            result = cancel_match(int(payload.get("bank_transaction_id")), operator, role)
            log_audit(
                "bank_reconcile",
                "cancel",
                "bank_transaction",
                int(payload.get("bank_transaction_id")),
                operator,
                role,
                {},
            )
            return jsonify(result), 200
        except (ValueError, ReconcileError) as err:
            return jsonify({"error": str(err)}), 400

    @app.get("/api/reconcile/report")
    def api_reconcile_report():
        try:
            result = get_reconcile_report(request.args)
            return jsonify(result), 200
        except ReconcileError as err:
            return jsonify({"error": str(err)}), 400

    @app.get("/api/tax/rules")
    def api_tax_rules():
        try:
            result = list_tax_rules()
            return jsonify(result), 200
        except TaxError as err:
            return jsonify({"error": str(err)}), 400

    @app.post("/api/tax/rules")
    def api_tax_rules_create():
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        try:
            result = create_tax_rule(payload)
            log_audit("tax", "rule_create", "tax_rule", result.get("id"), operator, role, payload)
            return jsonify(result), 201
        except TaxError as err:
            return jsonify({"error": str(err)}), 400

    @app.post("/api/tax/invoices/import")
    def api_tax_invoices_import():
        try:
            book_id = int(request.form.get("book_id", ""))
            file = request.files.get("file")
            if not file:
                return jsonify({"error": "file required"}), 400
            data = import_invoices(book_id, file.filename, file.read())
            return jsonify(data), 200
        except (ValueError, TaxError) as err:
            return jsonify({"error": str(err)}), 400

    @app.get("/api/tax/invoices")
    def api_tax_invoices():
        try:
            result = list_invoices(request.args)
            return jsonify(result), 200
        except TaxError as err:
            return jsonify({"error": str(err)}), 400

    @app.get("/api/tax/summary")
    def api_tax_summary():
        try:
            result = get_tax_summary(request.args)
            return jsonify(result), 200
        except TaxError as err:
            return jsonify({"error": str(err)}), 400

    @app.get("/api/tax/validate")
    def api_tax_validate():
        try:
            result = validate_tax(request.args)
            return jsonify(result), 200
        except TaxError as err:
            return jsonify({"error": str(err)}), 400

    @app.get("/api/tax/alerts/build")
    def api_tax_alerts_build():
        try:
            result = build_tax_alerts(request.args)
            return jsonify(result), 200
        except TaxError as err:
            return jsonify({"error": str(err)}), 400

    @app.get("/api/tax/alerts")
    def api_tax_alerts_list():
        try:
            result = list_tax_alerts(request.args)
            return jsonify(result), 200
        except TaxError as err:
            return jsonify({"error": str(err)}), 400

    @app.get("/api/vouchers/<int:voucher_id>")
    def api_voucher_detail(voucher_id: int):
        try:
            result = get_voucher_detail(voucher_id)
            return jsonify(result), 200
        except LedgerError as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("voucher_detail_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.post("/api/vouchers")
    def api_save_voucher():
        payload = request.get_json(silent=True) or {}
        try:
            result = save_voucher(payload)
            log_audit(
                "voucher",
                "voucher_create",
                "voucher",
                result.get("voucher_id"),
                payload.get("maker", ""),
                "",
                {"book_id": payload.get("book_id"), "status": result.get("status")},
            )
            return jsonify(result), 201
        except VoucherValidationError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400
        except Exception:
            app.logger.exception("voucher_save_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.post("/api/vouchers/<int:voucher_id>/approve")
    def api_voucher_approve(voucher_id: int):
        operator, role = _get_operator_from_headers()
        try:
            result = change_voucher_status(voucher_id, "approve", operator, role)
            log_audit("voucher", "approve", "voucher", voucher_id, operator, role, {})
            return jsonify(result), 200
        except VoucherStatusError as err:
            return jsonify({"error": str(err)}), 400

    @app.post("/api/vouchers/<int:voucher_id>/unapprove")
    def api_voucher_unapprove(voucher_id: int):
        operator, role = _get_operator_from_headers()
        try:
            result = change_voucher_status(voucher_id, "unapprove", operator, role)
            log_audit("voucher", "unapprove", "voucher", voucher_id, operator, role, {})
            return jsonify(result), 200
        except VoucherStatusError as err:
            return jsonify({"error": str(err)}), 400

    @app.post("/api/vouchers/<int:voucher_id>/post")
    def api_voucher_post(voucher_id: int):
        operator, role = _get_operator_from_headers()
        try:
            result = change_voucher_status(voucher_id, "post", operator, role)
            log_audit("voucher", "post", "voucher", voucher_id, operator, role, {})
            return jsonify(result), 200
        except VoucherStatusError as err:
            return jsonify({"error": str(err)}), 400

    @app.post("/api/vouchers/<int:voucher_id>/unpost")
    def api_voucher_unpost(voucher_id: int):
        operator, role = _get_operator_from_headers()
        try:
            result = change_voucher_status(voucher_id, "unpost", operator, role)
            log_audit("voucher", "unpost", "voucher", voucher_id, operator, role, {})
            return jsonify(result), 200
        except VoucherStatusError as err:
            return jsonify({"error": str(err)}), 400

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
