"""FA-FIELD-02: create fixed assets tables"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = None
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # fa_assets
    op.create_table(
            'fa_assets',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('acceptance_doc_no', sa.String(length=255), nullable=True),
            sa.Column('accumulated_depreciation', sa.Numeric(18,2), nullable=True),
            sa.Column('archive_status', sa.String(length=255), nullable=True),
            sa.Column('asset_category', sa.String(length=255), nullable=True),
            sa.Column('audit_trail_required_flag', sa.Boolean(), nullable=True),
            sa.Column('book_date', sa.Date(), nullable=True),
            sa.Column('capitalized_date', sa.Date(), nullable=True),
            sa.Column('custodian_person_id', sa.String(length=255), nullable=True),
            sa.Column('e_voucher_xml_ofd_path', sa.Text(), nullable=True),
            sa.Column('economic_use', sa.String(length=255), nullable=True),
            sa.Column('env_safety_level', sa.String(length=255), nullable=True),
            sa.Column('funding_source', sa.String(length=255), nullable=True),
            sa.Column('gl_acc_dep_subject', sa.String(length=255), nullable=True),
            sa.Column('gl_asset_subject', sa.String(length=255), nullable=True),
            sa.Column('gl_dep_expense_subject', sa.String(length=255), nullable=True),
            sa.Column('impairment_reserve', sa.Numeric(18,2), nullable=True),
            sa.Column('in_service_date', sa.Date(), nullable=True),
            sa.Column('input_vat_amount', sa.Numeric(18,2), nullable=True),
            sa.Column('invoice_code', sa.String(length=255), nullable=True),
            sa.Column('invoice_number', sa.String(length=255), nullable=True),
            sa.Column('legal_entity_id', sa.String(length=255), nullable=True),
            sa.Column('multi_book_depreciation_flag', sa.Boolean(), nullable=True),
            sa.Column('net_book_value', sa.Numeric(18,2), nullable=True),
            sa.Column('next_inventory_date', sa.Date(), nullable=True),
            sa.Column('original_cost_excl_tax', sa.Numeric(18,2), nullable=True),
            sa.Column('original_cost_incl_tax', sa.Numeric(18,2), nullable=True),
            sa.Column('posting_voucher_no', sa.String(length=255), nullable=True),
            sa.Column('project_code', sa.String(length=255), nullable=True),
            sa.Column('purchase_contract_no', sa.String(length=255), nullable=True),
            sa.Column('remarks', sa.String(length=255), nullable=True),
            sa.Column('responsible_person_id', sa.String(length=255), nullable=True),
            sa.Column('salvage_rate', sa.Numeric(18,2), nullable=True),
            sa.Column('salvage_value', sa.Numeric(18,2), nullable=True),
            sa.Column('spec_model', sa.String(length=255), nullable=True),
            sa.Column('storage_location_id', sa.String(length=255), nullable=True),
            sa.Column('tag_qr_payload', sa.Text(), nullable=True),
            sa.Column('tech_params_json', sa.Text(), nullable=True),
            sa.Column('uom', sa.String(length=255), nullable=True),
            sa.Column('use_status', sa.String(length=255), nullable=True),
            sa.Column('using_department_id', sa.String(length=255), nullable=True),
            sa.Column('vendor_name', sa.String(length=255), nullable=True),
            sa.Column('warranty_end_date', sa.Date(), nullable=True)
        )
    op.create_index('ix_fa_assets_asset_code', 'fa_assets', ['asset_code'], unique=True)
    op.create_index('ix_fa_assets_legal_entity_id', 'fa_assets', ['legal_entity_id'], unique=False)
    op.create_index('ix_fa_assets_using_department_id', 'fa_assets', ['using_department_id'], unique=False)

    # fa_depreciation_books
    op.create_table(
            'fa_depreciation_books',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('accumulated_depreciation', sa.Numeric(18,2), nullable=True),
            sa.Column('book_type', sa.String(length=255), nullable=True),
            sa.Column('last_dep_period', sa.String(length=255), nullable=True),
            sa.Column('net_book_value', sa.Numeric(18,2), nullable=True),
            sa.Column('salvage_rate', sa.Numeric(18,2), nullable=True),
            sa.Column('salvage_value', sa.Numeric(18,2), nullable=True)
        )
    op.create_index('ix_fa_dep_books_asset_id', 'fa_depreciation_books', ['asset_id'], unique=False)
    op.create_index('ix_fa_dep_books_asset_book', 'fa_depreciation_books', ['asset_id','book_type'], unique=True)

def downgrade():
    op.drop_index('ix_fa_dep_books_asset_id', table_name='fa_depreciation_books')
    op.drop_index('ix_fa_dep_books_asset_book', table_name='fa_depreciation_books')
    op.drop_table('fa_depreciation_books')
    op.drop_index('ix_fa_assets_asset_code', table_name='fa_assets')
    op.drop_index('ix_fa_assets_legal_entity_id', table_name='fa_assets')
    op.drop_index('ix_fa_assets_using_department_id', table_name='fa_assets')
    op.drop_table('fa_assets')

