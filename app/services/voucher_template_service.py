from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Tuple

from sqlalchemy import bindparam, text

from app.db import get_engine
from app.services.voucher_service import _check_period_open


class VoucherTemplateError(RuntimeError):
    def __init__(self, message: str, errors: List[Dict[str, object]] = None):
        super().__init__(message)
        self.errors = errors or []


TEMPLATES: Dict[str, Dict[str, object]] = {
    "BANK_FEE": {
        "code": "BANK_FEE",
        "name": "银行手续费",
        "required_params": ["amount", "biz_date"],
        "defaults_by_standard": {
            "enterprise": {
                "debit_subject_code": "6602",
                "credit_subject_code": "1002",
            },
            "small_enterprise": {
                "debit_subject_code": "5603",
                "credit_subject_code": "1002",
            },
        },
        "lines": [
            {
                "side": "debit",
                "subject_code": "{debit_subject_code}",
                "summary": "{summary_text}",
                "amount_field": "amount",
            },
            {
                "side": "credit",
                "subject_code": "{credit_subject_code}",
                "summary": "{summary_text}",
                "amount_field": "amount",
            },
        ],
    },
    "ASSET_DEPRECIATION": {
        "code": "ASSET_DEPRECIATION",
        "name": "固定资产折旧",
        "required_params": ["amount", "biz_date"],
        "defaults_by_standard": {
            "enterprise": {
                "debit_subject_code": "6602",
                "credit_subject_code": "1602",
            },
            "small_enterprise": {
                "debit_subject_code": "5602",
                "credit_subject_code": "1602",
            },
        },
        "lines": [
            {
                "side": "debit",
                "subject_code": "{debit_subject_code}",
                "summary": "{summary_text}",
                "amount_field": "amount",
            },
            {
                "side": "credit",
                "subject_code": "{credit_subject_code}",
                "summary": "{summary_text}",
                "amount_field": "amount",
            },
        ],
    },
    "EXPENSE_REIMBURSEMENT_PAYMENT": {
        "code": "EXPENSE_REIMBURSEMENT_PAYMENT",
        "name": "费用报销付款",
        "required_params": ["amount", "biz_date"],
        "defaults_by_standard": {
            "enterprise": {
                "debit_subject_code": "6602",
                "credit_subject_code": "1002",
            },
            "small_enterprise": {
                "debit_subject_code": "5602",
                "credit_subject_code": "1002",
            },
        },
        "lines": [
            {
                "side": "debit",
                "subject_code": "{debit_subject_code}",
                "summary": "{summary_text}",
                "amount_field": "amount",
            },
            {
                "side": "credit",
                "subject_code": "{credit_subject_code}",
                "summary": "{summary_text}",
                "amount_field": "amount",
            },
        ],
    },
}


def _parse_decimal(value) -> Decimal:
    if value is None or value == "":
        raise ValueError("amount_required")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("amount_invalid")


def _parse_date(value) -> date:
    if isinstance(value, date):
        return value
    if not value:
        raise ValueError("biz_date_required")
    try:
        return date.fromisoformat(str(value))
    except Exception:
        raise ValueError("biz_date_invalid")


def _safe_format(template: str, params: Dict[str, object]) -> str:
    class _Missing(dict):
        def __missing__(self, key):
            return "{" + key + "}"

    return str(template or "").format_map(_Missing(params))


def _load_subjects(conn, book_id: int, codes: List[str]) -> Dict[str, Dict[str, object]]:
    if not codes:
        return {}
    rows = conn.execute(
        text(
            "SELECT code, name, is_enabled FROM subjects "
            "WHERE book_id=:book_id AND code IN :codes"
        ).bindparams(bindparam("codes", expanding=True)),
        {"book_id": book_id, "codes": list(set(codes))},
    ).fetchall()
    out: Dict[str, Dict[str, object]] = {}
    for r in rows:
        out[r.code] = {"name": r.name or "", "is_enabled": int(r.is_enabled or 0)}
    return out


def _load_book_standard(conn, book_id: int) -> str:
    row = conn.execute(
        text("SELECT accounting_standard FROM books WHERE id=:book_id LIMIT 1"),
        {"book_id": book_id},
    ).fetchone()
    return str((row.accounting_standard if row else "") or "").strip()


def build_template_preview(
    book_id: int,
    template_code: str,
    params: Dict[str, object],
    operator: str = "",
    role: str = "",
) -> Dict[str, object]:
    errors: List[Dict[str, object]] = []
    validations: List[Dict[str, object]] = []
    warnings: List[str] = []

    try:
        book_id = int(book_id)
    except Exception:
        raise VoucherTemplateError("validation_error", [{"field": "book_id", "message": "book_id must be integer"}])

    tpl = TEMPLATES.get((template_code or "").strip().upper())
    if not tpl:
        raise VoucherTemplateError("validation_error", [{"field": "template_code", "message": "unsupported_template"}])

    merged = dict(params or {})

    for key in tpl.get("required_params") or []:
        if merged.get(key) in (None, ""):
            errors.append({"field": key, "message": "required"})

    amount = None
    biz_date = None
    if not errors:
        try:
            amount = _parse_decimal(merged.get("amount"))
            if amount <= 0:
                errors.append({"field": "amount", "message": "amount must be > 0"})
        except ValueError:
            errors.append({"field": "amount", "message": "amount invalid"})
        try:
            biz_date = _parse_date(merged.get("biz_date"))
        except ValueError:
            errors.append({"field": "biz_date", "message": "biz_date invalid"})

    validations.append({"rule": "date_valid", "ok": not any(e["field"] == "biz_date" for e in errors)})

    if errors:
        return {
            "success": False,
            "template_info": {"code": tpl["code"], "name": tpl["name"]},
            "voucher_draft": {"header": {}, "lines": []},
            "validations": validations + [
                {"rule": "period_open", "ok": False, "message": "skipped"},
                {"rule": "subject_valid", "ok": False, "message": "skipped"},
                {"rule": "debit_credit_balanced", "ok": False, "message": "skipped"},
            ],
            "errors": errors,
            "warnings": warnings,
            "audit_hint": {
                "action": "voucher_template_preview",
                "operator": operator or "",
                "operator_role": role or "",
                "persisted": False,
            },
        }

    engine = get_engine()
    with engine.connect() as conn:
        standard = _load_book_standard(conn, book_id)
        defaults_map = tpl.get("defaults_by_standard") or {}
        defaults = dict(defaults_map.get(standard) or defaults_map.get("enterprise") or {})
        for key, value in defaults.items():
            merged.setdefault(key, value)
        if not merged.get("summary_text"):
            merged["summary_text"] = f"{tpl.get('name', '')} {merged.get('counterparty', '')}".strip()

        raw_lines: List[Dict[str, object]] = []
        for idx, line_cfg in enumerate(tpl.get("lines") or []):
            field = line_cfg.get("amount_field") or "amount"
            line_amount = amount if field == "amount" else _parse_decimal(merged.get(field))
            subject_code = _safe_format(str(line_cfg.get("subject_code") or ""), merged)
            summary = _safe_format(str(line_cfg.get("summary") or ""), merged)
            if not summary:
                summary = str(tpl.get("name") or "")
            debit = line_amount if line_cfg.get("side") == "debit" else Decimal("0")
            credit = line_amount if line_cfg.get("side") == "credit" else Decimal("0")
            raw_lines.append(
                {
                    "line_no": idx + 1,
                    "summary": summary,
                    "subject_code": subject_code,
                    "debit": debit,
                    "credit": credit,
                }
            )

        total_debit = sum((x["debit"] for x in raw_lines), Decimal("0"))
        total_credit = sum((x["credit"] for x in raw_lines), Decimal("0"))
        diff = total_debit - total_credit
        balance_ok = diff == 0
        validations.append(
            {
                "rule": "debit_credit_balanced",
                "ok": balance_ok,
                "diff": float(diff),
                "message": "" if balance_ok else f"not balanced, diff={diff}",
            }
        )
        if not balance_ok:
            errors.append({"field": "balance", "message": f"debit_credit_not_balanced diff={diff}"})

        period_ok, period_msg = _check_period_open(conn, book_id, biz_date)
        validations.append({"rule": "period_open", "ok": period_ok, "message": period_msg or ""})
        if not period_ok:
            errors.append({"field": "biz_date", "message": period_msg or "accounting_period_closed"})

        codes = [x["subject_code"] for x in raw_lines]
        subject_map = _load_subjects(conn, book_id, codes)

    subject_errors = 0
    output_lines: List[Dict[str, object]] = []
    for row in raw_lines:
        subject = subject_map.get(row["subject_code"])
        if not subject:
            errors.append(
                {
                    "field": "subject_code",
                    "line_no": row["line_no"],
                    "message": f"subject_not_found:{row['subject_code']}",
                }
            )
            subject_errors += 1
            subject_name = ""
        elif subject.get("is_enabled") != 1:
            errors.append(
                {
                    "field": "subject_code",
                    "line_no": row["line_no"],
                    "message": f"subject_disabled:{row['subject_code']}",
                }
            )
            subject_errors += 1
            subject_name = subject.get("name") or ""
        else:
            subject_name = subject.get("name") or ""

        output_lines.append(
            {
                "line_no": row["line_no"],
                "summary": row["summary"],
                "subject_code": row["subject_code"],
                "subject_name": subject_name,
                "debit": float(row["debit"]),
                "credit": float(row["credit"]),
            }
        )

    validations.append(
        {
            "rule": "subject_valid",
            "ok": subject_errors == 0,
            "message": "" if subject_errors == 0 else f"{subject_errors} subject issues",
        }
    )

    return {
        "success": len(errors) == 0,
        "template_info": {"code": tpl["code"], "name": tpl["name"]},
        "voucher_draft": {
            "header": {
                "book_id": book_id,
                "voucher_date": biz_date.isoformat(),
                "voucher_word": "记",
                "status": "draft",
                "maker": operator or "",
            },
            "lines": output_lines,
        },
        "validations": validations,
        "errors": errors,
        "warnings": warnings,
        "audit_hint": {
            "action": "voucher_template_preview",
            "operator": operator or "",
            "operator_role": role or "",
            "persisted": False,
            "note": "preview only, no voucher persisted",
        },
    }


def list_template_candidates(book_id: int) -> Dict[str, object]:
    return {
        "book_id": int(book_id),
        "items": [{"code": t["code"], "name": t["name"]} for t in TEMPLATES.values()],
    }


def get_template_detail(template_code: str) -> Dict[str, object]:
    code = (template_code or "").strip().upper()
    tpl = TEMPLATES.get(code)
    if not tpl:
        raise VoucherTemplateError("template_not_found")
    return {"template": tpl}


def build_template_draft(
    book_id: int,
    template_code: str,
    params: Dict[str, object],
    operator: str = "",
    role: str = "",
) -> Dict[str, object]:
    return build_template_preview(book_id, template_code, params, operator=operator, role=role)
