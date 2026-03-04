"""PAYROLL-BIZ-01: create payroll MVP tables"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = None
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "payroll_employees",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),

        sa.Column("employee_no", sa.String(length=64), nullable=True),
        sa.Column("employee_name", sa.String(length=255), nullable=True),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("bank_account_id", sa.Integer(), nullable=True),

        sa.Column("base_salary", sa.Numeric(18,2), nullable=True),
        sa.Column("allowance_total", sa.Numeric(18,2), nullable=True),
        sa.Column("deduction_total", sa.Numeric(18,2), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
    )
    op.create_index("ix_payroll_employees_employee_no", "payroll_employees", ["employee_no"], unique=False)
    op.create_index("ix_payroll_employees_employee_name", "payroll_employees", ["employee_name"], unique=False)

    op.create_table(
        "payroll_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),

        sa.Column("period_yyyymm", sa.String(length=7), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
    )
    op.create_index("ix_payroll_runs_period", "payroll_runs", ["period_yyyymm"], unique=False)

    op.create_table(
        "payroll_run_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),

        sa.Column("run_id", sa.Integer(), nullable=True),
        sa.Column("employee_id", sa.Integer(), nullable=True),

        sa.Column("gross_pay", sa.Numeric(18,2), nullable=True),
        sa.Column("total_deductions", sa.Numeric(18,2), nullable=True),
        sa.Column("net_pay", sa.Numeric(18,2), nullable=True),

        sa.Column("note", sa.Text(), nullable=True),
    )
    op.create_index("ix_payroll_run_lines_run_id", "payroll_run_lines", ["run_id"], unique=False)
    op.create_index("ix_payroll_run_lines_employee_id", "payroll_run_lines", ["employee_id"], unique=False)


def downgrade():
    op.drop_index("ix_payroll_run_lines_employee_id", table_name="payroll_run_lines")
    op.drop_index("ix_payroll_run_lines_run_id", table_name="payroll_run_lines")
    op.drop_table("payroll_run_lines")

    op.drop_index("ix_payroll_runs_period", table_name="payroll_runs")
    op.drop_table("payroll_runs")

    op.drop_index("ix_payroll_employees_employee_name", table_name="payroll_employees")
    op.drop_index("ix_payroll_employees_employee_no", table_name="payroll_employees")
    op.drop_table("payroll_employees")
