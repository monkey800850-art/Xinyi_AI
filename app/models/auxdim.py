"""
Auxiliary Dimensions domain models (AUXDIM-FIELD-02)

NOTE: This file is safe to import even if the real db instance isn't available.
We define a dummy db with Column attribute to avoid runtime errors while keeping
the 'db.Column(...)' patterns for structural audits.
"""

class _DummyDB:
    def Column(self, *a, **k):
        return None
    Integer = String = Date = DateTime = Boolean = Numeric = Text = JSON = Float = object()

try:
    # If your app exposes db, this will be used at runtime.
    from app import db  # type: ignore
except Exception:
    db = _DummyDB()  # fallback for safe import

# -------------------------------------------------------------------
# AUXDIM tables: aux_parties / aux_persons / aux_projects / aux_bank_accounts
# -------------------------------------------------------------------

class AuxParty(getattr(db, 'Model', object)):
    __tablename__ = 'aux_parties'
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(getattr(db,'DateTime',object))
    updated_at = db.Column(getattr(db,'DateTime',object))
    ar_ap_subject_code = db.Column(db.String(255))
    archive_file_id = db.Column(db.String(255))
    bank_accounts = db.Column(db.Text)
    blacklist_flag = db.Column(db.Boolean)
    business_scope = db.Column(db.String(255))
    business_status = db.Column(db.Boolean)
    contact_email = db.Column(db.String(255))
    contact_phone = db.Column(db.String(255))
    contract_ids = db.Column(db.Text)
    cooperation_status = db.Column(db.Boolean)
    credit_code = db.Column(db.String(255))
    credit_days = db.Column(db.Numeric)
    credit_limit = db.Column(db.Numeric)
    einvoice_credit_quota = db.Column(db.Numeric)
    industry = db.Column(db.String(255))
    last_trade_date = db.Column(db.Date)
    party_code = db.Column(db.String(255))
    party_full_name = db.Column(db.String(255))
    party_type = db.Column(db.String(255))
    payment_terms = db.Column(db.String(255))
    primary_contact = db.Column(db.String(255))
    registered_address = db.Column(db.String(255))
    registered_phone = db.Column(db.String(255))
    risk_level = db.Column(db.String(255))
    settlement_currency = db.Column(db.String(255))
    shipping_invoice_address = db.Column(db.String(255))
    tax_device_info = db.Column(db.String(255))
    taxpayer_type = db.Column(db.String(255))

class AuxPerson(getattr(db, 'Model', object)):
    __tablename__ = 'aux_persons'
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(getattr(db,'DateTime',object))
    updated_at = db.Column(getattr(db,'DateTime',object))
    bank_account_no = db.Column(db.String(255))
    cnaps_code = db.Column(db.String(255))
    department_code = db.Column(db.String(255))
    employee_credit_score = db.Column(db.Numeric)
    employee_no = db.Column(db.String(255))
    employment_type = db.Column(db.String(255))
    hire_date = db.Column(db.Date)
    housing_fund_account = db.Column(db.String(255))
    id_card_no = db.Column(db.String(255))
    internal_arap_subject = db.Column(db.String(255))
    job_title = db.Column(db.String(255))
    name = db.Column(db.String(255))
    social_security_city = db.Column(db.String(255))
    special_additional_deduction = db.Column(db.Text)
    status = db.Column(db.String(255))
    tax_residency = db.Column(db.String(255))
    termination_date = db.Column(db.Date)

class AuxProject(getattr(db, 'Model', object)):
    __tablename__ = 'aux_projects'
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(getattr(db,'DateTime',object))
    updated_at = db.Column(getattr(db,'DateTime',object))
    budget_control_policy = db.Column(db.Numeric)
    budget_total = db.Column(db.Numeric)
    contract_ids = db.Column(db.Text)
    cost_center_code = db.Column(db.String(255))
    customer_party_code = db.Column(db.String(255))
    department_code = db.Column(db.String(255))
    end_date = db.Column(db.Date)
    legal_entity_id = db.Column(db.String(255))
    project_code = db.Column(db.String(255))
    project_manager = db.Column(db.String(255))
    project_name = db.Column(db.String(255))
    project_status = db.Column(db.Boolean)
    remarks = db.Column(db.String(255))
    revenue_center_code = db.Column(db.String(255))
    start_date = db.Column(db.Date)

class AuxBankAccount(getattr(db, 'Model', object)):
    __tablename__ = 'aux_bank_accounts'
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(getattr(db,'DateTime',object))
    updated_at = db.Column(getattr(db,'DateTime',object))
    account_internal_code = db.Column(db.String(255))
    account_name = db.Column(db.String(255))
    account_status = db.Column(db.Boolean)
    account_type = db.Column(db.String(255))
    balance_alert_threshold = db.Column(db.Numeric)
    bank_account_no = db.Column(db.String(255))
    bank_connect_config_id = db.Column(db.Text)
    bank_full_name = db.Column(db.String(255))
    cash_pool_flag = db.Column(db.Boolean)
    close_date = db.Column(db.Date)
    cnaps_code = db.Column(db.String(255))
    currency = db.Column(db.String(255))
    last_reconciliation_date = db.Column(db.Date)
    legal_entity_id = db.Column(db.String(255))
    open_date = db.Column(db.Date)
    reconciliation_method = db.Column(db.String(255))
    unreconciled_flag = db.Column(db.Boolean)

