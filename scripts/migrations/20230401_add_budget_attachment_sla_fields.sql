-- Reimbursement finance enhancement (budget / attachment / approval SLA)
ALTER TABLE reimbursements
    ADD COLUMN IF NOT EXISTS budget_check TINYINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS attachment_check TINYINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS approval_sla DATETIME NULL;
