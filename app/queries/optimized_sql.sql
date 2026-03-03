-- P2-PERF-02: Slow query governance for existing core tables
-- Apply on MySQL: mysql -h127.0.0.1 -uroot -p****** xinyi_ai < app/queries/optimized_sql.sql

USE xinyi_ai;

-- 1) Current context (slow log switch and threshold)
SHOW VARIABLES LIKE 'slow_query_log';
SHOW VARIABLES LIKE 'slow_query_log_file';
SHOW VARIABLES LIKE 'long_query_time';

-- 2) Representative TOP SQL (from reimbursement/payment/consolidation/bank paths)
-- Reimbursement list
EXPLAIN
SELECT id, title, applicant, department, total_amount, status, reject_reason, created_at
FROM reimbursements
WHERE book_id = 1
ORDER BY id DESC
LIMIT 50;

-- Payment list
EXPLAIN
SELECT id, title, payee_name, pay_method, amount, status
FROM payment_requests
WHERE book_id = 1
ORDER BY id DESC
LIMIT 50;

-- Bank unmatched list (reconcile)
EXPLAIN
SELECT id, bank_account_id, txn_date, amount, match_status
FROM bank_transactions
WHERE book_id = 1
  AND COALESCE(match_status, 'unmatched') = 'unmatched'
ORDER BY id DESC
LIMIT 100;

-- Consolidation adjustment set list
EXPLAIN
SELECT id, group_id, period, batch_id, status, created_at
FROM consolidation_adjustments
WHERE group_id = 1
  AND period = '2026-03'
ORDER BY id DESC
LIMIT 50;

-- Voucher trend source query (dashboard / reports)
EXPLAIN
SELECT v.voucher_date AS d, SUM(vl.debit) AS debit_sum
FROM vouchers v
JOIN voucher_lines vl ON vl.voucher_id = v.id
WHERE v.book_id = 1
  AND v.status = 'posted'
  AND v.voucher_date BETWEEN '2026-01-01' AND '2026-12-31'
GROUP BY v.voucher_date
ORDER BY v.voucher_date;

-- 3) Index strategy (guarded create)
-- reimbursements(book_id, id)
SET @idx_exists := (
  SELECT COUNT(*)
  FROM information_schema.statistics
  WHERE table_schema = DATABASE()
    AND table_name = 'reimbursements'
    AND index_name = 'ix_reimbursements_book_id_id'
);
SET @ddl := IF(@idx_exists = 0,
  'CREATE INDEX ix_reimbursements_book_id_id ON reimbursements(book_id, id)',
  'SELECT \"skip ix_reimbursements_book_id_id\"'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- payment_requests(book_id, id)
SET @idx_exists := (
  SELECT COUNT(*)
  FROM information_schema.statistics
  WHERE table_schema = DATABASE()
    AND table_name = 'payment_requests'
    AND index_name = 'ix_payment_requests_book_id_id'
);
SET @ddl := IF(@idx_exists = 0,
  'CREATE INDEX ix_payment_requests_book_id_id ON payment_requests(book_id, id)',
  'SELECT \"skip ix_payment_requests_book_id_id\"'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- bank_transactions(book_id, match_status, id)
SET @idx_exists := (
  SELECT COUNT(*)
  FROM information_schema.statistics
  WHERE table_schema = DATABASE()
    AND table_name = 'bank_transactions'
    AND index_name = 'ix_bank_transactions_book_match_id'
);
SET @ddl := IF(@idx_exists = 0,
  'CREATE INDEX ix_bank_transactions_book_match_id ON bank_transactions(book_id, match_status, id)',
  'SELECT \"skip ix_bank_transactions_book_match_id\"'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- consolidation_adjustments(group_id, period, id)
SET @idx_exists := (
  SELECT COUNT(*)
  FROM information_schema.statistics
  WHERE table_schema = DATABASE()
    AND table_name = 'consolidation_adjustments'
    AND index_name = 'ix_conso_adj_group_period_id'
);
SET @ddl := IF(@idx_exists = 0,
  'CREATE INDEX ix_conso_adj_group_period_id ON consolidation_adjustments(group_id, period, id)',
  'SELECT \"skip ix_conso_adj_group_period_id\"'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- consolidation_adjustments(group_id, period, batch_id)
SET @idx_exists := (
  SELECT COUNT(*)
  FROM information_schema.statistics
  WHERE table_schema = DATABASE()
    AND table_name = 'consolidation_adjustments'
    AND index_name = 'ix_conso_adj_group_period_batch'
);
SET @ddl := IF(@idx_exists = 0,
  'CREATE INDEX ix_conso_adj_group_period_batch ON consolidation_adjustments(group_id, period, batch_id)',
  'SELECT \"skip ix_conso_adj_group_period_batch\"'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- vouchers(book_id, status, voucher_date, id)
SET @idx_exists := (
  SELECT COUNT(*)
  FROM information_schema.statistics
  WHERE table_schema = DATABASE()
    AND table_name = 'vouchers'
    AND index_name = 'ix_vouchers_book_status_date_id'
);
SET @ddl := IF(@idx_exists = 0,
  'CREATE INDEX ix_vouchers_book_status_date_id ON vouchers(book_id, status, voucher_date, id)',
  'SELECT \"skip ix_vouchers_book_status_date_id\"'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Optional tax invoice index only when column exists
SET @col_exists := (
  SELECT COUNT(*)
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'tax_invoices'
    AND column_name = 'verification_status'
);
SET @idx_exists := (
  SELECT COUNT(*)
  FROM information_schema.statistics
  WHERE table_schema = DATABASE()
    AND table_name = 'tax_invoices'
    AND index_name = 'ix_tax_invoices_book_verify'
);
SET @ddl := IF(@col_exists > 0 AND @idx_exists = 0,
  'CREATE INDEX ix_tax_invoices_book_verify ON tax_invoices(book_id, verification_status)',
  'SELECT \"skip ix_tax_invoices_book_verify\"'
);
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 4) Verify newly added indexes
SELECT table_name, index_name, GROUP_CONCAT(column_name ORDER BY seq_in_index) AS idx_cols
FROM information_schema.statistics
WHERE table_schema = DATABASE()
  AND index_name IN (
    'ix_reimbursements_book_id_id',
    'ix_payment_requests_book_id_id',
    'ix_bank_transactions_book_match_id',
    'ix_conso_adj_group_period_id',
    'ix_conso_adj_group_period_batch',
    'ix_vouchers_book_status_date_id',
    'ix_tax_invoices_book_verify'
  )
GROUP BY table_name, index_name
ORDER BY table_name, index_name;
