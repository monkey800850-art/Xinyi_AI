"""
PAYROLL-FIELD-03 migration skeleton

This file is a placeholder. Replace with your actual migration framework (Alembic/Flask-Migrate).
Goal tables:
- payroll_employees
- payroll_records
- payroll_social_housing
- payroll_tax_ytd
- payroll_attendance_snapshots

All columns should be created according to scripts/payroll/payroll_field_mapping.json.
"""

# revision identifiers, used by Alembic.
revision = "20260304185406"
down_revision = "20260303_000049"
branch_labels = None
depends_on = None

def upgrade():
    raise NotImplementedError("Fill with Alembic/Flask-Migrate operations")

def downgrade():
    raise NotImplementedError("Fill with Alembic/Flask-Migrate operations")
