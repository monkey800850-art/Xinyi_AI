"""AUXDIM-FIELD-02: create auxdim master data tables"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '952b08052623'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # aux_parties <- 单位(客户/供应商)
    op.create_table(
            'aux_parties',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('ar_ap_subject_code', sa.String(length=255), nullable=True),
            sa.Column('archive_file_id', sa.String(length=255), nullable=True),
            sa.Column('bank_accounts', sa.Text(), nullable=True),
            sa.Column('blacklist_flag', sa.Boolean(), nullable=True),
            sa.Column('business_scope', sa.String(length=255), nullable=True),
            sa.Column('business_status', sa.String(length=255), nullable=True),
            sa.Column('contact_email', sa.String(length=255), nullable=True),
            sa.Column('contact_phone', sa.String(length=255), nullable=True),
            sa.Column('contract_ids', sa.Text(), nullable=True),
            sa.Column('cooperation_status', sa.String(length=255), nullable=True),
            sa.Column('credit_code', sa.String(length=255), nullable=True),
            sa.Column('credit_days', sa.Numeric(18,2), nullable=True),
            sa.Column('credit_limit', sa.Numeric(18,2), nullable=True),
            sa.Column('einvoice_credit_quota', sa.Numeric(18,2), nullable=True),
            sa.Column('industry', sa.String(length=255), nullable=True),
            sa.Column('last_trade_date', sa.Date(), nullable=True),
            sa.Column('party_code', sa.String(length=255), nullable=True),
            sa.Column('party_full_name', sa.String(length=255), nullable=True),
            sa.Column('party_type', sa.String(length=255), nullable=True),
            sa.Column('payment_terms', sa.String(length=255), nullable=True),
            sa.Column('primary_contact', sa.String(length=255), nullable=True),
            sa.Column('registered_address', sa.String(length=255), nullable=True),
            sa.Column('registered_phone', sa.String(length=255), nullable=True),
            sa.Column('risk_level', sa.String(length=255), nullable=True),
            sa.Column('settlement_currency', sa.String(length=255), nullable=True),
            sa.Column('shipping_invoice_address', sa.String(length=255), nullable=True),
            sa.Column('tax_device_info', sa.String(length=255), nullable=True),
            sa.Column('taxpayer_type', sa.String(length=255), nullable=True)
        )
    op.create_index('ix_aux_parties_party_code', 'aux_parties', ['party_code'], unique=True)
    op.create_index('ix_aux_parties_credit_code', 'aux_parties', ['credit_code'], unique=False)

    # aux_persons <- 个人(员工/往来主体)
    op.create_table(
            'aux_persons',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('bank_account_no', sa.String(length=255), nullable=True),
            sa.Column('cnaps_code', sa.String(length=255), nullable=True),
            sa.Column('department_code', sa.String(length=255), nullable=True),
            sa.Column('employee_credit_score', sa.Numeric(18,2), nullable=True),
            sa.Column('employee_no', sa.String(length=255), nullable=True),
            sa.Column('employment_type', sa.String(length=255), nullable=True),
            sa.Column('hire_date', sa.Date(), nullable=True),
            sa.Column('housing_fund_account', sa.String(length=255), nullable=True),
            sa.Column('id_card_no', sa.String(length=255), nullable=True),
            sa.Column('internal_arap_subject', sa.String(length=255), nullable=True),
            sa.Column('job_title', sa.String(length=255), nullable=True),
            sa.Column('name', sa.String(length=255), nullable=True),
            sa.Column('social_security_city', sa.String(length=255), nullable=True),
            sa.Column('special_additional_deduction', sa.Text(), nullable=True),
            sa.Column('tax_residency', sa.String(length=255), nullable=True),
            sa.Column('termination_date', sa.Date(), nullable=True)
        )
    op.create_index('ix_aux_persons_employee_no', 'aux_persons', ['employee_no'], unique=False)
    op.create_index('ix_aux_persons_id_card_no', 'aux_persons', ['id_card_no'], unique=False)

    # aux_bank_accounts <- 银行账户
    op.create_table(
            'aux_bank_accounts',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('account_internal_code', sa.String(length=255), nullable=True),
            sa.Column('account_name', sa.String(length=255), nullable=True),
            sa.Column('account_status', sa.String(length=255), nullable=True),
            sa.Column('account_type', sa.String(length=255), nullable=True),
            sa.Column('balance_alert_threshold', sa.Numeric(18,2), nullable=True),
            sa.Column('bank_account_no', sa.String(length=255), nullable=True),
            sa.Column('bank_connect_config_id', sa.Text(), nullable=True),
            sa.Column('bank_full_name', sa.String(length=255), nullable=True),
            sa.Column('cash_pool_flag', sa.Boolean(), nullable=True),
            sa.Column('close_date', sa.Date(), nullable=True),
            sa.Column('cnaps_code', sa.String(length=255), nullable=True),
            sa.Column('last_reconciliation_date', sa.Date(), nullable=True),
            sa.Column('legal_entity_id', sa.String(length=255), nullable=True),
            sa.Column('open_date', sa.Date(), nullable=True),
            sa.Column('reconciliation_method', sa.String(length=255), nullable=True),
            sa.Column('unreconciled_flag', sa.Boolean(), nullable=True)
        )
    op.create_index('ix_aux_bank_accounts_account_internal_code', 'aux_bank_accounts', ['account_internal_code'], unique=True)
    op.create_index('ix_aux_bank_accounts_bank_account_no', 'aux_bank_accounts', ['bank_account_no'], unique=False)

    # aux_projects <- 项目
    op.create_table(
            'aux_projects',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('budget_control_policy', sa.Numeric(18,2), nullable=True),
            sa.Column('budget_total', sa.Numeric(18,2), nullable=True),
            sa.Column('contract_ids', sa.Text(), nullable=True),
            sa.Column('cost_center_code', sa.String(length=255), nullable=True),
            sa.Column('customer_party_code', sa.String(length=255), nullable=True),
            sa.Column('department_code', sa.String(length=255), nullable=True),
            sa.Column('end_date', sa.Date(), nullable=True),
            sa.Column('legal_entity_id', sa.String(length=255), nullable=True),
            sa.Column('project_code', sa.String(length=255), nullable=True),
            sa.Column('project_manager', sa.String(length=255), nullable=True),
            sa.Column('project_name', sa.String(length=255), nullable=True),
            sa.Column('project_status', sa.String(length=255), nullable=True),
            sa.Column('remarks', sa.String(length=255), nullable=True),
            sa.Column('revenue_center_code', sa.String(length=255), nullable=True),
            sa.Column('start_date', sa.Date(), nullable=True)
        )
    op.create_index('ix_aux_projects_project_code', 'aux_projects', ['project_code'], unique=True)

def downgrade():
    op.drop_index('ix_aux_projects_project_code', table_name='aux_projects')
    op.drop_table('aux_projects')
    op.drop_index('ix_aux_bank_accounts_account_internal_code', table_name='aux_bank_accounts')
    op.drop_index('ix_aux_bank_accounts_bank_account_no', table_name='aux_bank_accounts')
    op.drop_table('aux_bank_accounts')
    op.drop_index('ix_aux_persons_employee_no', table_name='aux_persons')
    op.drop_index('ix_aux_persons_id_card_no', table_name='aux_persons')
    op.drop_table('aux_persons')
    op.drop_index('ix_aux_parties_party_code', table_name='aux_parties')
    op.drop_index('ix_aux_parties_credit_code', table_name='aux_parties')
    op.drop_table('aux_parties')

