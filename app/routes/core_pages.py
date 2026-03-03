from flask import Blueprint, render_template

core_pages_bp = Blueprint("core_pages", __name__)


@core_pages_bp.get("/")
def index():
    return render_template("user_home.html")


@core_pages_bp.get("/healthz")
def health():
    return {"status": "ok"}


@core_pages_bp.get("/dashboard")
def dashboard_page():
    return render_template("dashboard.html")


@core_pages_bp.get("/dashboard/boss")
def boss_dashboard_page():
    return render_template("boss_dashboard.html")


@core_pages_bp.get("/demo/autocomplete")
def demo_autocomplete():
    return render_template("demo_autocomplete.html")


@core_pages_bp.get("/demo/filters")
def demo_filters():
    return render_template("autocomplete_filters.html")


@core_pages_bp.get("/voucher/entry")
def voucher_entry():
    return render_template("voucher_entry.html")


@core_pages_bp.get("/voucher/import")
def voucher_import_page():
    return render_template("voucher_import.html")


@core_pages_bp.get("/reports/trial_balance")
def trial_balance_page():
    return render_template("trial_balance.html")


@core_pages_bp.get("/reports/subject_ledger")
def subject_ledger_page():
    return render_template("subject_ledger.html")


@core_pages_bp.get("/reports/aux_reports")
def aux_reports_page():
    return render_template("aux_reports.html")


@core_pages_bp.get("/reports/ar_ap")
def ar_ap_page():
    return render_template("ar_ap_aging.html")


@core_pages_bp.get("/reimbursements")
def reimbursements_list_page():
    return render_template("reimbursements_list.html")


@core_pages_bp.get("/reimbursements/new")
def reimbursements_new_page():
    return render_template("reimbursements_detail.html", reimbursement_id="")


@core_pages_bp.get("/reimbursements/<int:reimbursement_id>")
def reimbursements_detail_page(reimbursement_id: int):
    return render_template("reimbursements_detail.html", reimbursement_id=reimbursement_id)


@core_pages_bp.get("/payments")
def payments_list_page():
    return render_template("payments_list.html")


@core_pages_bp.get("/payments/new")
def payments_new_page():
    return render_template("payments_detail.html", payment_id="")


@core_pages_bp.get("/payroll")
def payroll_page():
    return render_template("payroll.html")


@core_pages_bp.get("/payments/<int:payment_id>")
def payments_detail_page(payment_id: int):
    return render_template("payments_detail.html", payment_id=payment_id)


@core_pages_bp.get("/banks/import")
def bank_import_page():
    return render_template("bank_import.html")


@core_pages_bp.get("/banks/reconcile")
def bank_reconcile_page():
    return render_template("bank_reconcile.html")


@core_pages_bp.get("/masters/departments")
def master_departments_page():
    return render_template("master_data.html", master_kind="departments", master_label="部门")


@core_pages_bp.get("/masters/persons")
def master_persons_page():
    return render_template("master_data.html", master_kind="persons", master_label="个人")


@core_pages_bp.get("/masters/entities")
def master_entities_page():
    return render_template("master_data.html", master_kind="entities", master_label="单位")


@core_pages_bp.get("/masters/projects")
def master_projects_page():
    return render_template("master_data.html", master_kind="projects", master_label="项目")


@core_pages_bp.get("/masters/bank_accounts")
def master_bank_accounts_page():
    return render_template("master_data.html", master_kind="bank_accounts", master_label="银行账户")


@core_pages_bp.get("/masters/subjects/aux")
def subject_aux_config_page():
    return render_template("subject_aux_config.html")


@core_pages_bp.get("/tax/rules")
def tax_rules_page():
    return render_template("tax_rules.html")


@core_pages_bp.get("/tax/invoices")
def tax_invoices_page():
    return render_template("tax_invoices.html")


@core_pages_bp.get("/tax/summary")
def tax_summary_page():
    return render_template("tax_summary.html")


@core_pages_bp.get("/assets/categories")
def asset_categories_page():
    return render_template("asset_categories.html")


@core_pages_bp.get("/assets/depreciation")
def asset_depreciation_page():
    return render_template("asset_depreciation.html")


@core_pages_bp.get("/assets/changes")
def asset_changes_page():
    return render_template("asset_changes.html")


@core_pages_bp.get("/assets/reports/ledger")
def asset_ledger_page():
    return render_template("asset_ledger.html")


@core_pages_bp.get("/assets/reports/depreciation")
def asset_depreciation_report_page():
    return render_template("asset_depreciation_reports.html")


@core_pages_bp.get("/system/users")
def system_users_page():
    return render_template("system_users.html")


@core_pages_bp.get("/system/roles")
def system_roles_page():
    return render_template("system_roles.html")


@core_pages_bp.get("/system/rules")
def system_rules_page():
    return render_template("system_rules.html")


@core_pages_bp.get("/system/books")
def system_books_page():
    return render_template("system_books.html")


@core_pages_bp.get("/system/book-init")
def system_book_init_page():
    return render_template("system_book_init.html")


@core_pages_bp.get("/system/audit")
def system_audit_page():
    return render_template("audit_logs.html")


@core_pages_bp.get("/system/init")
def system_init_page():
    return render_template("system_init.html")


@core_pages_bp.get("/assets")
def assets_list_page():
    return render_template("assets_list.html")


@core_pages_bp.get("/assets/new")
def assets_new_page():
    return render_template("assets_detail.html", asset_id="")


@core_pages_bp.get("/assets/<int:asset_id>")
def assets_detail_page(asset_id: int):
    return render_template("assets_detail.html", asset_id=asset_id)
