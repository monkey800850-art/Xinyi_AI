import io
import os
import calendar
import argparse
import json
from fnmatch import fnmatch
import re
import sys
from argparse import Namespace
from datetime import date, datetime, timedelta, timezone

from flask import Flask, jsonify, request, send_file, session
from sqlalchemy import text
from werkzeug.exceptions import HTTPException

from app.config import DatabaseConfigError, load_env
from app.db import test_db_connection
from app.db_router import clear_request_route_context, get_connection_provider, set_request_route_context
from app.routes import consolidation_bp, core_pages_bp
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
from app.services.reconciliation_service import (
    bulk_confirm_reconciliation,
    get_discrepancy_reasons,
    get_reconciliation_rules,
)
from app.services.book_service import (
    BookCreateError,
    BookManageError,
    build_book_backup_snapshot,
    create_book_with_subject_init,
    disable_book,
    get_book_init_integrity,
    list_books,
    verify_book_backup_snapshot,
)
from app.services.consolidation_service import (
    ConsolidationError,
    add_consolidation_group_member,
    create_consolidation_group,
    get_effective_group_members,
)
from app.services.consolidation_manage_service import (
    ConsolidationManageError,
    add_virtual_entity_member,
    bind_non_legal_to_legal,
    create_virtual_entity,
    disable_virtual_entity_member,
    get_virtual_entity_detail,
    list_relation_overview,
    list_virtual_entity_members,
)
from app.services.consolidation_authorization_service import (
    ConsolidationAuthorizationError,
    assert_virtual_authorized,
    create_authorization,
    list_authorizations,
    set_authorization_status,
)
from app.services.consolidation_adjustment_service import (
    ConsolidationAdjustmentError,
    create_consolidation_adjustment,
    get_adjustment_set_meta,
    list_consolidation_adjustment_sets,
    list_consolidation_adjustments,
    transition_adjustment_set_status,
)
from app.services.consolidation_ownership_service import (
    ConsolidationOwnershipError,
    create_consolidation_ownership,
    list_consolidation_ownership,
)
from app.services.consolidation_control_service import (
    ConsolidationControlError,
    get_consolidation_control_decision,
)
from app.services.consolidation_nci_service import ConsolidationNciError, get_consolidation_nci
from app.services.consolidation_nci_dynamic_service import (
    ConsolidationNciDynamicError,
    generate_nci_dynamic,
)
from app.services.consolidation_multi_period_rollover_service import (
    ConsolidationMultiPeriodRolloverError,
    generate_multi_period_rollover,
)
from app.services.consolidation_merge_journal_service import (
    ConsolidationMergeJournalError,
    generate_merge_journal_and_post_merge_balance,
)
from app.services.consolidation_report_generation_service import (
    ConsolidationReportGenerationError,
    generate_report_templates_and_merge_reports,
)
from app.services.consolidation_audit_permission_service import (
    ConsolidationAuditPermissionError,
    run_audit_logs_and_permission_control,
)
from app.services.consolidation_scope_criteria_service import (
    ConsolidationScopeCriteriaError,
    configure_merger_scope_and_criteria,
)
from app.services.consolidation_report_automation_service import (
    ConsolidationReportAutomationError,
    automate_report_generation_and_adjustment,
)
from app.services.consolidation_final_check_approval_service import (
    ConsolidationFinalCheckApprovalError,
    run_final_check_and_approval_flow,
)
from app.services.consolidation_disclosure_audit_package_service import (
    ConsolidationDisclosureAuditPackageError,
    generate_disclosure_and_audit_package,
)
from app.services.consolidation_onboarding_ic_match_service import (
    ConsolidationOnboardingIcMatchError,
    run_onboarding_ic_match,
)
from app.services.consolidation_purchase_method_service import (
    ConsolidationPurchaseMethodError,
    generate_purchase_method,
)
from app.services.consolidation_equity_method_service import (
    ConsolidationEquityMethodError,
    generate_equity_method,
)
from app.services.consolidation_unrealized_profit_service import (
    ConsolidationUnrealizedProfitError,
    generate_inventory_unrealized_profit,
)
from app.services.consolidation_unrealized_profit_reversal_service import (
    ConsolidationUnrealizedProfitReversalError,
    generate_inventory_unrealized_profit_reversal,
)
from app.services.consolidation_ic_asset_transfer_service import (
    ConsolidationIcAssetTransferError,
    generate_ic_asset_transfer_onboard,
)
from app.services.consolidation_type_service import (
    ConsolidationTypeError,
    evaluate_type,
    get_type,
    set_type,
)
from app.services.consolidation_audit_service import log_consolidation_audit
from app.services.consolidation_parameters_service import (
    ConsolidationParameterError,
    list_consolidation_parameters_contract,
    upsert_consolidation_parameters_contract,
)
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
from app.services.system_auth_service import AuthError, authenticate_user
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
from app.services.master_data_service import (
    MasterDataError,
    get_subject_aux_effective,
    list_master_items,
    list_subject_aux_configs,
    save_subject_aux_config,
    upsert_master_item,
)
from app.services.payment_service import (
    PaymentError,
    approve_payment,
    create_or_update_payment,
    delete_payment,
    execute_payment,
    get_payment_detail,
    list_payments,
    reject_payment,
    submit_payment,
    void_payment,
)
from app.services.payroll_service import (
    PayrollError,
    confirm_payroll_slip,
    create_payroll_disbursement_batch,
    create_payroll_payment_request,
    export_payroll_bank_file,
    list_payroll_disbursement_batches,
    list_payroll_region_policies,
    get_payroll_payment_status,
    get_payroll_voucher_suggestion,
    list_payroll_periods,
    list_payroll_slips,
    set_payroll_period_status,
    sync_attendance_interface,
    upsert_payroll_region_policy,
    upsert_payroll_period,
    upsert_payroll_slip,
)
from app.services.reimbursement_service import (
    ReimbursementError,
    approve_reimbursement,
    create_or_update_reimbursement,
    delete_reimbursement,
    get_reimbursement_detail,
    get_reimbursement_stats,
    list_reimbursement_sla_reminders,
    list_reimbursements,
    reject_reimbursement,
    submit_reimbursement,
    void_reimbursement,
)
from app.services.tax_service import (
    TaxError,
    build_tax_declaration_mapping,
    calc_labor_service_tax,
    calc_year_end_bonus_tax,
    build_tax_alerts,
    create_tax_diff_entry,
    create_tax_rule,
    get_tax_summary,
    import_invoices,
    list_invoices,
    list_tax_alerts,
    list_tax_declaration_mappings,
    list_tax_diff_entries,
    list_tax_rules,
    map_tax_declaration,
    validate_tax,
    verify_invoice,
)
from app.services.trial_balance_service import TrialBalanceError, get_trial_balance
from app.services.voucher_import_service import (
    VoucherImportError,
    commit_vouchers_import,
    get_voucher_import_template,
    preview_vouchers_import,
)
from app.services.voucher_service import VoucherValidationError, save_voucher
from app.services.voucher_template_service import VoucherTemplateError, build_template_preview
from app.services.voucher_template_service import (
    build_template_draft,
    get_template_detail,
    list_template_candidates,
)
from app.services.voucher_status_service import VoucherStatusError, change_voucher_status
from app.utils.errors import APIError, build_api_error_response


def _get_operator_from_headers():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}

    operator = request.headers.get("X-User", "").strip()
    role = request.headers.get("X-Role", "").strip()

    if not operator:
        operator = str(payload.get("operator") or payload.get("user") or payload.get("username") or payload.get("maker") or "").strip()
    if not role:
        role = str(payload.get("role") or payload.get("operator_role") or "").strip()

    if not operator:
        operator = request.form.get("operator", "").strip() or request.args.get("operator", "").strip()
    if not role:
        role = request.form.get("role", "").strip() or request.args.get("role", "").strip()

    auth_ctx = session.get("auth_ctx") if isinstance(session.get("auth_ctx"), dict) else {}
    if not operator:
        operator = str(auth_ctx.get("username") or "").strip()
    if not role:
        role = str(auth_ctx.get("role") or "").strip()
    return operator, role


def _parse_operator_id(value) -> int | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = int(raw)
    except Exception:
        return None
    return parsed if parsed > 0 else None


def _get_operator_id(payload: dict | None = None) -> int | None:
    payload = payload if isinstance(payload, dict) else {}
    candidate = (
        request.headers.get("X-Operator-Id")
        or payload.get("operator_id")
        or request.args.get("operator_id")
        or request.form.get("operator_id")
    )
    return _parse_operator_id(candidate)


def _safe_log_consolidation_audit(
    action: str,
    group_id: int | None,
    status: str,
    code: int,
    operator_id: int | None = None,
    payload: dict | None = None,
    note: str = "",
) -> None:
    try:
        log_consolidation_audit(
            action=action,
            group_id=group_id,
            status=status,
            code=code,
            operator_id=operator_id,
            payload=payload,
            note=note,
        )
    except Exception:
        app.logger.exception("consolidation_audit_log_failed action=%s group_id=%s", action, group_id)


def _period_to_as_of_date(period: str) -> date:
    raw = str(period or "").strip()
    if len(raw) != 7 or raw[4] != "-":
        raise ValueError("period_invalid")
    year = int(raw[:4])
    month = int(raw[5:])
    if month < 1 or month > 12:
        raise ValueError("period_invalid")
    day = calendar.monthrange(year, month)[1]
    return date(year, month, day)


def _build_main_nav(path: str):
    current = str(path or "").strip() or "/dashboard"
    nav_groups = [
        {
            "key": "system",
            "label": "系统管理",
            "items": [
                {"label": "工作台", "url": "/dashboard", "prefixes": ["/dashboard"]},
                {"label": "系统用户", "url": "/system/users", "prefixes": ["/system/users"]},
                {"label": "系统角色", "url": "/system/roles", "prefixes": ["/system/roles"]},
                {"label": "系统规则", "url": "/system/rules", "prefixes": ["/system/rules"]},
                {"label": "账套管理", "url": "/system/books", "prefixes": ["/system/books"]},
                {"label": "账套关系与合并管理", "url": "/system/consolidation", "prefixes": ["/system/consolidation"]},
                {"label": "建账初始化", "url": "/system/book-init", "prefixes": ["/system/book-init"]},
                {"label": "系统测试初始化（样本）", "url": "/system/init", "prefixes": ["/system/init"]},
                {"label": "系统审计日志", "url": "/system/audit", "prefixes": ["/system/audit"]},
            ],
        },
        {
            "key": "master",
            "label": "基础资料 / 辅助管理",
            "items": [
                {"label": "科目辅助挂接", "url": "/masters/subjects/aux", "prefixes": ["/masters/subjects/aux"]},
                {"label": "部门", "url": "/masters/departments", "prefixes": ["/masters/departments"]},
                {"label": "个人", "url": "/masters/persons", "prefixes": ["/masters/persons"]},
                {"label": "单位", "url": "/masters/entities", "prefixes": ["/masters/entities"]},
                {"label": "项目", "url": "/masters/projects", "prefixes": ["/masters/projects"]},
                {"label": "银行账户", "url": "/masters/bank_accounts", "prefixes": ["/masters/bank_accounts"]},
            ],
        },
        {
            "key": "voucher",
            "label": "凭证与账务",
            "items": [
                {"label": "凭证录入", "url": "/voucher/entry", "prefixes": ["/voucher/entry"]},
                {"label": "批量导入序时账", "url": "/voucher/import", "prefixes": ["/voucher/import"]},
            ],
        },
        {
            "key": "reports",
            "label": "报表",
            "items": [
                {"label": "发生余额表", "url": "/reports/trial_balance", "prefixes": ["/reports/trial_balance"]},
                {"label": "科目明细账", "url": "/reports/subject_ledger", "prefixes": ["/reports/subject_ledger"]},
                {"label": "辅助余额与明细", "url": "/reports/aux_reports", "prefixes": ["/reports/aux_reports"]},
                {"label": "应收应付账龄", "url": "/reports/ar_ap", "prefixes": ["/reports/ar_ap"]},
            ],
        },
        {
            "key": "tax",
            "label": "税务",
            "items": [
                {"label": "税务发票", "url": "/tax/invoices", "prefixes": ["/tax/invoices"]},
                {"label": "税务汇总", "url": "/tax/summary", "prefixes": ["/tax/summary"]},
                {"label": "税务规则", "url": "/tax/rules", "prefixes": ["/tax/rules"]},
            ],
        },
        {
            "key": "funds",
            "label": "资金",
            "items": [
                {"label": "银行导入", "url": "/banks/import", "prefixes": ["/banks/import"]},
                {"label": "银行对账", "url": "/banks/reconcile", "prefixes": ["/banks/reconcile"]},
                {"label": "支付申请", "url": "/payments", "prefixes": ["/payments", "/payments/"]},
                {"label": "新建支付申请", "url": "/payments/new", "prefixes": ["/payments/new"]},
            ],
        },
        {
            "key": "reimbursement",
            "label": "费用报销",
            "items": [
                {"label": "报销管理", "url": "/reimbursements", "prefixes": ["/reimbursements", "/reimbursements/"]},
                {"label": "新建报销单", "url": "/reimbursements/new", "prefixes": ["/reimbursements/new"]},
            ],
        },
        {
            "key": "assets",
            "label": "资产",
            "items": [
                {"label": "资产台账", "url": "/assets", "prefixes": ["/assets", "/assets/"]},
                {"label": "新建资产卡片", "url": "/assets/new", "prefixes": ["/assets/new"]},
                {"label": "资产类别", "url": "/assets/categories", "prefixes": ["/assets/categories"]},
                {"label": "资产变动", "url": "/assets/changes", "prefixes": ["/assets/changes"]},
                {"label": "资产折旧", "url": "/assets/depreciation", "prefixes": ["/assets/depreciation"]},
                {"label": "资产台账报表", "url": "/assets/reports/ledger", "prefixes": ["/assets/reports/ledger"]},
                {"label": "资产折旧汇总", "url": "/assets/reports/depreciation", "prefixes": ["/assets/reports/depreciation"]},
            ],
        },
    ]

    current_title = "工作台"
    for group in nav_groups:
        group["active"] = False
        for item in group["items"]:
            active = current == item["url"] or any(current.startswith(p) for p in item.get("prefixes", []))
            item["active"] = bool(active)
            if active:
                group["active"] = True
                current_title = item["label"]
    return nav_groups, current_title


def create_app() -> Flask:
    app_env = load_env()

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
    app.secret_key = os.getenv("SECRET_KEY")
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    default_samesite = "Strict" if app_env == "production" else "Lax"
    default_secure = "1" if app_env == "production" else "0"
    app.config["SESSION_COOKIE_SAMESITE"] = os.getenv("SESSION_COOKIE_SAMESITE", default_samesite)
    app.config["SESSION_COOKIE_SECURE"] = (
        str(os.getenv("SESSION_COOKIE_SECURE", default_secure)).strip().lower() in ("1", "true", "yes", "on")
    )

    def _as_positive_int(raw: str, fallback: int) -> int:
        try:
            value = int(str(raw or "").strip())
            return value if value > 0 else fallback
        except Exception:
            return fallback

    auth_session_timeout_minutes = _as_positive_int(os.getenv("AUTH_SESSION_TIMEOUT_MINUTES", "30"), 30)
    auth_max_failed_attempts = _as_positive_int(os.getenv("AUTH_MAX_FAILED_ATTEMPTS", "5"), 5)
    auth_lock_minutes = _as_positive_int(os.getenv("AUTH_LOCK_MINUTES", "15"), 15)
    auth_enable_rbac = str(os.getenv("AUTH_ENABLE_RBAC", "1")).strip().lower() in ("1", "true", "yes", "on")
    exempt_auth_paths = {"/api/auth/login"}

    def _is_protected_path(path: str) -> bool:
        path = str(path or "")
        return path.startswith("/api/") or path.startswith("/task/")

    def _load_role_permissions(role_code: str, tenant_id: str | None = None, book_id: str | None = None) -> set[str]:
        role_code = str(role_code or "").strip()
        if not role_code:
            return set()
        provider = get_connection_provider()
        with provider.connect(tenant_id=tenant_id, book_id=book_id) as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT p.perm_key
                    FROM sys_roles r
                    LEFT JOIN sys_role_permissions p ON p.role_id = r.id
                    WHERE r.code=:code
                      AND r.is_enabled=1
                    """
                ),
                {"code": role_code},
            ).fetchall()
        return {str(r.perm_key or "").strip() for r in rows if str(r.perm_key or "").strip()}

    def _rbac_allows(path: str, method: str, role_code: str, perms: set[str]) -> bool:
        role_code = str(role_code or "").strip().lower()
        if role_code in ("admin", "tester"):
            return True

        path = str(path or "").rstrip("/") or "/"
        method = str(method or "GET").upper()
        if not perms:
            return False

        family = "api" if path.startswith("/api/") else "task"
        token = f"{method}:{path}"
        direct_candidates = {
            "*",
            f"{family}:*",
            f"{method}:*",
            f"{method}:{family}:*",
            token,
            path,
        }
        if any(c in perms for c in direct_candidates):
            return True

        for perm in perms:
            p = str(perm or "").strip()
            if not p:
                continue
            if "*" in p and (fnmatch(token, p) or fnmatch(path, p)):
                return True
            if p.endswith(":") and token.startswith(p):
                return True
            if p.endswith("/") and path.startswith(p):
                return True
            if p.startswith("/") and path.startswith(p):
                return True
        return False

    app.register_blueprint(core_pages_bp)
    app.register_blueprint(consolidation_bp)

    def _is_api_or_task_path() -> bool:
        path = str(getattr(request, "path", "") or "")
        return path.startswith("/api/") or path.startswith("/task/")

    def _build_contract_error(
        code: str,
        message: str,
        details: dict | None = None,
    ) -> dict:
        request_id = (
            request.headers.get("X-Request-Id")
            or request.headers.get("X-Correlation-Id")
            or ""
        )
        return build_api_error_response(
            code=code,
            message=message,
            details=details or {},
            request_id=str(request_id or "").strip(),
            path=request.path,
            method=request.method,
        )

    def _safe_audit_error(action: str, detail: dict):
        try:
            operator, role = _get_operator_from_headers()
            log_audit("api", action, "request", None, operator, role, detail)
        except Exception:
            app.logger.exception("api_error_audit_failed action=%s", action)

    @app.errorhandler(APIError)
    def _handle_api_error(error: APIError):
        payload = _build_contract_error(error.code, error.message, error.details)
        _safe_audit_error(
            "api_error",
            {
                "code": error.code,
                "status_code": int(error.status_code),
                "path": request.path,
                "method": request.method,
            },
        )
        return jsonify(payload), int(error.status_code)

    @app.errorhandler(HTTPException)
    def _handle_http_exception(error: HTTPException):
        if not _is_api_or_task_path():
            return error
        code = "not_found" if int(error.code or 500) == 404 else "http_error"
        payload = _build_contract_error(code, str(error.name or "http_error"), {"description": str(error.description or "")})
        _safe_audit_error(
            "http_exception",
            {
                "code": int(error.code or 500),
                "name": str(error.name or ""),
                "path": request.path,
                "method": request.method,
            },
        )
        return jsonify(payload), int(error.code or 500)

    @app.errorhandler(Exception)
    def _handle_unexpected_exception(error: Exception):
        if not _is_api_or_task_path():
            raise error
        app.logger.exception("api_unexpected_error path=%s", request.path)
        payload = _build_contract_error("internal_error", "internal_error", {})
        _safe_audit_error(
            "internal_error",
            {
                "error": str(type(error).__name__),
                "path": request.path,
                "method": request.method,
            },
        )
        return jsonify(payload), 500

    @app.context_processor
    def _inject_main_nav():
        nav_groups, current_title = _build_main_nav(request.path)
        auth_ctx = session.get("auth_ctx") if isinstance(session.get("auth_ctx"), dict) else {}
        book_ctx = session.get("book_ctx") if isinstance(session.get("book_ctx"), dict) else {}
        subject_ctx = session.get("subject_ctx") if isinstance(session.get("subject_ctx"), dict) else {}
        current_subject_type = (
            request.headers.get("X-Subject-Type")
            or request.args.get("subject_type")
            or request.form.get("subject_type")
            or str(subject_ctx.get("subject_type") or "")
        ).strip()
        current_subject_id = (
            request.headers.get("X-Subject-Id")
            or request.args.get("subject_id")
            or request.form.get("subject_id")
            or str(subject_ctx.get("subject_id") or "")
        ).strip()
        if not current_subject_type and current_subject_id:
            current_subject_type = "book"
        if not current_subject_type:
            current_subject_type = "book"
        return {
            "nav_groups": nav_groups,
            "current_nav_title": current_title,
            "current_user_name": (
                request.headers.get("X-User") or request.args.get("user") or str(auth_ctx.get("username") or "")
            ).strip(),
            "current_user_role": (
                request.headers.get("X-Role") or request.args.get("role") or str(auth_ctx.get("role") or "")
            ).strip(),
            "current_book_id": (
                request.headers.get("X-Book-Id")
                or request.args.get("book_id")
                or request.form.get("book_id")
                or str(book_ctx.get("book_id") or "")
            ).strip()
            if current_subject_type == "book"
            else "",
            "current_subject_type": current_subject_type,
            "current_subject_id": current_subject_id,
        }

    def _extract_route_context():
        tenant_id = (request.headers.get("X-Tenant-Id") or "").strip()
        book_id = (request.headers.get("X-Book-Id") or "").strip()

        if request.view_args and "book_id" in request.view_args:
            book_id = str(request.view_args.get("book_id") or "").strip()
        if not book_id:
            book_id = (request.args.get("book_id") or "").strip()
        if not book_id:
            book_id = (request.form.get("book_id") or "").strip()

        payload = request.get_json(silent=True)
        if isinstance(payload, dict):
            if not tenant_id:
                tenant_id = str(payload.get("tenant_id") or "").strip()
            if not book_id:
                book_id = str(payload.get("book_id") or "").strip()

        if not tenant_id:
            tenant_id = (request.args.get("tenant_id") or "").strip()
        if not tenant_id:
            tenant_id = (request.form.get("tenant_id") or "").strip()

        return tenant_id or None, book_id or None

    @app.before_request
    def _bind_route_context():
        path = request.path or "/"
        tenant_id, book_id = _extract_route_context()
        set_request_route_context(tenant_id=tenant_id, book_id=book_id)
        auth_ctx = session.get("auth_ctx") if isinstance(session.get("auth_ctx"), dict) else {}
        expires_raw = str(session.get("auth_expires_at") or "").strip()
        if auth_ctx and expires_raw:
            try:
                expires_at = datetime.fromisoformat(expires_raw)
            except Exception:
                expires_at = None
            now_utc = datetime.now(timezone.utc)
            if expires_at is not None and expires_at <= now_utc:
                session.pop("auth_ctx", None)
                session.pop("auth_expires_at", None)
            elif expires_at is not None:
                session.permanent = True
                session["auth_expires_at"] = (
                    now_utc + timedelta(minutes=auth_session_timeout_minutes)
                ).isoformat()

        operator, role = _get_operator_from_headers()
        has_auth_headers = bool(
            str(request.headers.get("X-User") or "").strip() or str(request.headers.get("X-Role") or "").strip()
        )
        if operator or role:
            current = session.get("auth_ctx") if isinstance(session.get("auth_ctx"), dict) else {}
            # Avoid treating arbitrary payload fields as login; only persist when session already exists
            # or when upstream auth headers are explicitly present.
            if current or has_auth_headers:
                session["auth_ctx"] = {
                    "username": operator or str(current.get("username") or ""),
                    "role": role or str(current.get("role") or ""),
                }
                if current.get("user_id"):
                    session["auth_ctx"]["user_id"] = int(current.get("user_id"))
        payload = request.get_json(silent=True)
        subject_type = (
            request.headers.get("X-Subject-Type")
            or request.args.get("subject_type")
            or request.form.get("subject_type")
            or (str(payload.get("subject_type") or "").strip() if isinstance(payload, dict) else "")
        ).strip().lower()
        subject_id = (
            request.headers.get("X-Subject-Id")
            or request.args.get("subject_id")
            or request.form.get("subject_id")
            or (str(payload.get("subject_id") or "").strip() if isinstance(payload, dict) else "")
        ).strip()
        if not subject_type and subject_id:
            subject_type = "book"
        if not subject_type and book_id:
            subject_type = "book"
            subject_id = str(book_id)
        if subject_type in ("book", "virtual") and subject_id:
            session["subject_ctx"] = {
                "subject_type": subject_type,
                "subject_id": str(subject_id),
            }

        if book_id and str(subject_type or "book") == "book":
            session["book_ctx"] = {"book_id": str(book_id)}

        if auth_enable_rbac and _is_protected_path(path) and path not in exempt_auth_paths:
            current_auth = session.get("auth_ctx") if isinstance(session.get("auth_ctx"), dict) else {}
            username = str(current_auth.get("username") or "").strip()
            role_code = str(current_auth.get("role") or "").strip()
            if not username:
                return jsonify({"error": "unauthorized"}), 401
            if not role_code:
                try:
                    log_audit(
                        "auth",
                        "forbidden",
                        "request",
                        None,
                        username,
                        role_code,
                        {"path": path, "method": request.method, "reason": "role_missing"},
                    )
                except Exception:
                    app.logger.exception("rbac_audit_log_failed role_missing path=%s", path)
                return jsonify({"error": "forbidden"}), 403
            if str(role_code).strip().lower() in ("admin", "tester"):
                return None
            try:
                perms = _load_role_permissions(role_code, tenant_id=tenant_id, book_id=book_id)
            except Exception:
                app.logger.exception("rbac_permission_load_failed role=%s path=%s", role_code, path)
                try:
                    log_audit(
                        "auth",
                        "forbidden",
                        "request",
                        None,
                        username,
                        role_code,
                        {"path": path, "method": request.method, "reason": "permission_load_failed"},
                    )
                except Exception:
                    app.logger.exception("rbac_audit_log_failed permission_load_failed path=%s", path)
                return jsonify({"error": "forbidden"}), 403
            if not _rbac_allows(path=path, method=request.method, role_code=role_code, perms=perms):
                try:
                    log_audit(
                        "auth",
                        "forbidden",
                        "request",
                        None,
                        username,
                        role_code,
                        {"path": path, "method": request.method, "reason": "permission_denied"},
                    )
                except Exception:
                    app.logger.exception("rbac_audit_log_failed permission_denied path=%s", path)
                return jsonify({"error": "forbidden"}), 403

    @app.teardown_request
    def _clear_route_context(_err):
        clear_request_route_context()

    @app.after_request
    def _inject_request_context_script(response):
        try:
            content_type = (response.headers.get("Content-Type") or "").lower()
            if "text/html" not in content_type:
                return response
            html = response.get_data(as_text=True)
            inject = ""
            if "/static/js/request_context.js" not in html:
                inject += '<script src="/static/js/request_context.js"></script>'
            if "/static/js/navigation_rules.js" not in html:
                inject += '<script src="/static/js/navigation_rules.js"></script>'
            if inject:
                html2 = re.sub(
                    r"(<body[^>]*>)",
                    r"\1" + inject,
                    html,
                    count=1,
                    flags=re.IGNORECASE,
                )
                if html2 != html:
                    response.set_data(html2)
        except Exception:
            return response
        return response

    @app.post("/books")
    def create_book():
        payload = request.get_json(silent=True) or {}
        try:
            result = create_book_with_subject_init(payload)
            return jsonify(result), 201
        except BookCreateError as err:
            app.logger.exception("book_create_error")
            return jsonify({"error": str(err)}), 400
        except Exception as err:
            app.logger.exception("book_create_unexpected_error: %s", err)
            return jsonify({"error": "建账失败，请联系管理员并查看服务日志(book_create_unexpected_error)"}), 500

    @app.get("/api/books")
    def api_list_books():
        try:
            result = list_books(request.args)
            return jsonify(result), 200
        except BookManageError as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("book_list_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.get("/api/subjects/switchable")
    def api_switchable_subjects():
        try:
            books_result = list_books(request.args)
            relation = list_relation_overview(request.args.to_dict(flat=True))
            books = books_result.get("items") or []
            virtual_entities = relation.get("virtual_entities") or []

            items = []
            for b in books:
                items.append(
                    {
                        "subject_type": "book",
                        "subject_id": int(b.get("book_id") or b.get("id")),
                        "subject_name": str(b.get("book_name") or ""),
                        "subject_code": str(b.get("book_code") or ""),
                        "status": str(b.get("status") or ""),
                        "is_enabled": int(b.get("is_enabled") or 0),
                        "book_id": int(b.get("book_id") or b.get("id")),
                        "book_name": str(b.get("book_name") or ""),
                        "book_code": str(b.get("book_code") or ""),
                    }
                )
            for v in virtual_entities:
                sid = int(v.get("id") or 0)
                if not sid:
                    continue
                items.append(
                    {
                        "subject_type": "virtual",
                        "subject_id": sid,
                        "subject_name": str(v.get("virtual_name") or ""),
                        "subject_code": str(v.get("virtual_code") or ""),
                        "status": "enabled" if int(v.get("is_enabled") or 0) == 1 else "disabled",
                        "is_enabled": int(v.get("is_enabled") or 0),
                        "virtual_id": sid,
                        "virtual_name": str(v.get("virtual_name") or ""),
                        "virtual_code": str(v.get("virtual_code") or ""),
                        "member_count": int(v.get("member_count") or 0),
                    }
                )

            return jsonify({"items": items, "books": books, "virtual_entities": virtual_entities}), 200
        except (BookManageError, ConsolidationManageError) as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("switchable_subjects_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.get("/api/books/<int:book_id>/init-integrity")
    def api_book_init_integrity(book_id: int):
        try:
            result = get_book_init_integrity(book_id)
            return jsonify(result), 200
        except BookManageError as err:
            return jsonify({"error": str(err)}), 400

    @app.get("/api/books/<int:book_id>/backup-snapshot")
    def api_book_backup_snapshot(book_id: int):
        operator, role = _get_operator_from_headers()
        try:
            result = build_book_backup_snapshot(book_id)
            log_audit(
                "book",
                "backup_snapshot",
                "book",
                book_id,
                operator,
                role,
                {
                    "book_id": book_id,
                    "subject_count": (result.get("stats") or {}).get("subject_count", 0),
                    "period_count": (result.get("stats") or {}).get("period_count", 0),
                },
            )
            return jsonify(result), 200
        except BookManageError as err:
            return jsonify({"error": str(err)}), 400

    @app.post("/api/books/backup-restore-verify")
    def api_book_backup_restore_verify():
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        try:
            result = verify_book_backup_snapshot(payload)
            log_audit(
                "book",
                "backup_restore_verify",
                "book_backup",
                None,
                operator,
                role,
                {"ok": bool(result.get("ok")), "error_count": len(result.get("errors") or [])},
            )
            status = 200 if result.get("ok") else 400
            return jsonify(result), status
        except BookManageError as err:
            return jsonify({"error": str(err)}), 400

    @app.post("/api/books/<int:book_id>/disable")
    def api_disable_book(book_id: int):
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        try:
            result = disable_book(book_id, payload.get("confirm_text", ""), role)
            log_audit(
                "book",
                "disable",
                "book",
                book_id,
                operator,
                role,
                {"book_id": book_id, "safety_confirmed": True},
            )
            return jsonify(result), 200
        except BookManageError as err:
            status = 403 if str(err) == "forbidden" else 400
            return jsonify({"error": str(err)}), status

    @app.get("/api/dashboard/workbench")
    def api_dashboard_workbench():
        try:
            result = get_workbench_metrics(request.args)
            return jsonify(result), 200
        except DashboardError as err:
            return jsonify({"error": str(err)}), 400

    @app.get("/api/dashboard/boss")
    def api_dashboard_boss():
        _, role = _get_operator_from_headers()
        if role not in ("boss", "admin"):
            return jsonify({"error": "forbidden"}), 403
        try:
            result = get_boss_metrics(request.args)
            return jsonify(result), 200
        except DashboardError as err:
            return jsonify({"error": str(err)}), 400

    @app.post("/api/system/init/reset-and-seed")
    def api_system_init_reset_and_seed():
        operator, role = _get_operator_from_headers()
        role = str(role or "").strip().lower()
        if role not in ("admin", "tester"):
            return jsonify({"error": "forbidden"}), 403

        payload = request.get_json(silent=True) or {}

        def _as_bool(value) -> bool:
            if isinstance(value, bool):
                return value
            return str(value or "").strip().lower() in ("1", "true", "yes", "y", "on")

        standards_raw = payload.get("standards")
        if isinstance(standards_raw, list):
            standards = ",".join([str(x).strip() for x in standards_raw if str(x).strip()])
        else:
            standards = str(standards_raw or "small,enterprise").strip()

        dry_run = _as_bool(payload.get("dry_run"))
        force = _as_bool(payload.get("force")) or (not dry_run)
        allow_production = _as_bool(payload.get("allow_production"))
        seed_batch_code = str(payload.get("seed_batch_code") or f"UI-INIT-{date.today().strftime('%Y%m%d')}").strip()

        args = Namespace(
            dry_run=dry_run,
            force=force,
            allow_production=allow_production,
            standards=standards,
            seed_batch_code=seed_batch_code,
        )

        try:
            from scripts.reset_and_seed_sample_data import run as run_data_init

            summary = run_data_init(args)
            log_audit(
                "system",
                "data_init_run",
                "system_init",
                None,
                operator,
                role,
                {
                    "dry_run": 1 if dry_run else 0,
                    "standards": standards,
                    "seed_batch_code": seed_batch_code,
                },
            )
            return jsonify({"ok": True, "summary": summary}), 200
        except Exception as err:
            app.logger.exception("system_init_run_failed")
            return jsonify({"error": str(err)}), 400

    @app.get("/api/autocomplete")
    def api_autocomplete():
        try:
            params = request.args.to_dict(flat=True)
            _, role = _get_operator_from_headers()
            role = str(role or "").strip().lower()
            if "include_hidden" not in params and role in ("tester", "admin"):
                params["include_hidden"] = "1"
            result = autocomplete(params)
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
        except ConsolidationAuthorizationError:
            return jsonify({"error": "forbidden"}), 403
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

    @app.get("/api/masters/<string:kind>")
    def api_list_master_items(kind: str):
        try:
            params = request.args.to_dict(flat=True)
            _, role = _get_operator_from_headers()
            role = str(role or "").strip().lower()
            if "include_hidden" not in params and role in ("tester", "admin"):
                params["include_hidden"] = "1"
            result = list_master_items(kind, params)
            return jsonify(result), 200
        except MasterDataError as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("master_list_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.post("/api/masters/<string:kind>")
    def api_save_master_item(kind: str):
        payload = request.get_json(silent=True) or {}
        try:
            result = upsert_master_item(kind, payload)
            return jsonify(result), 200
        except MasterDataError as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("master_save_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.get("/api/subjects/aux")
    def api_list_subject_aux_configs():
        try:
            result = list_subject_aux_configs(request.args)
            return jsonify(result), 200
        except MasterDataError as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("subject_aux_list_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.post("/api/subjects/aux")
    def api_save_subject_aux_config():
        payload = request.get_json(silent=True) or {}
        try:
            result = save_subject_aux_config(payload)
            return jsonify(result), 200
        except MasterDataError as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("subject_aux_save_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.get("/api/subjects/aux/effective")
    def api_subject_aux_effective():
        try:
            result = get_subject_aux_effective(request.args)
            return jsonify(result), 200
        except MasterDataError as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("subject_aux_effective_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.post("/api/consolidation/groups")
    def api_create_consolidation_group():
        payload = request.get_json(silent=True) or {}
        try:
            result = create_consolidation_group(payload)
            return jsonify(result), 201
        except ConsolidationError as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("consolidation_group_create_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.post("/api/consolidation/groups/<int:group_id>/members")
    def api_add_consolidation_group_member(group_id: int):
        payload = request.get_json(silent=True) or {}
        try:
            result = add_consolidation_group_member(group_id, payload)
            return jsonify(result), 201
        except ConsolidationError as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("consolidation_group_member_add_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.post("/api/consolidation/members")
    def api_consolidation_members_onboard():
        payload = request.get_json(silent=True) or {}
        operator_id = _get_operator_id(payload)
        group_id = None
        try:
            group_id = int(payload.get("consolidation_group_id"))
            if group_id <= 0:
                raise ValueError("consolidation_group_id_invalid")
            with get_connection_provider().connect() as conn:
                assert_virtual_authorized(conn, group_id, date.today())
            member_payload = {
                "member_book_id": payload.get("member_book_id"),
                "member_entity_id": payload.get("member_entity_id"),
                "member_type": payload.get("member_type"),
                "effective_from": payload.get("effective_from"),
                "effective_to": payload.get("effective_to"),
                "note": payload.get("note"),
                "is_enabled": payload.get("is_enabled", 1),
            }
            result = add_consolidation_group_member(group_id, member_payload)
            _safe_log_consolidation_audit(
                action="members_post",
                group_id=group_id,
                status="success",
                code=201,
                operator_id=operator_id,
                payload=payload,
                note="member_onboarded",
            )
            return jsonify({"ok": True, "item": result}), 201
        except (TypeError, ValueError):
            _safe_log_consolidation_audit(
                action="members_post",
                group_id=group_id,
                status="failed",
                code=400,
                operator_id=operator_id,
                payload=payload,
                note="consolidation_group_id_invalid",
            )
            return jsonify({"ok": False, "error": "consolidation_group_id_invalid"}), 400
        except ConsolidationAuthorizationError as err:
            _safe_log_consolidation_audit(
                action="members_post",
                group_id=group_id,
                status="forbidden",
                code=403,
                operator_id=operator_id,
                payload=payload,
                note=str(err),
            )
            return jsonify({"error": "forbidden"}), 403
        except ConsolidationError as err:
            _safe_log_consolidation_audit(
                action="members_post",
                group_id=group_id,
                status="failed",
                code=400,
                operator_id=operator_id,
                payload=payload,
                note=str(err),
            )
            return jsonify({"ok": False, "error": str(err)}), 400
        except Exception:
            app.logger.exception("consolidation_members_onboard_unexpected_error")
            _safe_log_consolidation_audit(
                action="members_post",
                group_id=group_id,
                status="failed",
                code=500,
                operator_id=operator_id,
                payload=payload,
                note="internal_error",
            )
            return jsonify({"ok": False, "error": "internal_error"}), 500

    @app.get("/api/consolidation/read_probe")
    def api_consolidation_read_probe():
        args = request.args.to_dict(flat=True)
        operator_id = _get_operator_id()
        group_id = None
        try:
            group_raw = str(args.get("consolidation_group_id") or "").strip()
            group_id = int(group_raw)
            if group_id <= 0:
                raise ValueError("consolidation_group_id_invalid")
            with get_connection_provider().connect() as conn:
                assert_virtual_authorized(conn, group_id, date.today())
                exists = conn.execute(
                    text("SELECT id FROM consolidation_groups WHERE id=:group_id LIMIT 1"),
                    {"group_id": group_id},
                ).fetchone()
                if not exists:
                    _safe_log_consolidation_audit(
                        action="read_probe",
                        group_id=group_id,
                        status="failed",
                        code=404,
                        operator_id=operator_id,
                        payload=args,
                        note="consolidation_group_not_found",
                    )
                    return jsonify({"ok": False, "error": "consolidation_group_not_found"}), 404
            _safe_log_consolidation_audit(
                action="read_probe",
                group_id=group_id,
                status="success",
                code=200,
                operator_id=operator_id,
                payload=args,
                note="authorized",
            )
            return jsonify({"ok": True, "consolidation_group_id": group_id}), 200
        except (TypeError, ValueError):
            _safe_log_consolidation_audit(
                action="read_probe",
                group_id=group_id,
                status="failed",
                code=400,
                operator_id=operator_id,
                payload=args,
                note="consolidation_group_id_invalid",
            )
            return jsonify({"ok": False, "error": "consolidation_group_id_invalid"}), 400
        except ConsolidationAuthorizationError as err:
            _safe_log_consolidation_audit(
                action="read_probe",
                group_id=group_id,
                status="forbidden",
                code=403,
                operator_id=operator_id,
                payload=args,
                note=str(err),
            )
            return jsonify({"error": "forbidden"}), 403
        except Exception:
            app.logger.exception("consolidation_read_probe_unexpected_error")
            _safe_log_consolidation_audit(
                action="read_probe",
                group_id=group_id,
                status="failed",
                code=500,
                operator_id=operator_id,
                payload=args,
                note="internal_error",
            )
            return jsonify({"ok": False, "error": "internal_error"}), 500

    @app.post("/api/consolidation/adjustments")
    def api_consolidation_adjustments_create():
        payload = request.get_json(silent=True) or {}
        operator_id = _get_operator_id(payload)
        group_id = None
        try:
            group_id = int(payload.get("consolidation_group_id") or payload.get("group_id"))
            if group_id <= 0:
                raise ValueError("consolidation_group_id_invalid")
            as_of = _period_to_as_of_date(str(payload.get("period") or "").strip())
            with get_connection_provider().connect() as conn:
                assert_virtual_authorized(conn, group_id, as_of)
            result = create_consolidation_adjustment(payload)
            _safe_log_consolidation_audit(
                action="adjustments_post",
                group_id=group_id,
                status="success",
                code=201,
                operator_id=operator_id,
                payload=payload,
                note="adjustment_created",
            )
            return jsonify({"ok": True, "item": result}), 201
        except ConsolidationAuthorizationError as err:
            _safe_log_consolidation_audit(
                action="adjustments_post",
                group_id=group_id,
                status="forbidden",
                code=403,
                operator_id=operator_id,
                payload=payload,
                note=str(err),
            )
            return jsonify({"error": "forbidden"}), 403
        except (TypeError, ValueError, ConsolidationAdjustmentError) as err:
            _safe_log_consolidation_audit(
                action="adjustments_post",
                group_id=group_id,
                status="failed",
                code=400,
                operator_id=operator_id,
                payload=payload,
                note=str(err),
            )
            return jsonify({"ok": False, "error": str(err)}), 400
        except Exception:
            app.logger.exception("consolidation_adjustments_create_unexpected_error")
            _safe_log_consolidation_audit(
                action="adjustments_post",
                group_id=group_id,
                status="failed",
                code=500,
                operator_id=operator_id,
                payload=payload,
                note="internal_error",
            )
            return jsonify({"ok": False, "error": "internal_error"}), 500

    @app.get("/api/consolidation/adjustments")
    def api_consolidation_adjustments_list():
        args = request.args.to_dict(flat=True)
        operator_id = _get_operator_id()
        group_id = None
        try:
            group_id = int(args.get("consolidation_group_id") or args.get("group_id"))
            if group_id <= 0:
                raise ValueError("consolidation_group_id_invalid")
            as_of = _period_to_as_of_date(str(args.get("period") or "").strip())
            with get_connection_provider().connect() as conn:
                assert_virtual_authorized(conn, group_id, as_of)
            result = list_consolidation_adjustments(args)
            _safe_log_consolidation_audit(
                action="adjustments_get",
                group_id=group_id,
                status="success",
                code=200,
                operator_id=operator_id,
                payload=args,
                note="adjustment_listed",
            )
            return jsonify({"ok": True, **result}), 200
        except ConsolidationAuthorizationError as err:
            _safe_log_consolidation_audit(
                action="adjustments_get",
                group_id=group_id,
                status="forbidden",
                code=403,
                operator_id=operator_id,
                payload=args,
                note=str(err),
            )
            return jsonify({"error": "forbidden"}), 403
        except (TypeError, ValueError, ConsolidationAdjustmentError) as err:
            _safe_log_consolidation_audit(
                action="adjustments_get",
                group_id=group_id,
                status="failed",
                code=400,
                operator_id=operator_id,
                payload=args,
                note=str(err),
            )
            return jsonify({"ok": False, "error": str(err)}), 400
        except Exception:
            app.logger.exception("consolidation_adjustments_list_unexpected_error")
            _safe_log_consolidation_audit(
                action="adjustments_get",
                group_id=group_id,
                status="failed",
                code=500,
                operator_id=operator_id,
                payload=args,
                note="internal_error",
            )
            return jsonify({"ok": False, "error": "internal_error"}), 500

    @app.get("/api/consolidation/adjustment_sets")
    def api_consolidation_adjustment_sets_list():
        args = request.args.to_dict(flat=True)
        operator_id = _get_operator_id()
        group_id = None
        try:
            group_id = int(args.get("consolidation_group_id") or args.get("group_id"))
            if group_id <= 0:
                raise ValueError("consolidation_group_id_invalid")
            as_of_raw = str(args.get("as_of") or "").strip()
            if as_of_raw:
                as_of = date.fromisoformat(as_of_raw)
            else:
                as_of = _period_to_as_of_date(str(args.get("period") or "").strip())
            with get_connection_provider().connect() as conn:
                assert_virtual_authorized(conn, group_id, as_of)
            result = list_consolidation_adjustment_sets(args)
            _safe_log_consolidation_audit(
                action="adjustment_sets_get",
                group_id=group_id,
                status="success",
                code=200,
                operator_id=operator_id,
                payload=args,
                note="adjustment_set_listed",
            )
            return jsonify({"ok": True, **result}), 200
        except ConsolidationAuthorizationError as err:
            _safe_log_consolidation_audit(
                action="adjustment_sets_get",
                group_id=group_id,
                status="forbidden",
                code=403,
                operator_id=operator_id,
                payload=args,
                note=str(err),
            )
            return jsonify({"error": "forbidden"}), 403
        except (TypeError, ValueError, ConsolidationAdjustmentError) as err:
            _safe_log_consolidation_audit(
                action="adjustment_sets_get",
                group_id=group_id,
                status="failed",
                code=400,
                operator_id=operator_id,
                payload=args,
                note=str(err),
            )
            return jsonify({"ok": False, "error": str(err)}), 400
        except Exception:
            app.logger.exception("consolidation_adjustment_sets_list_unexpected_error")
            _safe_log_consolidation_audit(
                action="adjustment_sets_get",
                group_id=group_id,
                status="failed",
                code=500,
                operator_id=operator_id,
                payload=args,
                note="internal_error",
            )
            return jsonify({"ok": False, "error": "internal_error"}), 500

    def _api_consolidation_adjustment_set_transition(set_id: str, action: str):
        payload = request.get_json(silent=True) or {}
        operator_id = _get_operator_id(payload) or 1
        group_id = None
        try:
            meta = get_adjustment_set_meta(set_id)
            group_id = int(meta.get("group_id") or 0)
            as_of = _period_to_as_of_date(str(meta.get("period") or ""))
            with get_connection_provider().connect() as conn:
                assert_virtual_authorized(conn, group_id, as_of)
            result = transition_adjustment_set_status(
                set_id,
                action=action,
                operator_id=operator_id,
                note=payload.get("note") or payload.get("reason") or "",
            )
            _safe_log_consolidation_audit(
                action=f"adjustment_set_{action}",
                group_id=group_id,
                status="success",
                code=200,
                operator_id=operator_id,
                payload={"set_id": set_id, **payload},
                note=f"status={result.get('status','')}",
            )
            return jsonify({"ok": True, "item": result}), 200
        except ConsolidationAuthorizationError as err:
            _safe_log_consolidation_audit(
                action=f"adjustment_set_{action}",
                group_id=group_id,
                status="forbidden",
                code=403,
                operator_id=operator_id,
                payload={"set_id": set_id, **payload},
                note=str(err),
            )
            return jsonify({"error": "forbidden"}), 403
        except ConsolidationAdjustmentError as err:
            msg = str(err)
            conflict_errors = {
                "adjustment_set_reviewed_blocked",
                "adjustment_set_locked_blocked",
                "adjustment_set_transition_invalid",
            }
            status_code = 409 if msg in conflict_errors else 400
            _safe_log_consolidation_audit(
                action=f"adjustment_set_{action}",
                group_id=group_id,
                status="failed",
                code=status_code,
                operator_id=operator_id,
                payload={"set_id": set_id, **payload},
                note=msg,
            )
            return jsonify({"ok": False, "error": msg}), status_code
        except Exception:
            app.logger.exception("consolidation_adjustment_set_transition_unexpected_error")
            _safe_log_consolidation_audit(
                action=f"adjustment_set_{action}",
                group_id=group_id,
                status="failed",
                code=500,
                operator_id=operator_id,
                payload={"set_id": set_id, **payload},
                note="internal_error",
            )
            return jsonify({"ok": False, "error": "internal_error"}), 500

    @app.post("/api/consolidation/adjustment_sets/<string:set_id>/review")
    def api_consolidation_adjustment_set_review(set_id: str):
        return _api_consolidation_adjustment_set_transition(set_id, "review")

    @app.post("/api/consolidation/adjustment_sets/<string:set_id>/lock")
    def api_consolidation_adjustment_set_lock(set_id: str):
        return _api_consolidation_adjustment_set_transition(set_id, "lock")

    @app.post("/api/consolidation/adjustment_sets/<string:set_id>/reopen")
    def api_consolidation_adjustment_set_reopen(set_id: str):
        return _api_consolidation_adjustment_set_transition(set_id, "reopen")

    @app.post("/api/consolidation/onboarding/ic_match")
    def api_consolidation_onboarding_ic_match():
        payload = request.get_json(silent=True) or {}
        operator_id = _get_operator_id(payload) or 1
        group_id = None
        try:
            group_id = int(payload.get("consolidation_group_id"))
            if group_id <= 0:
                raise ValueError("consolidation_group_id_invalid")
            as_of = date.fromisoformat(str(payload.get("as_of") or "").strip())
            with get_connection_provider().connect() as conn:
                assert_virtual_authorized(conn, group_id, as_of)
            result = run_onboarding_ic_match(group_id, as_of.isoformat(), operator_id=operator_id)
            _safe_log_consolidation_audit(
                action="onboarding_ic_match",
                group_id=group_id,
                status="success",
                code=200,
                operator_id=operator_id,
                payload=payload,
                note=f"matched={result.get('matched_count',0)} unmatched={result.get('unmatched_count',0)}",
            )
            return (
                jsonify(
                    {
                        "ok": True,
                        "set_id": result.get("set_id"),
                        "adjustment_set_id": result.get("set_id"),
                        "stats": {
                            "matched": result.get("matched_count", 0),
                            "unmatched": result.get("unmatched_count", 0),
                            "line_count": result.get("line_count", 0),
                        },
                        "preview_lines": result.get("draft_adjustment_lines") or [],
                        "matched_pairs": result.get("matched_pairs") or [],
                        "unmatched": result.get("unmatched") or [],
                        "unmatched_export_csv": result.get("unmatched_export_csv") or "",
                        "reused_existing_set": bool(result.get("reused_existing_set")),
                        "adjustment_id": result.get("adjustment_id"),
                    }
                ),
                200,
            )
        except ConsolidationAuthorizationError as err:
            _safe_log_consolidation_audit(
                action="onboarding_ic_match",
                group_id=group_id,
                status="forbidden",
                code=403,
                operator_id=operator_id,
                payload=payload,
                note=str(err),
            )
            return jsonify({"error": "forbidden"}), 403
        except (TypeError, ValueError, ConsolidationOnboardingIcMatchError, ConsolidationAdjustmentError) as err:
            msg = str(err)
            conflict_errors = {"adjustment_set_reviewed_blocked", "adjustment_set_locked_blocked"}
            status_code = 409 if msg in conflict_errors else 400
            _safe_log_consolidation_audit(
                action="onboarding_ic_match",
                group_id=group_id,
                status="failed",
                code=status_code,
                operator_id=operator_id,
                payload=payload,
                note=msg,
            )
            return jsonify({"ok": False, "error": msg}), status_code
        except Exception:
            app.logger.exception("consolidation_onboarding_ic_match_unexpected_error")
            _safe_log_consolidation_audit(
                action="onboarding_ic_match",
                group_id=group_id,
                status="failed",
                code=500,
                operator_id=operator_id,
                payload=payload,
                note="internal_error",
            )
            return jsonify({"ok": False, "error": "internal_error"}), 500

    @app.post("/api/consolidation/purchase_method/generate")
    def api_consolidation_purchase_method_generate():
        payload = request.get_json(silent=True) or {}
        operator_id = _get_operator_id(payload) or 1
        group_id = None
        try:
            group_id = int(payload.get("consolidation_group_id") or payload.get("group_id"))
            if group_id <= 0:
                raise ValueError("consolidation_group_id_invalid")
            as_of = date.fromisoformat(str(payload.get("acquisition_date") or "").strip())
            with get_connection_provider().connect() as conn:
                assert_virtual_authorized(conn, group_id, as_of)
            result = generate_purchase_method(payload, operator_id=operator_id)
            _safe_log_consolidation_audit(
                action="purchase_method_generate",
                group_id=group_id,
                status="success",
                code=200,
                operator_id=operator_id,
                payload=payload,
                note=f"set={result.get('adjustment_set_id','')}",
            )
            return (
                jsonify(
                    {
                        "ok": True,
                        "adjustment_set_id": result.get("adjustment_set_id"),
                        "counts": {"lines": int(result.get("line_count") or 0)},
                        "preview_lines": result.get("preview_lines") or [],
                        **result,
                    }
                ),
                200,
            )
        except ConsolidationAuthorizationError as err:
            _safe_log_consolidation_audit(
                action="purchase_method_generate",
                group_id=group_id,
                status="forbidden",
                code=403,
                operator_id=operator_id,
                payload=payload,
                note=str(err),
            )
            return jsonify({"error": "forbidden"}), 403
        except (TypeError, ValueError, ConsolidationPurchaseMethodError, ConsolidationAdjustmentError) as err:
            msg = str(err)
            status_code = 409 if msg in {"adjustment_set_reviewed_blocked", "adjustment_set_locked_blocked"} else 400
            _safe_log_consolidation_audit(
                action="purchase_method_generate",
                group_id=group_id,
                status="failed",
                code=status_code,
                operator_id=operator_id,
                payload=payload,
                note=msg,
            )
            return jsonify({"ok": False, "error": msg}), status_code
        except Exception:
            app.logger.exception("consolidation_purchase_method_generate_unexpected_error")
            _safe_log_consolidation_audit(
                action="purchase_method_generate",
                group_id=group_id,
                status="failed",
                code=500,
                operator_id=operator_id,
                payload=payload,
                note="internal_error",
            )
            return jsonify({"ok": False, "error": "internal_error"}), 500

    @app.post("/api/consolidation/eliminations/unrealized_profit/inventory/generate")
    def api_consolidation_inventory_up_generate():
        payload = request.get_json(silent=True) or {}
        operator_id = _get_operator_id(payload) or 1
        group_id = None
        try:
            group_id = int(payload.get("group_id") or payload.get("consolidation_group_id"))
            if group_id <= 0:
                raise ValueError("group_id_invalid")
            end_date = date.fromisoformat(str(payload.get("end_date") or "").strip())
            with get_connection_provider().connect() as conn:
                assert_virtual_authorized(conn, group_id, end_date)
            result = generate_inventory_unrealized_profit(payload, operator_id=operator_id)
            _safe_log_consolidation_audit(
                action="inventory_up_generate",
                group_id=group_id,
                status="success",
                code=200,
                operator_id=operator_id,
                payload=payload,
                note=f"set={result.get('adjustment_set_id','')}",
            )
            return jsonify({"ok": True, **result}), 200
        except ConsolidationAuthorizationError as err:
            _safe_log_consolidation_audit(
                action="inventory_up_generate",
                group_id=group_id,
                status="forbidden",
                code=403,
                operator_id=operator_id,
                payload=payload,
                note=str(err),
            )
            return jsonify({"error": "forbidden"}), 403
        except (TypeError, ValueError, ConsolidationUnrealizedProfitError, ConsolidationAdjustmentError) as err:
            msg = str(err)
            status_code = 409 if msg in {"adjustment_set_reviewed_blocked", "adjustment_set_locked_blocked"} else 400
            _safe_log_consolidation_audit(
                action="inventory_up_generate",
                group_id=group_id,
                status="failed",
                code=status_code,
                operator_id=operator_id,
                payload=payload,
                note=msg,
            )
            return jsonify({"ok": False, "error": msg}), status_code
        except Exception:
            app.logger.exception("consolidation_inventory_up_generate_unexpected_error")
            _safe_log_consolidation_audit(
                action="inventory_up_generate",
                group_id=group_id,
                status="failed",
                code=500,
                operator_id=operator_id,
                payload=payload,
                note="internal_error",
            )
            return jsonify({"ok": False, "error": "internal_error"}), 500

    @app.post("/api/consolidation/equity_method/generate")
    def api_consolidation_equity_method_generate():
        payload = request.get_json(silent=True) or {}
        operator_id = _get_operator_id(payload) or 1
        group_id = None
        try:
            group_id = int(payload.get("consolidation_group_id") or payload.get("group_id"))
            if group_id <= 0:
                raise ValueError("consolidation_group_id_invalid")
            as_of = date.fromisoformat(str(payload.get("as_of") or "").strip())
            with get_connection_provider().connect() as conn:
                assert_virtual_authorized(conn, group_id, as_of)
            result = generate_equity_method(payload, operator_id=operator_id)
            _safe_log_consolidation_audit(
                action="equity_method_generate",
                group_id=group_id,
                status="success",
                code=200,
                operator_id=operator_id,
                payload=payload,
                note=f"set={result.get('adjustment_set_id','')}",
            )
            return (
                jsonify(
                    {
                        "ok": True,
                        "adjustment_set_id": result.get("adjustment_set_id"),
                        "counts": {"lines": int(result.get("line_count") or 0)},
                        "preview_lines": result.get("preview_lines") or [],
                        **result,
                    }
                ),
                200,
            )
        except ConsolidationAuthorizationError as err:
            _safe_log_consolidation_audit(
                action="equity_method_generate",
                group_id=group_id,
                status="forbidden",
                code=403,
                operator_id=operator_id,
                payload=payload,
                note=str(err),
            )
            return jsonify({"error": "forbidden"}), 403
        except (TypeError, ValueError, ConsolidationEquityMethodError, ConsolidationAdjustmentError) as err:
            msg = str(err)
            status_code = 409 if msg in {"adjustment_set_reviewed_blocked", "adjustment_set_locked_blocked"} else 400
            _safe_log_consolidation_audit(
                action="equity_method_generate",
                group_id=group_id,
                status="failed",
                code=status_code,
                operator_id=operator_id,
                payload=payload,
                note=msg,
            )
            return jsonify({"ok": False, "error": msg}), status_code
        except Exception:
            app.logger.exception("consolidation_equity_method_generate_unexpected_error")
            _safe_log_consolidation_audit(
                action="equity_method_generate",
                group_id=group_id,
                status="failed",
                code=500,
                operator_id=operator_id,
                payload=payload,
                note="internal_error",
            )
            return jsonify({"ok": False, "error": "internal_error"}), 500

    @app.post("/task/cons-21")
    def api_task_cons_21():
        payload = request.get_json(silent=True) or {}
        operator_id = _get_operator_id(payload) or 1
        try:
            result = generate_equity_method(payload, operator_id=operator_id)
            return jsonify({"status": "success", "message": "权益法核算完成", **result}), 200
        except (TypeError, ValueError, ConsolidationEquityMethodError, ConsolidationAdjustmentError) as err:
            return jsonify({"status": "failed", "error": str(err)}), 400
        except Exception:
            app.logger.exception("task_cons_21_unexpected_error")
            return jsonify({"status": "failed", "error": "internal_error"}), 500

    @app.post("/task/cons-22")
    def api_task_cons_22():
        payload = request.get_json(silent=True) or {}
        operator_id = _get_operator_id(payload) or 1
        try:
            result = generate_nci_dynamic(payload, operator_id=operator_id)
            return jsonify({"status": "success", "message": "NCI动态计算完成", **result}), 200
        except (TypeError, ValueError, ConsolidationNciDynamicError, ConsolidationAdjustmentError) as err:
            return jsonify({"status": "failed", "error": str(err)}), 400
        except Exception:
            app.logger.exception("task_cons_22_unexpected_error")
            return jsonify({"status": "failed", "error": "internal_error"}), 500

    @app.post("/api/consolidation/rollover/generate")
    def api_consolidation_rollover_generate():
        payload = request.get_json(silent=True) or {}
        operator_id = _get_operator_id(payload) or 1
        group_id = None
        try:
            group_id = int(payload.get("consolidation_group_id") or payload.get("group_id"))
            if group_id <= 0:
                raise ValueError("consolidation_group_id_invalid")
            as_of = date.fromisoformat(str(payload.get("as_of") or "").strip()) if str(payload.get("as_of") or "").strip() else None
            if as_of is not None:
                with get_connection_provider().connect() as conn:
                    assert_virtual_authorized(conn, group_id, as_of)
            result = generate_multi_period_rollover(payload, operator_id=operator_id)
            _safe_log_consolidation_audit(
                action="multi_period_rollover_generate",
                group_id=group_id,
                status="success",
                code=200,
                operator_id=operator_id,
                payload=payload,
                note=f"to_period={result.get('to_period','')};sets={result.get('source_set_count',0)}",
            )
            return jsonify({"ok": True, **result}), 200
        except ConsolidationAuthorizationError as err:
            _safe_log_consolidation_audit(
                action="multi_period_rollover_generate",
                group_id=group_id,
                status="forbidden",
                code=403,
                operator_id=operator_id,
                payload=payload,
                note=str(err),
            )
            return jsonify({"error": "forbidden"}), 403
        except (TypeError, ValueError, ConsolidationMultiPeriodRolloverError, ConsolidationAdjustmentError) as err:
            msg = str(err)
            status_code = 409 if msg in {"adjustment_set_reviewed_blocked", "adjustment_set_locked_blocked"} else 400
            _safe_log_consolidation_audit(
                action="multi_period_rollover_generate",
                group_id=group_id,
                status="failed",
                code=status_code,
                operator_id=operator_id,
                payload=payload,
                note=msg,
            )
            return jsonify({"ok": False, "error": msg}), status_code
        except Exception:
            app.logger.exception("consolidation_multi_period_rollover_unexpected_error")
            _safe_log_consolidation_audit(
                action="multi_period_rollover_generate",
                group_id=group_id,
                status="failed",
                code=500,
                operator_id=operator_id,
                payload=payload,
                note="internal_error",
            )
            return jsonify({"ok": False, "error": "internal_error"}), 500

    @app.post("/task/cons-23")
    def api_task_cons_23():
        payload = request.get_json(silent=True) or {}
        operator_id = _get_operator_id(payload) or 1
        try:
            result = generate_multi_period_rollover(payload, operator_id=operator_id)
            return jsonify({"status": "success", "message": "多期滚动支持完成", **result}), 200
        except (TypeError, ValueError, ConsolidationMultiPeriodRolloverError, ConsolidationAdjustmentError) as err:
            return jsonify({"status": "failed", "error": str(err)}), 400
        except Exception:
            app.logger.exception("task_cons_23_unexpected_error")
            return jsonify({"status": "failed", "error": "internal_error"}), 500

    @app.post("/api/consolidation/merge_journal/generate")
    def api_consolidation_merge_journal_generate():
        payload = request.get_json(silent=True) or {}
        operator_id = _get_operator_id(payload) or 1
        group_id = None
        try:
            group_id = int(payload.get("consolidation_group_id") or payload.get("group_id"))
            if group_id <= 0:
                raise ValueError("consolidation_group_id_invalid")
            as_of = date.fromisoformat(str(payload.get("as_of") or "").strip()) if str(payload.get("as_of") or "").strip() else None
            if as_of is not None:
                with get_connection_provider().connect() as conn:
                    assert_virtual_authorized(conn, group_id, as_of)
            result = generate_merge_journal_and_post_merge_balance(payload, operator_id=operator_id)
            _safe_log_consolidation_audit(
                action="merge_journal_generate",
                group_id=group_id,
                status="success",
                code=200,
                operator_id=operator_id,
                payload=payload,
                note=f"set={result.get('adjustment_set_id','')}",
            )
            return jsonify({"ok": True, **result}), 200
        except ConsolidationAuthorizationError as err:
            _safe_log_consolidation_audit(
                action="merge_journal_generate",
                group_id=group_id,
                status="forbidden",
                code=403,
                operator_id=operator_id,
                payload=payload,
                note=str(err),
            )
            return jsonify({"error": "forbidden"}), 403
        except (TypeError, ValueError, ConsolidationMergeJournalError, ConsolidationAdjustmentError) as err:
            msg = str(err)
            status_code = 409 if msg in {"adjustment_set_reviewed_blocked", "adjustment_set_locked_blocked"} else 400
            _safe_log_consolidation_audit(
                action="merge_journal_generate",
                group_id=group_id,
                status="failed",
                code=status_code,
                operator_id=operator_id,
                payload=payload,
                note=msg,
            )
            return jsonify({"ok": False, "error": msg}), status_code
        except Exception:
            app.logger.exception("consolidation_merge_journal_generate_unexpected_error")
            _safe_log_consolidation_audit(
                action="merge_journal_generate",
                group_id=group_id,
                status="failed",
                code=500,
                operator_id=operator_id,
                payload=payload,
                note="internal_error",
            )
            return jsonify({"ok": False, "error": "internal_error"}), 500

    @app.post("/task/cons-24")
    def api_task_cons_24():
        payload = request.get_json(silent=True) or {}
        operator_id = _get_operator_id(payload) or 1
        try:
            result = generate_merge_journal_and_post_merge_balance(payload, operator_id=operator_id)
            return jsonify({"status": "success", "message": "合并作业单与合并后余额层完成", **result}), 200
        except (TypeError, ValueError, ConsolidationMergeJournalError, ConsolidationAdjustmentError) as err:
            return jsonify({"status": "failed", "error": str(err)}), 400
        except Exception:
            app.logger.exception("task_cons_24_unexpected_error")
            return jsonify({"status": "failed", "error": "internal_error"}), 500

    @app.post("/api/consolidation/reports/generate")
    def api_consolidation_reports_generate():
        payload = request.get_json(silent=True) or {}
        operator_id = _get_operator_id(payload) or 1
        group_id = None
        try:
            group_id = int(payload.get("consolidation_group_id") or payload.get("group_id"))
            if group_id <= 0:
                raise ValueError("consolidation_group_id_invalid")
            as_of = date.fromisoformat(str(payload.get("as_of") or "").strip()) if str(payload.get("as_of") or "").strip() else None
            if as_of is not None:
                with get_connection_provider().connect() as conn:
                    assert_virtual_authorized(conn, group_id, as_of)
            result = generate_report_templates_and_merge_reports(payload, operator_id=operator_id)
            _safe_log_consolidation_audit(
                action="consolidation_reports_generate",
                group_id=group_id,
                status="success",
                code=200,
                operator_id=operator_id,
                payload=payload,
                note=f"batch={result.get('batch_id','')}",
            )
            return jsonify({"ok": True, **result}), 200
        except ConsolidationAuthorizationError as err:
            _safe_log_consolidation_audit(
                action="consolidation_reports_generate",
                group_id=group_id,
                status="forbidden",
                code=403,
                operator_id=operator_id,
                payload=payload,
                note=str(err),
            )
            return jsonify({"error": "forbidden"}), 403
        except (TypeError, ValueError, ConsolidationReportGenerationError) as err:
            _safe_log_consolidation_audit(
                action="consolidation_reports_generate",
                group_id=group_id,
                status="failed",
                code=400,
                operator_id=operator_id,
                payload=payload,
                note=str(err),
            )
            return jsonify({"ok": False, "error": str(err)}), 400
        except Exception:
            app.logger.exception("consolidation_reports_generate_unexpected_error")
            _safe_log_consolidation_audit(
                action="consolidation_reports_generate",
                group_id=group_id,
                status="failed",
                code=500,
                operator_id=operator_id,
                payload=payload,
                note="internal_error",
            )
            return jsonify({"ok": False, "error": "internal_error"}), 500

    @app.post("/task/cons-25")
    def api_task_cons_25():
        payload = request.get_json(silent=True) or {}
        operator_id = _get_operator_id(payload) or 1
        try:
            result = generate_report_templates_and_merge_reports(payload, operator_id=operator_id)
            return jsonify({"status": "success", "message": "报表模板与合并报表生成完成", **result}), 200
        except (TypeError, ValueError, ConsolidationReportGenerationError) as err:
            return jsonify({"status": "failed", "error": str(err)}), 400
        except Exception:
            app.logger.exception("task_cons_25_unexpected_error")
            return jsonify({"status": "failed", "error": "internal_error"}), 500

    @app.post("/api/consolidation/audit-permission/check")
    def api_consolidation_audit_permission_check():
        payload = request.get_json(silent=True) or {}
        operator_id = _get_operator_id(payload) or 1
        group_id = None
        try:
            group_id = int(payload.get("consolidation_group_id") or payload.get("group_id"))
            if group_id <= 0:
                raise ValueError("consolidation_group_id_invalid")
            result = run_audit_logs_and_permission_control(payload, operator_id=operator_id)
            permission_granted = bool(result.get("permission_granted"))
            status_code = 200 if permission_granted else 403
            _safe_log_consolidation_audit(
                action="cons26_audit_permission_check",
                group_id=group_id,
                status="success" if permission_granted else "forbidden",
                code=status_code,
                operator_id=operator_id,
                payload=payload,
                note=f"log_id={((result.get('audit_log') or {}).get('id') or 0)}",
            )
            return jsonify({"ok": permission_granted, **result}), status_code
        except (TypeError, ValueError, ConsolidationAuditPermissionError) as err:
            msg = str(err)
            _safe_log_consolidation_audit(
                action="cons26_audit_permission_check",
                group_id=group_id,
                status="failed",
                code=400,
                operator_id=operator_id,
                payload=payload,
                note=msg,
            )
            return jsonify({"ok": False, "error": msg}), 400
        except Exception:
            app.logger.exception("consolidation_audit_permission_check_unexpected_error")
            _safe_log_consolidation_audit(
                action="cons26_audit_permission_check",
                group_id=group_id,
                status="failed",
                code=500,
                operator_id=operator_id,
                payload=payload,
                note="internal_error",
            )
            return jsonify({"ok": False, "error": "internal_error"}), 500

    @app.post("/task/cons-26")
    def api_task_cons_26():
        payload = request.get_json(silent=True) or {}
        operator_id = _get_operator_id(payload) or 1
        try:
            result = run_audit_logs_and_permission_control(payload, operator_id=operator_id)
            permission_granted = bool(result.get("permission_granted"))
            status_code = 200 if permission_granted else 403
            body = {
                "status": "success" if permission_granted else "failed",
                "message": "审计日志与权限控制检查完成" if permission_granted else "权限校验未通过",
                **result,
            }
            return jsonify(body), status_code
        except (TypeError, ValueError, ConsolidationAuditPermissionError) as err:
            return jsonify({"status": "failed", "error": str(err)}), 400
        except Exception:
            app.logger.exception("task_cons_26_unexpected_error")
            return jsonify({"status": "failed", "error": "internal_error"}), 500

    @app.post("/api/consolidation/scope-criteria/configure")
    def api_consolidation_scope_criteria_configure():
        payload = request.get_json(silent=True) or {}
        operator_id = _get_operator_id(payload) or 1
        group_id = None
        try:
            group_id = int(payload.get("consolidation_group_id") or payload.get("group_id"))
            if group_id <= 0:
                raise ValueError("consolidation_group_id_invalid")
            result = configure_merger_scope_and_criteria(payload, operator_id=operator_id)
            _safe_log_consolidation_audit(
                action="cons27_scope_criteria_configure",
                group_id=group_id,
                status="success",
                code=200,
                operator_id=operator_id,
                payload=payload,
                note="scope_and_criteria_configured",
            )
            return jsonify({"ok": True, **result}), 200
        except (TypeError, ValueError, ConsolidationScopeCriteriaError) as err:
            _safe_log_consolidation_audit(
                action="cons27_scope_criteria_configure",
                group_id=group_id,
                status="failed",
                code=400,
                operator_id=operator_id,
                payload=payload,
                note=str(err),
            )
            return jsonify({"ok": False, "error": str(err)}), 400
        except Exception:
            app.logger.exception("consolidation_scope_criteria_configure_unexpected_error")
            _safe_log_consolidation_audit(
                action="cons27_scope_criteria_configure",
                group_id=group_id,
                status="failed",
                code=500,
                operator_id=operator_id,
                payload=payload,
                note="internal_error",
            )
            return jsonify({"ok": False, "error": "internal_error"}), 500

    @app.post("/task/cons-27")
    def api_task_cons_27():
        payload = request.get_json(silent=True) or {}
        operator_id = _get_operator_id(payload) or 1
        try:
            result = configure_merger_scope_and_criteria(payload, operator_id=operator_id)
            return jsonify({"status": "success", "message": "合并范围与口径配置完成", **result}), 200
        except (TypeError, ValueError, ConsolidationScopeCriteriaError) as err:
            return jsonify({"status": "failed", "error": str(err)}), 400
        except Exception:
            app.logger.exception("task_cons_27_unexpected_error")
            return jsonify({"status": "failed", "error": "internal_error"}), 500

    @app.post("/api/consolidation/reports/automate")
    def api_consolidation_reports_automate():
        payload = request.get_json(silent=True) or {}
        operator_id = _get_operator_id(payload) or 1
        group_id = None
        try:
            group_id = int(payload.get("consolidation_group_id") or payload.get("group_id"))
            if group_id <= 0:
                raise ValueError("consolidation_group_id_invalid")
            result = automate_report_generation_and_adjustment(payload, operator_id=operator_id)
            _safe_log_consolidation_audit(
                action="cons28_reports_automate",
                group_id=group_id,
                status="success",
                code=200,
                operator_id=operator_id,
                payload=payload,
                note=f"delta={result.get('delta_after_adjustment', 0)}",
            )
            return jsonify({"ok": True, **result}), 200
        except (TypeError, ValueError, ConsolidationReportAutomationError) as err:
            _safe_log_consolidation_audit(
                action="cons28_reports_automate",
                group_id=group_id,
                status="failed",
                code=400,
                operator_id=operator_id,
                payload=payload,
                note=str(err),
            )
            return jsonify({"ok": False, "error": str(err)}), 400
        except Exception:
            app.logger.exception("consolidation_reports_automate_unexpected_error")
            _safe_log_consolidation_audit(
                action="cons28_reports_automate",
                group_id=group_id,
                status="failed",
                code=500,
                operator_id=operator_id,
                payload=payload,
                note="internal_error",
            )
            return jsonify({"ok": False, "error": "internal_error"}), 500

    @app.post("/task/cons-28")
    def api_task_cons_28():
        payload = request.get_json(silent=True) or {}
        operator_id = _get_operator_id(payload) or 1
        try:
            result = automate_report_generation_and_adjustment(payload, operator_id=operator_id)
            return jsonify({"status": "success", "message": "合并报表自动化生成与调节完成", **result}), 200
        except (TypeError, ValueError, ConsolidationReportAutomationError) as err:
            return jsonify({"status": "failed", "error": str(err)}), 400
        except Exception:
            app.logger.exception("task_cons_28_unexpected_error")
            return jsonify({"status": "failed", "error": "internal_error"}), 500

    @app.post("/api/consolidation/final_check_approval/run")
    def api_consolidation_final_check_approval_run():
        payload = request.get_json(silent=True) or {}
        operator_id = _get_operator_id(payload) or 1
        group_id = None
        try:
            group_id = int(payload.get("consolidation_group_id") or payload.get("group_id"))
            if group_id <= 0:
                raise ValueError("consolidation_group_id_invalid")
            result = run_final_check_and_approval_flow(payload, operator_id=operator_id)
            status_code = 200 if bool(result.get("final_check_passed")) else 409
            _safe_log_consolidation_audit(
                action="cons29_final_check_approval",
                group_id=group_id,
                status="success" if status_code == 200 else "failed",
                code=status_code,
                operator_id=operator_id,
                payload=payload,
                note=f"approval_status={((result.get('approval_flow') or {}).get('approval_status') or '')}",
            )
            return jsonify({"ok": status_code == 200, **result}), status_code
        except (TypeError, ValueError, ConsolidationFinalCheckApprovalError) as err:
            _safe_log_consolidation_audit(
                action="cons29_final_check_approval",
                group_id=group_id,
                status="failed",
                code=400,
                operator_id=operator_id,
                payload=payload,
                note=str(err),
            )
            return jsonify({"ok": False, "error": str(err)}), 400
        except Exception:
            app.logger.exception("consolidation_final_check_approval_unexpected_error")
            _safe_log_consolidation_audit(
                action="cons29_final_check_approval",
                group_id=group_id,
                status="failed",
                code=500,
                operator_id=operator_id,
                payload=payload,
                note="internal_error",
            )
            return jsonify({"ok": False, "error": "internal_error"}), 500

    @app.post("/task/cons-29")
    def api_task_cons_29():
        payload = request.get_json(silent=True) or {}
        operator_id = _get_operator_id(payload) or 1
        try:
            result = run_final_check_and_approval_flow(payload, operator_id=operator_id)
            check_ok = bool(result.get("final_check_passed"))
            return (
                jsonify(
                    {
                        "status": "success" if check_ok else "failed",
                        "message": "合并作业单与合并报表最终校验与审批流完成" if check_ok else "最终校验未通过",
                        **result,
                    }
                ),
                200 if check_ok else 409,
            )
        except (TypeError, ValueError, ConsolidationFinalCheckApprovalError) as err:
            return jsonify({"status": "failed", "error": str(err)}), 400
        except Exception:
            app.logger.exception("task_cons_29_unexpected_error")
            return jsonify({"status": "failed", "error": "internal_error"}), 500

    @app.post("/api/consolidation/disclosure-audit-package/generate")
    def api_consolidation_disclosure_audit_package_generate():
        payload = request.get_json(silent=True) or {}
        operator_id = _get_operator_id(payload) or 1
        group_id = None
        try:
            group_id = int(payload.get("consolidation_group_id") or payload.get("group_id"))
            if group_id <= 0:
                raise ValueError("consolidation_group_id_invalid")
            result = generate_disclosure_and_audit_package(payload, operator_id=operator_id)
            _safe_log_consolidation_audit(
                action="cons30_disclosure_audit_package_generate",
                group_id=group_id,
                status="success",
                code=200,
                operator_id=operator_id,
                payload=payload,
                note=f"package_id={result.get('package_id', 0)}",
            )
            return jsonify({"ok": True, **result}), 200
        except (TypeError, ValueError, ConsolidationDisclosureAuditPackageError) as err:
            _safe_log_consolidation_audit(
                action="cons30_disclosure_audit_package_generate",
                group_id=group_id,
                status="failed",
                code=400,
                operator_id=operator_id,
                payload=payload,
                note=str(err),
            )
            return jsonify({"ok": False, "error": str(err)}), 400
        except Exception:
            app.logger.exception("consolidation_disclosure_audit_package_generate_unexpected_error")
            _safe_log_consolidation_audit(
                action="cons30_disclosure_audit_package_generate",
                group_id=group_id,
                status="failed",
                code=500,
                operator_id=operator_id,
                payload=payload,
                note="internal_error",
            )
            return jsonify({"ok": False, "error": "internal_error"}), 500

    @app.post("/task/cons-30")
    def api_task_cons_30():
        payload = request.get_json(silent=True) or {}
        operator_id = _get_operator_id(payload) or 1
        try:
            result = generate_disclosure_and_audit_package(payload, operator_id=operator_id)
            return jsonify({"status": "success", "message": "报表披露与审计包生成完成", **result}), 200
        except (TypeError, ValueError, ConsolidationDisclosureAuditPackageError) as err:
            return jsonify({"status": "failed", "error": str(err)}), 400
        except Exception:
            app.logger.exception("task_cons_30_unexpected_error")
            return jsonify({"status": "failed", "error": "internal_error"}), 500

    @app.post("/api/consolidation/eliminations/unrealized_profit/inventory/reversal/generate")
    def api_consolidation_inventory_up_reversal_generate():
        payload = request.get_json(silent=True) or {}
        operator_id = _get_operator_id(payload) or 1
        group_id = None
        try:
            group_id = int(payload.get("group_id") or payload.get("consolidation_group_id"))
            if group_id <= 0:
                raise ValueError("group_id_invalid")
            end_date = date.fromisoformat(str(payload.get("end_date") or "").strip())
            with get_connection_provider().connect() as conn:
                assert_virtual_authorized(conn, group_id, end_date)
            result = generate_inventory_unrealized_profit_reversal(payload, operator_id=operator_id)
            _safe_log_consolidation_audit(
                action="inventory_up_reversal_generate",
                group_id=group_id,
                status="success",
                code=200,
                operator_id=operator_id,
                payload=payload,
                note=f"set={result.get('adjustment_set_id','')}",
            )
            return jsonify({"ok": True, **result}), 200
        except ConsolidationAuthorizationError as err:
            _safe_log_consolidation_audit(
                action="inventory_up_reversal_generate",
                group_id=group_id,
                status="forbidden",
                code=403,
                operator_id=operator_id,
                payload=payload,
                note=str(err),
            )
            return jsonify({"error": "forbidden"}), 403
        except (TypeError, ValueError, ConsolidationUnrealizedProfitReversalError, ConsolidationAdjustmentError) as err:
            msg = str(err)
            status_code = 409 if msg in {"adjustment_set_reviewed_blocked", "adjustment_set_locked_blocked"} else 400
            _safe_log_consolidation_audit(
                action="inventory_up_reversal_generate",
                group_id=group_id,
                status="failed",
                code=status_code,
                operator_id=operator_id,
                payload=payload,
                note=msg,
            )
            return jsonify({"ok": False, "error": msg}), status_code
        except Exception:
            app.logger.exception("consolidation_inventory_up_reversal_generate_unexpected_error")
            _safe_log_consolidation_audit(
                action="inventory_up_reversal_generate",
                group_id=group_id,
                status="failed",
                code=500,
                operator_id=operator_id,
                payload=payload,
                note="internal_error",
            )
            return jsonify({"ok": False, "error": "internal_error"}), 500

    @app.post("/api/consolidation/eliminations/ic_asset_transfer/generate")
    def api_consolidation_ic_asset_transfer_generate():
        payload = request.get_json(silent=True) or {}
        operator_id = _get_operator_id(payload) or 1
        group_id = None
        try:
            group_id = int(payload.get("group_id") or payload.get("consolidation_group_id"))
            if group_id <= 0:
                raise ValueError("group_id_invalid")
            as_of = date.fromisoformat(str(payload.get("as_of") or payload.get("as_of_date") or "").strip())
            with get_connection_provider().connect() as conn:
                assert_virtual_authorized(conn, group_id, as_of)
            result = generate_ic_asset_transfer_onboard(payload, operator_id=operator_id)
            _safe_log_consolidation_audit(
                action="ic_asset_transfer_generate",
                group_id=group_id,
                status="success",
                code=200,
                operator_id=operator_id,
                payload=payload,
                note=f"set={result.get('adjustment_set_id','')}",
            )
            return jsonify({"ok": True, **result}), 200
        except ConsolidationAuthorizationError as err:
            _safe_log_consolidation_audit(
                action="ic_asset_transfer_generate",
                group_id=group_id,
                status="forbidden",
                code=403,
                operator_id=operator_id,
                payload=payload,
                note=str(err),
            )
            return jsonify({"error": "forbidden"}), 403
        except (TypeError, ValueError, ConsolidationIcAssetTransferError, ConsolidationAdjustmentError) as err:
            msg = str(err)
            status_code = 409 if msg in {"adjustment_set_reviewed_blocked", "adjustment_set_locked_blocked"} else 400
            _safe_log_consolidation_audit(
                action="ic_asset_transfer_generate",
                group_id=group_id,
                status="failed",
                code=status_code,
                operator_id=operator_id,
                payload=payload,
                note=msg,
            )
            return jsonify({"ok": False, "error": msg}), status_code
        except Exception:
            app.logger.exception("consolidation_ic_asset_transfer_generate_unexpected_error")
            _safe_log_consolidation_audit(
                action="ic_asset_transfer_generate",
                group_id=group_id,
                status="failed",
                code=500,
                operator_id=operator_id,
                payload=payload,
                note="internal_error",
            )
            return jsonify({"ok": False, "error": "internal_error"}), 500

    @app.post("/api/consolidation/ownership")
    def api_consolidation_ownership_create():
        payload = request.get_json(silent=True) or {}
        operator_id = _get_operator_id(payload)
        group_id = None
        try:
            group_id = int(payload.get("consolidation_group_id") or payload.get("group_id"))
            if group_id <= 0:
                raise ValueError("consolidation_group_id_invalid")
            as_of_raw = str(payload.get("effective_from") or "").strip()
            as_of = date.fromisoformat(as_of_raw) if as_of_raw else date.today()
            with get_connection_provider().connect() as conn:
                assert_virtual_authorized(conn, group_id, as_of)
            result = create_consolidation_ownership(payload)
            _safe_log_consolidation_audit(
                action="ownership_post",
                group_id=group_id,
                status="success",
                code=201,
                operator_id=operator_id,
                payload=payload,
                note="ownership_created",
            )
            return jsonify({"ok": True, "item": result}), 201
        except ConsolidationAuthorizationError as err:
            _safe_log_consolidation_audit(
                action="ownership_post",
                group_id=group_id,
                status="forbidden",
                code=403,
                operator_id=operator_id,
                payload=payload,
                note=str(err),
            )
            return jsonify({"error": "forbidden"}), 403
        except (TypeError, ValueError, ConsolidationOwnershipError) as err:
            _safe_log_consolidation_audit(
                action="ownership_post",
                group_id=group_id,
                status="failed",
                code=400,
                operator_id=operator_id,
                payload=payload,
                note=str(err),
            )
            return jsonify({"ok": False, "error": str(err)}), 400
        except Exception:
            app.logger.exception("consolidation_ownership_create_unexpected_error")
            _safe_log_consolidation_audit(
                action="ownership_post",
                group_id=group_id,
                status="failed",
                code=500,
                operator_id=operator_id,
                payload=payload,
                note="internal_error",
            )
            return jsonify({"ok": False, "error": "internal_error"}), 500

    @app.get("/api/consolidation/ownership")
    def api_consolidation_ownership_list():
        args = request.args.to_dict(flat=True)
        operator_id = _get_operator_id()
        group_id = None
        try:
            group_id = int(args.get("consolidation_group_id") or args.get("group_id"))
            if group_id <= 0:
                raise ValueError("consolidation_group_id_invalid")
            as_of = date.fromisoformat(str(args.get("as_of") or "").strip())
            with get_connection_provider().connect() as conn:
                assert_virtual_authorized(conn, group_id, as_of)
            result = list_consolidation_ownership(args)
            _safe_log_consolidation_audit(
                action="ownership_get",
                group_id=group_id,
                status="success",
                code=200,
                operator_id=operator_id,
                payload=args,
                note="ownership_listed",
            )
            return jsonify({"ok": True, **result}), 200
        except ConsolidationAuthorizationError as err:
            _safe_log_consolidation_audit(
                action="ownership_get",
                group_id=group_id,
                status="forbidden",
                code=403,
                operator_id=operator_id,
                payload=args,
                note=str(err),
            )
            return jsonify({"error": "forbidden"}), 403
        except (TypeError, ValueError, ConsolidationOwnershipError) as err:
            _safe_log_consolidation_audit(
                action="ownership_get",
                group_id=group_id,
                status="failed",
                code=400,
                operator_id=operator_id,
                payload=args,
                note=str(err),
            )
            return jsonify({"ok": False, "error": str(err)}), 400
        except Exception:
            app.logger.exception("consolidation_ownership_list_unexpected_error")
            _safe_log_consolidation_audit(
                action="ownership_get",
                group_id=group_id,
                status="failed",
                code=500,
                operator_id=operator_id,
                payload=args,
                note="internal_error",
            )
            return jsonify({"ok": False, "error": "internal_error"}), 500

    @app.get("/api/consolidation/control_decision")
    def api_consolidation_control_decision():
        args = request.args.to_dict(flat=True)
        group_id = None
        try:
            group_id = int(args.get("consolidation_group_id"))
            if group_id <= 0:
                raise ValueError("consolidation_group_id_invalid")
            as_of = date.fromisoformat(str(args.get("as_of") or "").strip())
            with get_connection_provider().connect() as conn:
                assert_virtual_authorized(conn, group_id, as_of)
            result = get_consolidation_control_decision(group_id, as_of.isoformat())
            return jsonify({"ok": True, **result}), 200
        except ConsolidationAuthorizationError:
            return jsonify({"error": "forbidden"}), 403
        except (TypeError, ValueError, ConsolidationControlError) as err:
            return jsonify({"ok": False, "error": str(err)}), 400
        except Exception:
            app.logger.exception("consolidation_control_decision_unexpected_error")
            return jsonify({"ok": False, "error": "internal_error"}), 500

    @app.get("/api/consolidation/nci")
    def api_consolidation_nci():
        args = request.args.to_dict(flat=True)
        try:
            group_id = int(args.get("consolidation_group_id"))
            if group_id <= 0:
                raise ValueError("consolidation_group_id_invalid")
            as_of = date.fromisoformat(str(args.get("as_of") or "").strip())
            with get_connection_provider().connect() as conn:
                assert_virtual_authorized(conn, group_id, as_of)
            result = get_consolidation_nci(group_id, as_of.isoformat())
            return jsonify({"ok": True, **result}), 200
        except ConsolidationAuthorizationError:
            return jsonify({"error": "forbidden"}), 403
        except (TypeError, ValueError, ConsolidationNciError) as err:
            return jsonify({"ok": False, "error": str(err)}), 400
        except Exception:
            app.logger.exception("consolidation_nci_unexpected_error")
            return jsonify({"ok": False, "error": "internal_error"}), 500

    @app.post("/api/consolidation/nci/generate")
    def api_consolidation_nci_generate():
        payload = request.get_json(silent=True) or {}
        operator_id = _get_operator_id(payload) or 1
        group_id = None
        try:
            group_id = int(payload.get("consolidation_group_id") or payload.get("group_id"))
            if group_id <= 0:
                raise ValueError("consolidation_group_id_invalid")
            as_of = date.fromisoformat(str(payload.get("as_of") or "").strip())
            with get_connection_provider().connect() as conn:
                assert_virtual_authorized(conn, group_id, as_of)
            result = generate_nci_dynamic(payload, operator_id=operator_id)
            _safe_log_consolidation_audit(
                action="nci_dynamic_generate",
                group_id=group_id,
                status="success",
                code=200,
                operator_id=operator_id,
                payload=payload,
                note=f"set={result.get('adjustment_set_id','')}",
            )
            return (
                jsonify(
                    {
                        "ok": True,
                        "adjustment_set_id": result.get("adjustment_set_id"),
                        "counts": {"lines": int(result.get("line_count") or 0)},
                        "preview_lines": result.get("preview_lines") or [],
                        **result,
                    }
                ),
                200,
            )
        except ConsolidationAuthorizationError as err:
            _safe_log_consolidation_audit(
                action="nci_dynamic_generate",
                group_id=group_id,
                status="forbidden",
                code=403,
                operator_id=operator_id,
                payload=payload,
                note=str(err),
            )
            return jsonify({"error": "forbidden"}), 403
        except (TypeError, ValueError, ConsolidationNciDynamicError, ConsolidationAdjustmentError) as err:
            msg = str(err)
            status_code = 409 if msg in {"adjustment_set_reviewed_blocked", "adjustment_set_locked_blocked"} else 400
            _safe_log_consolidation_audit(
                action="nci_dynamic_generate",
                group_id=group_id,
                status="failed",
                code=status_code,
                operator_id=operator_id,
                payload=payload,
                note=msg,
            )
            return jsonify({"ok": False, "error": msg}), status_code
        except Exception:
            app.logger.exception("consolidation_nci_dynamic_generate_unexpected_error")
            _safe_log_consolidation_audit(
                action="nci_dynamic_generate",
                group_id=group_id,
                status="failed",
                code=500,
                operator_id=operator_id,
                payload=payload,
                note="internal_error",
            )
            return jsonify({"ok": False, "error": "internal_error"}), 500

    @app.get("/api/consolidation/groups/<int:group_id>/members/effective")
    def api_get_consolidation_group_members_effective(group_id: int):
        try:
            result = get_effective_group_members(group_id, request.args)
            return jsonify(result), 200
        except ConsolidationError as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("consolidation_group_member_effective_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.get("/api/consolidation/relations/overview")
    def api_consolidation_relations_overview():
        try:
            result = list_relation_overview(request.args.to_dict(flat=True))
            return jsonify(result), 200
        except ConsolidationManageError as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("consolidation_relations_overview_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.get("/api/consolidation/parameters")
    def api_consolidation_parameters():
        group_id_raw = str(request.args.get("consolidation_group_id") or "").strip()
        group_code = str(request.args.get("group_code") or "").strip()
        tenant_id = str(request.args.get("tenant_id") or "").strip() or None
        try:
            if not group_id_raw and not group_code:
                return (
                    jsonify(
                        {
                            "ok": True,
                            "items": [],
                            "version": "cons-params-v1",
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "message": "未指定合并组/返回空",
                        }
                    ),
                    200,
                )
            with get_connection_provider().connect(tenant_id=tenant_id) as conn:
                if group_id_raw:
                    if not group_id_raw.isdigit():
                        raise ConsolidationParameterError("consolidation_group_id_invalid")
                    gid = int(group_id_raw)
                elif group_code:
                    row = conn.execute(
                        text(
                            """
                            SELECT id
                            FROM consolidation_groups
                            WHERE group_code=:group_code
                            ORDER BY id DESC
                            LIMIT 1
                            """
                        ),
                        {"group_code": group_code},
                    ).fetchone()
                    if not row:
                        raise ConsolidationParameterError("group_code_not_found")
                    gid = int(row.id)
                else:
                    raise ConsolidationParameterError("consolidation_group_id_or_group_code_required")
                assert_virtual_authorized(conn, gid, date.today())
            result = list_consolidation_parameters_contract(gid, tenant_id=tenant_id)
            return (
                jsonify(
                    {
                        "ok": True,
                        "items": result.get("items") or [],
                        "version": "cons-params-v1",
                        "ts": datetime.now(timezone.utc).isoformat(),
                    }
                ),
                200,
            )
        except ConsolidationAuthorizationError:
            return jsonify({"error": "forbidden"}), 403
        except ValueError:
            return jsonify({"ok": False, "error": "consolidation_group_id_invalid"}), 400
        except ConsolidationParameterError as err:
            return jsonify({"ok": False, "error": str(err)}), 400
        except Exception:
            app.logger.exception("consolidation_parameters_unexpected_error")
            return jsonify({"ok": False, "error": "consolidation_parameters_invalid"}), 400

    @app.put("/api/consolidation/parameters")
    def api_upsert_consolidation_parameters():
        payload = request.get_json(silent=True) or {}
        tenant_id = str(payload.get("tenant_id") or "").strip() or None
        try:
            with get_connection_provider().connect(tenant_id=tenant_id) as conn:
                gid_raw = str(payload.get("consolidation_group_id") or "").strip()
                group_code = str(payload.get("group_code") or "").strip()
                if gid_raw:
                    gid = int(gid_raw)
                elif group_code:
                    row = conn.execute(
                        text(
                            """
                            SELECT id
                            FROM consolidation_groups
                            WHERE group_code=:group_code
                            ORDER BY id DESC
                            LIMIT 1
                            """
                        ),
                        {"group_code": group_code},
                    ).fetchone()
                    if not row:
                        raise ConsolidationParameterError("group_code_not_found")
                    gid = int(row.id)
                    payload["consolidation_group_id"] = gid
                else:
                    raise ConsolidationParameterError("consolidation_group_id_or_group_code_required")
                assert_virtual_authorized(conn, gid, date.today())
            result = upsert_consolidation_parameters_contract(payload, tenant_id=tenant_id)
            return (
                jsonify(
                    {
                        "ok": True,
                        "item": result.get("item") or {},
                        "version": "cons-params-v1",
                        "ts": datetime.now(timezone.utc).isoformat(),
                    }
                ),
                200,
            )
        except ConsolidationAuthorizationError:
            return jsonify({"error": "forbidden"}), 403
        except ValueError:
            return jsonify({"ok": False, "error": "consolidation_group_id_invalid"}), 400
        except ConsolidationParameterError as err:
            return jsonify({"ok": False, "error": str(err)}), 400
        except Exception:
            app.logger.exception("consolidation_parameters_upsert_unexpected_error")
            return jsonify({"ok": False, "error": "consolidation_parameters_invalid"}), 400

    @app.get("/api/consolidation/type")
    def api_consolidation_type_get():
        args = request.args.to_dict(flat=True)
        operator_id = _get_operator_id()
        group_id = None
        try:
            group_id = int(args.get("group_id") or args.get("consolidation_group_id"))
            if group_id <= 0:
                raise ValueError("group_id_invalid")
            with get_connection_provider().connect() as conn:
                assert_virtual_authorized(conn, group_id, date.today())
            item = get_type(group_id)
            _safe_log_consolidation_audit(
                action="type_get",
                group_id=group_id,
                status="success",
                code=200,
                operator_id=operator_id,
                payload=args,
                note="type_loaded",
            )
            return jsonify({"ok": True, "item": item}), 200
        except ConsolidationAuthorizationError as err:
            _safe_log_consolidation_audit(
                action="type_get",
                group_id=group_id,
                status="forbidden",
                code=403,
                operator_id=operator_id,
                payload=args,
                note=str(err),
            )
            return jsonify({"error": "forbidden"}), 403
        except (TypeError, ValueError, ConsolidationTypeError) as err:
            _safe_log_consolidation_audit(
                action="type_get",
                group_id=group_id,
                status="failed",
                code=400,
                operator_id=operator_id,
                payload=args,
                note=str(err),
            )
            return jsonify({"ok": False, "error": str(err)}), 400
        except Exception:
            app.logger.exception("consolidation_type_get_unexpected_error")
            _safe_log_consolidation_audit(
                action="type_get",
                group_id=group_id,
                status="failed",
                code=500,
                operator_id=operator_id,
                payload=args,
                note="internal_error",
            )
            return jsonify({"ok": False, "error": "internal_error"}), 500

    @app.post("/api/consolidation/type")
    def api_consolidation_type_set():
        payload = request.get_json(silent=True) or {}
        operator_id = _get_operator_id(payload) or 1
        group_id = None
        try:
            group_id = int(payload.get("group_id") or payload.get("consolidation_group_id"))
            if group_id <= 0:
                raise ValueError("group_id_invalid")
            as_of = date.fromisoformat(str(payload.get("as_of") or "").strip())
            with get_connection_provider().connect() as conn:
                assert_virtual_authorized(conn, group_id, as_of)
            result = evaluate_type(group_id, as_of.isoformat())
            _safe_log_consolidation_audit(
                action="type_post",
                group_id=group_id,
                status="success",
                code=200,
                operator_id=operator_id,
                payload=payload,
                note=f"as_of={as_of.isoformat()}",
            )
            return jsonify({"ok": True, **result}), 200
        except ConsolidationAuthorizationError as err:
            _safe_log_consolidation_audit(
                action="type_post",
                group_id=group_id,
                status="forbidden",
                code=403,
                operator_id=operator_id,
                payload=payload,
                note=str(err),
            )
            return jsonify({"error": "forbidden"}), 403
        except (TypeError, ValueError, ConsolidationTypeError) as err:
            _safe_log_consolidation_audit(
                action="type_post",
                group_id=group_id,
                status="failed",
                code=400,
                operator_id=operator_id,
                payload=payload,
                note=str(err),
            )
            return jsonify({"ok": False, "error": str(err)}), 400
        except Exception:
            app.logger.exception("consolidation_type_set_unexpected_error")
            _safe_log_consolidation_audit(
                action="type_post",
                group_id=group_id,
                status="failed",
                code=500,
                operator_id=operator_id,
                payload=payload,
                note="internal_error",
            )
            return jsonify({"ok": False, "error": "internal_error"}), 500

    @app.post("/api/consolidation/relations/non-legal-bind")
    def api_consolidation_bind_non_legal():
        payload = request.get_json(silent=True) or {}
        try:
            result = bind_non_legal_to_legal(payload)
            return jsonify(result), 200
        except ConsolidationManageError as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("consolidation_bind_non_legal_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.get("/api/consolidation/virtual-entities")
    def api_consolidation_virtual_entities():
        try:
            result = list_relation_overview(request.args.to_dict(flat=True))
            return jsonify({"items": result.get("virtual_entities") or []}), 200
        except ConsolidationManageError as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("consolidation_virtual_entities_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.post("/api/consolidation/virtual-entities")
    def api_consolidation_virtual_entities_create():
        payload = request.get_json(silent=True) or {}
        try:
            result = create_virtual_entity(payload)
            return jsonify(result), 201
        except ConsolidationManageError as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("consolidation_virtual_entities_create_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.get("/api/consolidation/virtual-entities/<int:virtual_id>")
    def api_consolidation_virtual_detail(virtual_id: int):
        try:
            result = get_virtual_entity_detail(virtual_id)
            return jsonify(result), 200
        except ConsolidationManageError as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("consolidation_virtual_detail_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.get("/api/consolidation/virtual-entities/<int:virtual_id>/members")
    def api_consolidation_virtual_members(virtual_id: int):
        try:
            result = list_virtual_entity_members(virtual_id)
            return jsonify(result), 200
        except ConsolidationManageError as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("consolidation_virtual_members_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.post("/api/consolidation/virtual-entities/<int:virtual_id>/members")
    def api_consolidation_virtual_members_add(virtual_id: int):
        payload = request.get_json(silent=True) or {}
        try:
            result = add_virtual_entity_member(virtual_id, payload)
            return jsonify(result), 201
        except ConsolidationManageError as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("consolidation_virtual_members_add_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.post("/api/consolidation/members/<int:member_id>/disable")
    def api_consolidation_member_disable(member_id: int):
        try:
            result = disable_virtual_entity_member(member_id)
            return jsonify(result), 200
        except ConsolidationManageError as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("consolidation_member_disable_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.post("/api/authorizations")
    def api_consolidation_authorization_create():
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        try:
            result = create_authorization(payload, operator=operator, role=role)
            return jsonify(result), 201
        except ConsolidationAuthorizationError as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("consolidation_authorization_create_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.get("/api/authorizations")
    def api_consolidation_authorization_list():
        try:
            result = list_authorizations(request.args.to_dict(flat=True))
            return jsonify(result), 200
        except ConsolidationAuthorizationError as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("consolidation_authorization_list_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.patch("/api/authorizations/<int:authorization_id>/activate")
    def api_consolidation_authorization_activate(authorization_id: int):
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        try:
            result = set_authorization_status(
                authorization_id,
                "active",
                operator=operator,
                role=role,
                payload=payload,
            )
            return jsonify(result), 200
        except ConsolidationAuthorizationError as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("consolidation_authorization_activate_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.patch("/api/authorizations/<int:authorization_id>/suspend")
    def api_consolidation_authorization_suspend(authorization_id: int):
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        try:
            result = set_authorization_status(
                authorization_id,
                "suspended",
                operator=operator,
                role=role,
                payload=payload,
            )
            return jsonify(result), 200
        except ConsolidationAuthorizationError as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("consolidation_authorization_suspend_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.patch("/api/authorizations/<int:authorization_id>/revoke")
    def api_consolidation_authorization_revoke(authorization_id: int):
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        try:
            result = set_authorization_status(
                authorization_id,
                "revoked",
                operator=operator,
                role=role,
                payload=payload,
            )
            return jsonify(result), 200
        except ConsolidationAuthorizationError as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("consolidation_authorization_revoke_unexpected_error")
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
        username = str(payload.get("username") or "").strip()
        password = str(payload.get("password") or "")
        if not username or not password:
            return jsonify({"error": "validation_error", "detail": {"field": "username/password"}}), 400
        try:
            auth = authenticate_user(
                username=username,
                password=password,
                max_failed_attempts=auth_max_failed_attempts,
                lock_minutes=auth_lock_minutes,
            )
        except AuthError as err:
            status = 401
            if str(err) == "account_locked":
                status = 423
            elif str(err) == "auth_schema_not_ready":
                status = 503
            log_audit("auth", "login_failed", "user", None, username, "", {"username": username, **(err.detail or {})})
            return jsonify({"error": str(err), "detail": err.detail}), status

        expires_at = datetime.now(timezone.utc) + timedelta(minutes=auth_session_timeout_minutes)
        session.permanent = True
        session["auth_ctx"] = {
            "user_id": int(auth["id"]),
            "username": str(auth["username"] or ""),
            "role": str(auth["role"] or ""),
        }
        session["auth_expires_at"] = expires_at.isoformat()
        log_audit(
            "auth",
            "login",
            "user",
            int(auth["id"]),
            str(auth["username"] or ""),
            str(auth["role"] or ""),
            {"username": str(auth["username"] or ""), "expires_at": expires_at.isoformat()},
        )
        return (
            jsonify(
                {
                    "status": "ok",
                    "user": {
                        "id": int(auth["id"]),
                        "username": str(auth["username"] or ""),
                        "display_name": str(auth["display_name"] or ""),
                        "role": str(auth["role"] or ""),
                    },
                    "expires_at": expires_at.isoformat(),
                }
            ),
            200,
        )

    @app.post("/api/auth/logout")
    def api_auth_logout():
        payload = request.get_json(silent=True) or {}
        username = payload.get("username") or ""
        operator = (payload.get("operator") or username or "").strip()
        role = (payload.get("role") or "").strip()
        session.pop("auth_ctx", None)
        session.pop("auth_expires_at", None)
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

    @app.get("/api/reimbursements/sla-reminders")
    def api_reimbursements_sla_reminders():
        try:
            result = list_reimbursement_sla_reminders(request.args)
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

    @app.post("/api/reimbursements/<int:reimbursement_id>/void")
    def api_reimbursement_void(reimbursement_id: int):
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        try:
            result = void_reimbursement(reimbursement_id, operator, role, payload.get("reason"))
            log_audit(
                "reimbursement",
                "void",
                "reimbursement",
                reimbursement_id,
                operator,
                role,
                {"reason": payload.get("reason") or "", "from_status": result.get("from_status"), "to_status": result.get("to_status")},
            )
            return jsonify(result), 200
        except ReimbursementError as err:
            return jsonify({"error": str(err)}), 400

    @app.delete("/api/reimbursements/<int:reimbursement_id>")
    def api_reimbursement_delete(reimbursement_id: int):
        operator, role = _get_operator_from_headers()
        try:
            result = delete_reimbursement(reimbursement_id, operator, role)
            log_audit(
                "reimbursement",
                "delete",
                "reimbursement",
                reimbursement_id,
                operator,
                role,
                {"from_status": result.get("from_status"), "to_status": result.get("to_status")},
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

    @app.post("/api/payments/<int:payment_id>/void")
    def api_payment_void(payment_id: int):
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        try:
            result = void_payment(payment_id, operator, role, payload.get("reason"))
            log_audit(
                "payment",
                "void",
                "payment",
                payment_id,
                operator,
                role,
                {"reason": payload.get("reason") or "", "from_status": result.get("from_status"), "to_status": result.get("to_status")},
            )
            return jsonify(result), 200
        except PaymentError as err:
            return jsonify({"error": str(err)}), 400

    @app.delete("/api/payments/<int:payment_id>")
    def api_payment_delete(payment_id: int):
        operator, role = _get_operator_from_headers()
        try:
            result = delete_payment(payment_id, operator, role)
            log_audit(
                "payment",
                "delete",
                "payment",
                payment_id,
                operator,
                role,
                {"from_status": result.get("from_status"), "to_status": result.get("to_status")},
            )
            return jsonify(result), 200
        except PaymentError as err:
            return jsonify({"error": str(err)}), 400

    @app.post("/api/payroll/periods")
    def api_payroll_upsert_period():
        operator, role = _get_operator_from_headers()
        if role not in ("payroll", "hr", "admin"):
            return jsonify({"error": "forbidden"}), 403
        payload = request.get_json(silent=True) or {}
        try:
            result = upsert_payroll_period(payload)
            log_audit("payroll", "period_upsert", "payroll_period", result.get("id"), operator, role, payload)
            return jsonify(result), 200
        except PayrollError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.get("/api/payroll/periods")
    def api_payroll_list_periods():
        _, role = _get_operator_from_headers()
        if role not in ("payroll", "hr", "admin", "auditor"):
            return jsonify({"error": "forbidden"}), 403
        try:
            result = list_payroll_periods(request.args)
            return jsonify(result), 200
        except PayrollError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.post("/api/payroll/periods/<int:period_id>/close")
    def api_payroll_close_period(period_id: int):
        operator, role = _get_operator_from_headers()
        if role not in ("payroll", "admin"):
            return jsonify({"error": "forbidden"}), 403
        operator_id = _get_operator_id({})
        try:
            result = set_payroll_period_status(period_id, "close", operator_id)
            log_audit("payroll", "period_close", "payroll_period", period_id, operator, role, result)
            return jsonify(result), 200
        except PayrollError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.post("/api/payroll/periods/<int:period_id>/reopen")
    def api_payroll_reopen_period(period_id: int):
        operator, role = _get_operator_from_headers()
        if role not in ("payroll", "admin"):
            return jsonify({"error": "forbidden"}), 403
        try:
            result = set_payroll_period_status(period_id, "reopen", None)
            log_audit("payroll", "period_reopen", "payroll_period", period_id, operator, role, result)
            return jsonify(result), 200
        except PayrollError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.post("/api/payroll/slips")
    def api_payroll_upsert_slip():
        operator, role = _get_operator_from_headers()
        if role not in ("payroll", "hr", "admin"):
            return jsonify({"error": "forbidden"}), 403
        payload = request.get_json(silent=True) or {}
        try:
            result = upsert_payroll_slip(payload)
            log_audit("payroll", "slip_upsert", "payroll_slip", result.get("id"), operator, role, payload)
            return jsonify(result), 200
        except PayrollError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.get("/api/payroll/slips")
    def api_payroll_list_slips():
        _, role = _get_operator_from_headers()
        if role not in ("payroll", "hr", "admin", "auditor", "cashier", "employee", "staff", "self"):
            return jsonify({"error": "forbidden"}), 403
        try:
            params = request.args.to_dict(flat=True)
            params["viewer_role"] = role
            viewer_employee_id = (
                request.headers.get("X-Employee-Id")
                or request.args.get("employee_id")
                or request.headers.get("X-Operator-Id")
            )
            if viewer_employee_id:
                params["viewer_employee_id"] = str(viewer_employee_id)
            result = list_payroll_slips(params)
            return jsonify(result), 200
        except PayrollError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.post("/api/payroll/slips/<int:slip_id>/confirm")
    def api_payroll_confirm_slip(slip_id: int):
        operator, role = _get_operator_from_headers()
        if role not in ("payroll", "admin"):
            return jsonify({"error": "forbidden"}), 403
        try:
            result = confirm_payroll_slip(slip_id, operator, role)
            log_audit("payroll", "slip_confirm", "payroll_slip", slip_id, operator, role, result)
            return jsonify(result), 200
        except PayrollError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.get("/api/payroll/slips/<int:slip_id>/voucher-suggestion")
    def api_payroll_voucher_suggestion(slip_id: int):
        _, role = _get_operator_from_headers()
        if role not in ("payroll", "admin", "auditor"):
            return jsonify({"error": "forbidden"}), 403
        try:
            result = get_payroll_voucher_suggestion(slip_id)
            return jsonify(result), 200
        except PayrollError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.post("/api/payroll/slips/<int:slip_id>/create-payment-request")
    def api_payroll_create_payment_request(slip_id: int):
        operator, role = _get_operator_from_headers()
        if role not in ("payroll", "cashier", "admin"):
            return jsonify({"error": "forbidden"}), 403
        try:
            result = create_payroll_payment_request(slip_id, operator, role)
            log_audit("payroll", "create_payment_request", "payroll_slip", slip_id, operator, role, result)
            return jsonify(result), 200
        except PayrollError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.get("/api/payroll/slips/<int:slip_id>/payment-status")
    def api_payroll_payment_status(slip_id: int):
        _, role = _get_operator_from_headers()
        if role not in ("payroll", "cashier", "hr", "admin", "auditor"):
            return jsonify({"error": "forbidden"}), 403
        try:
            result = get_payroll_payment_status(slip_id)
            return jsonify(result), 200
        except PayrollError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.post("/api/payroll/policies/regions")
    def api_payroll_upsert_region_policy():
        operator, role = _get_operator_from_headers()
        if role not in ("payroll", "hr", "admin"):
            return jsonify({"error": "forbidden"}), 403
        payload = request.get_json(silent=True) or {}
        try:
            result = upsert_payroll_region_policy(payload)
            log_audit("payroll", "region_policy_upsert", "payroll_region_policy", result.get("id"), operator, role, payload)
            return jsonify(result), 200
        except PayrollError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.get("/api/payroll/policies/regions")
    def api_payroll_list_region_policies():
        _, role = _get_operator_from_headers()
        if role not in ("payroll", "hr", "admin", "auditor"):
            return jsonify({"error": "forbidden"}), 403
        try:
            result = list_payroll_region_policies(request.args.to_dict(flat=True))
            return jsonify(result), 200
        except PayrollError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.post("/api/payroll/disbursement-batches")
    def api_payroll_create_disbursement_batch():
        operator, role = _get_operator_from_headers()
        if role not in ("payroll", "cashier", "admin"):
            return jsonify({"error": "forbidden"}), 403
        payload = request.get_json(silent=True) or {}
        try:
            result = create_payroll_disbursement_batch(payload, operator, role)
            log_audit("payroll", "disbursement_batch_create", "payroll_disbursement_batch", result.get("batch_id"), operator, role, result)
            return jsonify(result), 200
        except PayrollError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.get("/api/payroll/disbursement-batches")
    def api_payroll_list_disbursement_batches():
        _, role = _get_operator_from_headers()
        if role not in ("payroll", "cashier", "admin", "auditor"):
            return jsonify({"error": "forbidden"}), 403
        try:
            result = list_payroll_disbursement_batches(request.args.to_dict(flat=True))
            return jsonify(result), 200
        except PayrollError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.get("/api/payroll/disbursement-batches/<int:batch_id>/bank-file")
    def api_payroll_export_bank_file(batch_id: int):
        operator, role = _get_operator_from_headers()
        if role not in ("payroll", "cashier", "admin", "auditor"):
            return jsonify({"error": "forbidden"}), 403
        try:
            result = export_payroll_bank_file(batch_id, operator, role)
            return send_file(
                io.BytesIO(result["content"]),
                mimetype="text/csv; charset=utf-8",
                as_attachment=True,
                download_name=result["file_name"],
            )
        except PayrollError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.post("/api/payroll/attendance/sync")
    def api_payroll_attendance_sync():
        _, role = _get_operator_from_headers()
        if role not in ("payroll", "hr", "admin", "attendance", "system"):
            return jsonify({"error": "forbidden"}), 403
        payload = request.get_json(silent=True) or {}
        try:
            result = sync_attendance_interface(payload)
            return jsonify(result), 200
        except PayrollError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    # Keep attendance interface compatible for external systems.
    @app.post("/api/attendance/sync")
    def api_attendance_sync():
        _, role = _get_operator_from_headers()
        if role not in ("payroll", "hr", "admin", "attendance", "system"):
            return jsonify({"error": "forbidden"}), 403
        payload = request.get_json(silent=True) or {}
        try:
            result = sync_attendance_interface(payload)
            return jsonify(result), 200
        except PayrollError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400

    @app.post("/api/bank_transactions/import")
    def api_bank_import():
        try:
            book_id = int(request.form.get("book_id", ""))
            bank_account_id = int(request.form.get("bank_account_id", ""))
            template_mapping_raw = (request.form.get("template_mapping") or "").strip()
            template_mapping = {}
            if template_mapping_raw:
                try:
                    template_mapping = json.loads(template_mapping_raw)
                except Exception:
                    return jsonify({"error": "template_mapping must be valid json"}), 400
                if not isinstance(template_mapping, dict):
                    return jsonify({"error": "template_mapping must be object"}), 400
            file = request.files.get("file")
            if not file:
                return jsonify({"error": "file required"}), 400
            data = import_bank_transactions(
                book_id, bank_account_id, file.filename, file.read(), template_mapping=template_mapping
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

    @app.get("/api/reconcile/rules")
    def api_reconcile_rules():
        try:
            return jsonify({"items": get_reconciliation_rules()}), 200
        except ReconcileError as err:
            return jsonify({"error": str(err)}), 400

    @app.get("/api/reconcile/discrepancy-reasons")
    def api_reconcile_discrepancy_reasons():
        try:
            return jsonify({"items": get_discrepancy_reasons()}), 200
        except ReconcileError as err:
            return jsonify({"error": str(err)}), 400

    @app.post("/api/reconcile/bulk-confirm")
    def api_reconcile_bulk_confirm():
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        try:
            result = bulk_confirm_reconciliation(payload.get("records") or [], operator, role)
            log_audit(
                "bank_reconcile",
                "bulk_confirm",
                "bank_transaction",
                None,
                operator,
                role,
                {"total": result.get("total"), "success": result.get("success"), "failed": result.get("failed")},
            )
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

    @app.post("/api/tax/invoices/verify")
    def api_tax_invoice_verify():
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        try:
            result = verify_invoice(payload)
            log_audit("tax", "invoice_verify", "tax_invoice", payload.get("invoice_id"), operator, role, {"valid": result.get("valid"), "errors": result.get("errors", [])})
            return jsonify(result), 200
        except TaxError as err:
            return jsonify({"error": str(err)}), 400

    @app.post("/api/tax/diff-ledger")
    def api_tax_diff_ledger_create():
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        try:
            result = create_tax_diff_entry(payload)
            log_audit("tax", "diff_ledger_create", "tax_difference_ledger", result.get("id"), operator, role, payload)
            return jsonify(result), 200
        except TaxError as err:
            return jsonify({"error": str(err)}), 400

    @app.get("/api/tax/diff-ledger")
    def api_tax_diff_ledger_list():
        try:
            result = list_tax_diff_entries(request.args)
            return jsonify(result), 200
        except TaxError as err:
            return jsonify({"error": str(err)}), 400

    @app.post("/api/tax/declaration-mappings")
    def api_tax_declaration_mapping_save():
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        try:
            result = map_tax_declaration(payload)
            log_audit("tax", "declaration_mapping_save", "tax_declaration_mapping", None, operator, role, {"book_id": payload.get("book_id"), "declaration_code": payload.get("declaration_code"), "count": result.get("count")})
            return jsonify(result), 200
        except TaxError as err:
            return jsonify({"error": str(err)}), 400

    @app.get("/api/tax/declaration-mappings")
    def api_tax_declaration_mapping_list():
        try:
            result = list_tax_declaration_mappings(request.args)
            return jsonify(result), 200
        except TaxError as err:
            return jsonify({"error": str(err)}), 400

    @app.post("/api/tax/declaration-mappings/build")
    def api_tax_declaration_mapping_build():
        payload = request.get_json(silent=True) or {}
        try:
            result = build_tax_declaration_mapping(payload)
            return jsonify(result), 200
        except TaxError as err:
            return jsonify({"error": str(err)}), 400

    @app.post("/api/tax/calc/year-end-bonus")
    def api_tax_calc_year_end_bonus():
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        try:
            result = calc_year_end_bonus_tax(payload)
            log_audit(
                "tax",
                "calc_year_end_bonus",
                "tax_calc",
                None,
                operator,
                role,
                {
                    "tax_mode": payload.get("tax_mode"),
                    "biz_year": payload.get("biz_year"),
                    "success": True,
                },
            )
            return jsonify(result), 200
        except TaxError as err:
            return jsonify({"error": str(err)}), 400

    @app.post("/api/tax/calc/labor-service")
    def api_tax_calc_labor_service():
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        try:
            result = calc_labor_service_tax(payload)
            log_audit(
                "tax",
                "calc_labor_service",
                "tax_calc",
                None,
                operator,
                role,
                {"period": payload.get("period"), "success": True},
            )
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

    @app.get("/api/vouchers/import/template")
    def api_voucher_import_template():
        try:
            filename, content = get_voucher_import_template()
            return send_file(
                io.BytesIO(content),
                as_attachment=True,
                download_name=filename,
                mimetype="text/csv",
            )
        except Exception:
            app.logger.exception("voucher_import_template_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.post("/api/vouchers/import/preview")
    def api_voucher_import_preview():
        operator, role = _get_operator_from_headers()
        file = request.files.get("file")
        if not file:
            return jsonify({"error": "file required"}), 400
        payload = {
            "book_id": request.form.get("book_id") or request.args.get("book_id") or request.headers.get("X-Book-Id"),
            "maker": request.form.get("maker") or operator,
        }
        try:
            result = preview_vouchers_import(payload, file.filename or "voucher_import.csv", file.read())
            log_audit(
                "voucher_import",
                "preview",
                "voucher_import_batch",
                None,
                operator,
                role,
                {
                    "book_id": payload.get("book_id"),
                    "error_count": int(result.get("error_count") or 0),
                    "voucher_groups": int((result.get("summary") or {}).get("voucher_groups") or 0),
                },
            )
            return jsonify(result), 200
        except VoucherImportError as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("voucher_import_preview_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.post("/api/vouchers/import/commit")
    def api_voucher_import_commit():
        operator, role = _get_operator_from_headers()
        file = request.files.get("file")
        if not file:
            return jsonify({"error": "file required"}), 400
        payload = {
            "book_id": request.form.get("book_id") or request.args.get("book_id") or request.headers.get("X-Book-Id"),
            "maker": request.form.get("maker") or operator,
        }
        try:
            result = commit_vouchers_import(payload, file.filename or "voucher_import.csv", file.read())
            status = 200 if int(result.get("error_count") or 0) == 0 else 400
            log_audit(
                "voucher_import",
                "commit",
                "voucher_import_batch",
                None,
                operator,
                role,
                {
                    "book_id": payload.get("book_id"),
                    "error_count": int(result.get("error_count") or 0),
                    "imported_voucher_count": int((result.get("summary") or {}).get("imported_voucher_count") or 0),
                    "imported_line_count": int((result.get("summary") or {}).get("imported_line_count") or 0),
                },
            )
            return jsonify(result), status
        except VoucherImportError as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("voucher_import_commit_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    def _run_voucher_template_preview(action_name: str):
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        try:
            result = build_template_preview(
                payload.get("book_id"),
                payload.get("template_code"),
                payload.get("params") or {},
                operator=operator,
                role=role,
            )
            log_audit(
                "voucher",
                action_name,
                "voucher_template",
                None,
                operator,
                role,
                {
                    "book_id": payload.get("book_id"),
                    "template_code": payload.get("template_code"),
                    "success": bool(result.get("success")),
                    "error_count": len(result.get("errors") or []),
                    "preview_only": True,
                },
            )
            status = 200 if result.get("success") else 400
            return jsonify(result), status
        except VoucherTemplateError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400
        except Exception:
            app.logger.exception("voucher_template_preview_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.post("/api/vouchers/template-preview")
    def api_voucher_template_preview():
        return _run_voucher_template_preview("template_preview")

    @app.post("/api/vouchers/template-suggest")
    def api_voucher_template_suggest():
        return _run_voucher_template_preview("template_suggest")

    @app.get("/api/voucher-templates/search")
    def api_voucher_template_search():
        try:
            result = list_template_candidates(request.args.to_dict(flat=True))
            return jsonify(result), 200
        except VoucherTemplateError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400
        except Exception:
            app.logger.exception("voucher_template_search_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.get("/api/voucher-templates/detail")
    def api_voucher_template_detail():
        try:
            result = get_template_detail(request.args.to_dict(flat=True))
            return jsonify(result), 200
        except VoucherTemplateError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400
        except Exception:
            app.logger.exception("voucher_template_detail_unexpected_error")
            return jsonify({"error": "internal_error"}), 500

    @app.post("/api/vouchers/template-draft")
    def api_voucher_template_draft():
        operator, role = _get_operator_from_headers()
        payload = request.get_json(silent=True) or {}
        try:
            result = build_template_draft(
                payload.get("book_id"),
                payload.get("template_code"),
                payload.get("params") or {},
                standard_type=payload.get("standard_type") or "",
                aux_context=payload.get("aux_context") or {},
                operator=operator,
                role=role,
            )
            log_audit(
                "voucher",
                "template_draft",
                "voucher_template",
                None,
                operator,
                role,
                {
                    "book_id": payload.get("book_id"),
                    "template_code": payload.get("template_code"),
                    "success": bool(result.get("success")),
                    "error_count": len(result.get("errors") or []),
                    "aux_missing_count": len(result.get("required_aux_inputs") or []),
                },
            )
            status = 200 if result.get("success") else 400
            return jsonify(result), status
        except VoucherTemplateError as err:
            return jsonify({"error": str(err), "errors": err.errors}), 400
        except Exception:
            app.logger.exception("voucher_template_draft_unexpected_error")
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


def _run_cli_task() -> int | None:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--task", default="")
    parser.add_argument("--action", default="")
    parser.add_argument("--group-id", type=int, default=0)
    parser.add_argument("--as-of", default="")
    parser.add_argument("--associate-entity-id", type=int, default=0)
    parser.add_argument("--opening-carrying-amount", default="0")
    parser.add_argument("--ownership-pct", default="0")
    parser.add_argument("--net-income", default="0")
    parser.add_argument("--other-comprehensive-income", default="0")
    parser.add_argument("--dividends", default="0")
    parser.add_argument("--impairment", default="0")
    parser.add_argument("--entity-net-assets", default="{}")
    parser.add_argument("--entity-net-profit", default="{}")
    parser.add_argument("--opening-nci-balance", default="{}")
    parser.add_argument("--from-period", default="")
    parser.add_argument("--to-period", default="")
    parser.add_argument("--period", default="")
    parser.add_argument("--start-period", default="")
    parser.add_argument("--note", default="")
    parser.add_argument("--consolidation-method", default="")
    parser.add_argument("--default-scope", default="")
    parser.add_argument("--currency", default="")
    parser.add_argument("--fx-rate-policy", default="")
    parser.add_argument("--accounting-policy", default="")
    parser.add_argument("--period-elimination", default="")
    parser.add_argument("--operator-id", type=int, default=1)
    args, _unknown = parser.parse_known_args()

    task = str(args.task or "").strip().upper()
    action = str(args.action or "").strip().lower()
    if not task and not action:
        return None

    if task == "CONS-21" and action == "equity_method_calculation":
        payload = {
            "consolidation_group_id": args.group_id,
            "as_of": args.as_of,
            "associate_entity_id": args.associate_entity_id,
            "opening_carrying_amount": args.opening_carrying_amount,
            "ownership_pct": args.ownership_pct,
            "net_income": args.net_income,
            "other_comprehensive_income": args.other_comprehensive_income,
            "dividends": args.dividends,
            "impairment": args.impairment,
        }
        try:
            result = generate_equity_method(payload, operator_id=args.operator_id)
            print(json.dumps({"ok": True, **result}, ensure_ascii=False))
            return 0
        except Exception as err:
            print(json.dumps({"ok": False, "error": str(err)}, ensure_ascii=False))
            return 1

    if task == "CONS-22" and action == "nci_dynamic_calculation":
        payload = {
            "consolidation_group_id": args.group_id,
            "as_of": args.as_of,
            "entity_net_assets": args.entity_net_assets,
            "entity_net_profit": args.entity_net_profit,
            "opening_nci_balance": args.opening_nci_balance,
        }
        try:
            result = generate_nci_dynamic(payload, operator_id=args.operator_id)
            print(json.dumps({"ok": True, **result}, ensure_ascii=False))
            return 0
        except Exception as err:
            print(json.dumps({"ok": False, "error": str(err)}, ensure_ascii=False))
            return 1

    if task == "CONS-23" and action == "multi_period_rollover_support":
        payload = {
            "consolidation_group_id": args.group_id,
            "as_of": args.as_of,
            "from_period": args.from_period,
            "to_period": args.to_period,
        }
        try:
            result = generate_multi_period_rollover(payload, operator_id=args.operator_id)
            print(json.dumps({"ok": True, **result}, ensure_ascii=False))
            return 0
        except Exception as err:
            print(json.dumps({"ok": False, "error": str(err)}, ensure_ascii=False))
            return 1

    if task == "CONS-24" and action == "merge_journal_and_post_merge_balance":
        payload = {
            "consolidation_group_id": args.group_id,
            "period": args.period,
            "as_of": args.as_of,
        }
        try:
            result = generate_merge_journal_and_post_merge_balance(payload, operator_id=args.operator_id)
            print(json.dumps({"ok": True, **result}, ensure_ascii=False))
            return 0
        except Exception as err:
            print(json.dumps({"ok": False, "error": str(err)}, ensure_ascii=False))
            return 1

    if task == "CONS-25" and action == "generate_report_templates_and_merge_reports":
        payload = {
            "consolidation_group_id": args.group_id,
            "period": args.period,
            "as_of": args.as_of,
        }
        try:
            result = generate_report_templates_and_merge_reports(payload, operator_id=args.operator_id)
            print(json.dumps({"ok": True, **result}, ensure_ascii=False))
            return 0
        except Exception as err:
            print(json.dumps({"ok": False, "error": str(err)}, ensure_ascii=False))
            return 1

    if task == "CONS-26" and action == "audit_logs_and_permission_control":
        payload = {
            "consolidation_group_id": args.group_id,
            "as_of": args.as_of,
            "action_content": "audit_logs_and_permission_control",
        }
        try:
            result = run_audit_logs_and_permission_control(payload, operator_id=args.operator_id)
            print(json.dumps({"ok": bool(result.get("permission_granted")), **result}, ensure_ascii=False))
            return 0 if bool(result.get("permission_granted")) else 1
        except Exception as err:
            print(json.dumps({"ok": False, "error": str(err)}, ensure_ascii=False))
            return 1

    if task == "CONS-27" and action == "configure_merger_scope_and_criteria":
        payload = {
            "consolidation_group_id": args.group_id,
            "start_period": args.start_period,
            "note": args.note,
            "consolidation_method": args.consolidation_method,
            "default_scope": args.default_scope,
            "currency": args.currency,
            "fx_rate_policy": args.fx_rate_policy,
            "accounting_policy": args.accounting_policy,
            "period_elimination": args.period_elimination,
            "operator_id": args.operator_id,
        }
        try:
            result = configure_merger_scope_and_criteria(payload, operator_id=args.operator_id)
            print(json.dumps({"ok": True, **result}, ensure_ascii=False))
            return 0
        except Exception as err:
            print(json.dumps({"ok": False, "error": str(err)}, ensure_ascii=False))
            return 1

    if task == "CONS-28" and action == "automate_report_generation_and_adjustment":
        payload = {
            "consolidation_group_id": args.group_id,
            "period": args.period,
            "as_of": args.as_of,
            "operator_id": args.operator_id,
        }
        try:
            result = automate_report_generation_and_adjustment(payload, operator_id=args.operator_id)
            print(json.dumps({"ok": True, **result}, ensure_ascii=False))
            return 0
        except Exception as err:
            print(json.dumps({"ok": False, "error": str(err)}, ensure_ascii=False))
            return 1

    if task == "CONS-29" and action == "final_check_and_approval_flow":
        payload = {
            "consolidation_group_id": args.group_id,
            "period": args.period,
            "as_of": args.as_of,
            "operator_id": args.operator_id,
            "approver_id": args.operator_id,
            "auto_approve": True,
        }
        try:
            result = run_final_check_and_approval_flow(payload, operator_id=args.operator_id)
            ok = bool(result.get("final_check_passed"))
            print(json.dumps({"ok": ok, **result}, ensure_ascii=False))
            return 0 if ok else 1
        except Exception as err:
            print(json.dumps({"ok": False, "error": str(err)}, ensure_ascii=False))
            return 1

    if task == "CONS-30" and action == "generate_disclosure_and_audit_package":
        payload = {
            "consolidation_group_id": args.group_id,
            "period": args.period,
            "as_of": args.as_of,
            "operator_id": args.operator_id,
        }
        try:
            result = generate_disclosure_and_audit_package(payload, operator_id=args.operator_id)
            print(json.dumps({"ok": True, **result}, ensure_ascii=False))
            return 0
        except Exception as err:
            print(json.dumps({"ok": False, "error": str(err)}, ensure_ascii=False))
            return 1

    print(json.dumps({"ok": False, "error": "task_or_action_not_supported"}, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    cli_exit_code = _run_cli_task()
    if cli_exit_code is not None:
        sys.exit(cli_exit_code)
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=False)
