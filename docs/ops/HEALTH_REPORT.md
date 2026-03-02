# Repository Health Report

- Generated at: 2026-03-02 12:48:53 +0800
- Scope: cleanup baseline for determinable/reproducible regression

## 1) git status -sb
```bash
$ git status -sb
## main...origin/main [ahead 8]
 M .gitignore
 M app.py
 M app/db.py
A  app/db_router.py
 M app/services/asset_service.py
 M app/services/autocomplete_service.py
 M app/services/aux_reports_service.py
 M app/services/book_service.py
A  app/services/consolidation_manage_service.py
A  app/services/consolidation_parameters_service.py
A  app/services/consolidation_service.py
 M app/services/dashboard_service.py
 M app/services/depreciation_service.py
 M app/services/export_service.py
 M app/services/ledger_service.py
 M app/services/payment_service.py
 M app/services/reimbursement_service.py
 M app/services/system_service.py
 M app/services/trial_balance_service.py
 M app/services/voucher_service.py
 M app/services/voucher_template_service.py
A  migrations/versions/20260301_000021_consolidation_models.py
A  migrations/versions/20260302_000026_consolidation_parameters.py
 M scripts/ops/db_backup.sh
 M scripts/ops/db_restore_verify.sh
 M scripts/ops/health_check.sh
 M scripts/ops/min_regression.sh
 M static/css/aux_reports.css
 M static/css/dashboard.css
 M static/css/subject_ledger.css
 M static/css/trial_balance.css
 M static/css/voucher_entry.css
 M static/js/asset_changes.js
 M static/js/asset_depreciation.js
 M static/js/asset_depreciation_reports.js
 M static/js/asset_ledger.js
 M static/js/assets.js
 M static/js/assets_cards.js
 M static/js/autocomplete.js
 M static/js/aux_reports.js
 M static/js/bank_import.js
 M static/js/bank_reconcile.js
 M static/js/dashboard.js
 M static/js/payments.js
 M static/js/reimbursements.js
 M static/js/subject_ledger.js
 M static/js/tax_invoices.js
 M static/js/tax_rules.js
 M static/js/tax_summary.js
 M static/js/trial_balance.js
 M static/js/voucher_entry.js
 M templates/asset_categories.html
 M templates/asset_changes.html
 M templates/asset_depreciation.html
 M templates/asset_depreciation_reports.html
 M templates/asset_ledger.html
 M templates/assets_detail.html
 M templates/assets_list.html
 M templates/aux_reports.html
 M templates/bank_import.html
 M templates/bank_reconcile.html
 M templates/dashboard.html
 M templates/payments_detail.html
 M templates/payments_list.html
 M templates/reimbursements_detail.html
 M templates/reimbursements_list.html
 M templates/subject_ledger.html
 M templates/tax_invoices.html
 M templates/tax_rules.html
 M templates/tax_summary.html
 M templates/trial_balance.html
 M templates/voucher_entry.html
A  tests/test_arch02_db_router.py
A  tests/test_arch02_service_router_integration.py
AM tests/test_arch04_consolidation_model.py
AM tests/test_arch05_consolidation_reports.py
?? _change_buckets.tsv
?? app/services/master_data_service.py
?? app/services/voucher_import_service.py
?? docs/R5_3_retest_notes.txt
?? docs/ops/HEALTH_REPORT.md
?? docs/roadmap/
?? migrations/versions/20260228_000018_voucher_line_aux_items.py
?? migrations/versions/20260228_000019_tenant_datasource_mapping.py
?? migrations/versions/20260301_000020_voucher_aux_sort_order.py
?? migrations/versions/20260301_000022_master_data_business_fields.py
?? migrations/versions/20260301_000023_seed_init_templates_and_hidden_flags.py
?? migrations/versions/20260301_000024_template_preset_enhance.py
?? scripts/ops/init_tenant_defaults.py
?? scripts/reset_and_seed_sample_data.py
?? static/css/main_layout.css
?? static/css/system_book_init.css
?? static/css/system_books.css
?? static/css/system_consolidation.css
?? static/css/system_init.css
?? static/css/voucher_import.css
?? static/js/main_layout.js
?? static/js/master_data.js
?? static/js/navigation_rules.js
?? static/js/request_context.js
?? static/js/subject_aux_config.js
?? static/js/system_book_init.js
?? static/js/system_books.js
?? static/js/system_consolidation.js
?? static/js/system_init.js
?? static/js/ui_feedback.js
?? static/js/voucher_import.js
?? templates/main_layout.html
?? templates/master_data.html
?? templates/subject_aux_config.html
?? templates/system_book_init.html
?? templates/system_books.html
?? templates/system_consolidation.html
?? templates/system_init.html
?? templates/voucher_import.html
?? tests/test_biz01_master_data_real_usable.py
?? tests/test_biz02_subject_aux_rules.py
?? tests/test_biz03_voucher_multi_aux.py
?? tests/test_biz04_rollback_actions.py
?? tests/test_biz05_ledger_drill_rules.py
?? tests/test_biz06_aux_query_model.py
?? tests/test_book_mt_step4_2_trial_balance_scope.py
?? tests/test_step4_1_fix3_virtual_create_compat.py
```

## 2) Untracked files count by key directory
```bash
$ git status --porcelain=v1 -uall | awk ...
app/: 2
tests/: 8
migrations/: 6
templates/: 8
static/: 17
docs/: 3
other: 3
```

## 3) Colon filename scan (find . -name '*:*')
```bash
$ find . -name '*:*'
```
