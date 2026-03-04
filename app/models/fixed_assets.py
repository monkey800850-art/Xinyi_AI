"""
Fixed Assets domain models (FA-FIELD-02)
Safe-import dummy db fallback; replace with real db.Model in future refactor if needed.
"""

class _DummyDB:
    def Column(self, *a, **k):
        return None
    Integer = String = Date = DateTime = Boolean = Numeric = Text = JSON = Float = object()

try:
    from app import db  # type: ignore
except Exception:
    db = _DummyDB()

# -------------------------------------------------------------------
# Tables: fa_assets / fa_depreciation_books
# -------------------------------------------------------------------

class FixedAsset(getattr(db, 'Model', object)):
    __tablename__ = 'fa_assets'
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(getattr(db,'DateTime',object))
    updated_at = db.Column(getattr(db,'DateTime',object))
    acceptance_doc_no = db.Column(db.String(255))
    accumulated_depreciation = db.Column(db.Numeric)
    archive_status = db.Column(db.String(255))
    asset_category = db.Column(db.String(255))
    audit_trail_required_flag = db.Column(db.Boolean)
    book_date = db.Column(db.Date)
    capitalized_date = db.Column(db.Date)
    custodian_person_id = db.Column(db.String(255))
    e_voucher_xml_ofd_path = db.Column(db.Text)
    economic_use = db.Column(db.String(255))
    env_safety_level = db.Column(db.String(255))
    funding_source = db.Column(db.String(255))
    gl_acc_dep_subject = db.Column(db.String(255))
    gl_asset_subject = db.Column(db.String(255))
    gl_dep_expense_subject = db.Column(db.String(255))
    impairment_reserve = db.Column(db.String(255))
    in_service_date = db.Column(db.Date)
    input_vat_amount = db.Column(db.Numeric)
    invoice_code = db.Column(db.String(255))
    invoice_number = db.Column(db.String(255))
    legal_entity_id = db.Column(db.String(255))
    multi_book_depreciation_flag = db.Column(db.Boolean)
    net_book_value = db.Column(db.Numeric)
    next_inventory_date = db.Column(db.Date)
    original_cost_excl_tax = db.Column(db.Numeric)
    original_cost_incl_tax = db.Column(db.Numeric)
    posting_voucher_no = db.Column(db.String(255))
    project_code = db.Column(db.String(255))
    purchase_contract_no = db.Column(db.String(255))
    remarks = db.Column(db.String(255))
    responsible_person_id = db.Column(db.String(255))
    salvage_rate = db.Column(db.Numeric)
    salvage_value = db.Column(db.Numeric)
    spec_model = db.Column(db.String(255))
    storage_location_id = db.Column(db.String(255))
    tag_qr_payload = db.Column(db.Text)
    tech_params_json = db.Column(db.Text)
    uom = db.Column(db.String(255))
    use_status = db.Column(db.String(255))
    using_department_id = db.Column(db.String(255))
    vendor_name = db.Column(db.String(255))
    warranty_end_date = db.Column(db.Date)

class FixedAssetDepreciationBook(getattr(db, 'Model', object)):
    __tablename__ = 'fa_depreciation_books'
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(getattr(db,'DateTime',object))
    updated_at = db.Column(getattr(db,'DateTime',object))
    accumulated_depreciation = db.Column(db.Numeric)
    book_type = db.Column(db.String(255))
    last_dep_period = db.Column(db.String(255))
    net_book_value = db.Column(db.Numeric)
    salvage_rate = db.Column(db.Numeric)
    salvage_value = db.Column(db.Numeric)

