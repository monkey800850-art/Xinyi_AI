from decimal import Decimal
from typing import Dict, List

from app.services.consolidation_adjustment_service import regenerate_generated_adjustment_set
from app.services.consolidation_report_generation_service import (
    ConsolidationReportGenerationError,
    generate_report_templates_and_merge_reports,
)


class ConsolidationReportAutomationError(RuntimeError):
    pass


RULE_CODE = "CONS28_AUTO_ADJ"
TAG = "cons28_auto_adjustment"


def _parse_positive_int(value: object, field: str) -> int:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationReportAutomationError(f"{field}_required")
    try:
        parsed = int(raw)
    except Exception as err:
        raise ConsolidationReportAutomationError(f"{field}_invalid") from err
    if parsed <= 0:
        raise ConsolidationReportAutomationError(f"{field}_invalid")
    return parsed


def _to_decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value if value is not None else "0"))
    except Exception:
        return Decimal("0")


def _bs_delta(report_result: Dict[str, object]) -> Decimal:
    reports = report_result.get("reports") or []
    bs = None
    for item in reports:
        if str(item.get("report_code") or "") == "BALANCE_SHEET":
            bs = item
            break
    if not bs:
        raise ConsolidationReportAutomationError("balance_sheet_not_found")
    kv = {str(i.get("item_code") or ""): _to_decimal(i.get("amount")) for i in (bs.get("items") or []) if isinstance(i, dict)}
    assets = kv.get("asset_total", Decimal("0"))
    liab_eq = kv.get("liability_equity_total", Decimal("0"))
    return (assets - liab_eq).quantize(Decimal("0.01"))


def _set_id(group_id: int, period: str) -> str:
    return f"AUTOADJ-{group_id}-{period.replace('-', '')}"


def _build_adjustment_lines(set_id: str, operator_id: int, delta: Decimal) -> List[Dict[str, object]]:
    if delta == 0:
        return []
    amount = abs(delta).quantize(Decimal("0.01"))
    if delta > 0:
        # Increase equity side to match assets: Dr expense / Cr equity reserve.
        return [
            {
                "subject_code": "6601",
                "debit": str(amount),
                "credit": "0",
                "note": "CONS-28 自动调节（借费用）",
                "set_id": set_id,
                "source": "generated",
                "rule": RULE_CODE,
                "evidence_ref": set_id,
                "operator_id": str(operator_id),
            },
            {
                "subject_code": "3001",
                "debit": "0",
                "credit": str(amount),
                "note": "CONS-28 自动调节（贷权益）",
                "set_id": set_id,
                "source": "generated",
                "rule": RULE_CODE,
                "evidence_ref": set_id,
                "operator_id": str(operator_id),
            },
        ]
    # decrease equity side: Dr equity / Cr income
    return [
        {
            "subject_code": "3001",
            "debit": str(amount),
            "credit": "0",
            "note": "CONS-28 自动调节（借权益）",
            "set_id": set_id,
            "source": "generated",
            "rule": RULE_CODE,
            "evidence_ref": set_id,
            "operator_id": str(operator_id),
        },
        {
            "subject_code": "6001",
            "debit": "0",
            "credit": str(amount),
            "note": "CONS-28 自动调节（贷收入）",
            "set_id": set_id,
            "source": "generated",
            "rule": RULE_CODE,
            "evidence_ref": set_id,
            "operator_id": str(operator_id),
        },
    ]


def automate_report_generation_and_adjustment(payload: Dict[str, object], operator_id: object = 1) -> Dict[str, object]:
    group_id = _parse_positive_int(payload.get("consolidation_group_id") or payload.get("group_id"), "consolidation_group_id")
    operator = _parse_positive_int(operator_id, "operator_id")
    try:
        initial = generate_report_templates_and_merge_reports(payload, operator_id=operator)
    except ConsolidationReportGenerationError as err:
        raise ConsolidationReportAutomationError(str(err)) from err

    period = str(initial.get("period") or "")
    delta_before = _bs_delta(initial)
    adjustment_generated = False
    adjustment_set_id = ""
    adjusted_lines = 0
    final_result = initial

    if delta_before != 0:
        set_id = _set_id(group_id, period)
        lines = _build_adjustment_lines(set_id, operator, delta_before)
        if lines:
            upserted = regenerate_generated_adjustment_set(
                group_id=group_id,
                period=period,
                operator_id=operator,
                set_id=set_id,
                rule_code=RULE_CODE,
                evidence_ref=set_id,
                tag=TAG,
                generated_lines=lines,
            )
            item = dict(upserted.get("item") or {})
            adjusted_lines = len(list(item.get("lines") or lines))
            adjustment_generated = True
            adjustment_set_id = set_id
            final_result = generate_report_templates_and_merge_reports(payload, operator_id=operator)

    delta_after = _bs_delta(final_result)
    return {
        "group_id": group_id,
        "period": period,
        "rule_code": RULE_CODE,
        "initial_batch_id": str(initial.get("batch_id") or ""),
        "final_batch_id": str(final_result.get("batch_id") or ""),
        "delta_before_adjustment": float(delta_before),
        "delta_after_adjustment": float(delta_after),
        "adjustment_generated": adjustment_generated,
        "adjustment_set_id": adjustment_set_id,
        "adjustment_line_count": adjusted_lines,
        "template_count": int(final_result.get("template_count") or 0),
        "report_count": int(final_result.get("report_count") or 0),
        "reports": final_result.get("reports") or [],
    }
