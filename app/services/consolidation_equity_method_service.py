from datetime import date
from decimal import Decimal
from typing import Dict, List

from app.services.consolidation_adjustment_service import regenerate_generated_adjustment_set


class ConsolidationEquityMethodError(RuntimeError):
    pass


RULE_CODE = "EQUITY_METHOD"
SOURCE = "generated"
TAG = "equity_method"


def _parse_positive_int(value: object, field: str) -> int:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationEquityMethodError(f"{field}_required")
    try:
        parsed = int(raw)
    except Exception as err:
        raise ConsolidationEquityMethodError(f"{field}_invalid") from err
    if parsed <= 0:
        raise ConsolidationEquityMethodError(f"{field}_invalid")
    return parsed


def _parse_date(value: object, field: str) -> date:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationEquityMethodError(f"{field}_required")
    try:
        return date.fromisoformat(raw)
    except Exception as err:
        raise ConsolidationEquityMethodError(f"{field}_invalid") from err


def _to_decimal(value: object, field: str) -> Decimal:
    try:
        return Decimal(str(value if value is not None else "0"))
    except Exception as err:
        raise ConsolidationEquityMethodError(f"{field}_invalid") from err


def _parse_ratio(value: object, field: str) -> Decimal:
    ratio = _to_decimal(value, field)
    if ratio < 0:
        raise ConsolidationEquityMethodError(f"{field}_invalid")
    if ratio > 1 and ratio <= 100:
        ratio = ratio / Decimal("100")
    if ratio > 1:
        raise ConsolidationEquityMethodError(f"{field}_invalid")
    return ratio


def _period(as_of: date) -> str:
    return as_of.strftime("%Y-%m")


def _set_id(group_id: int, as_of: date, associate_entity_id: int) -> str:
    return f"EM-{group_id}-{as_of.strftime('%Y%m%d')}-{associate_entity_id}"


def _line(
    *,
    set_id: str,
    operator_id: int,
    subject_code: str,
    debit: Decimal,
    credit: Decimal,
    note: str,
) -> Dict[str, object]:
    return {
        "subject_code": subject_code,
        "debit": str(debit),
        "credit": str(credit),
        "note": note,
        "set_id": set_id,
        "source": SOURCE,
        "rule": RULE_CODE,
        "evidence_ref": set_id,
        "operator_id": str(operator_id),
    }


def _build_lines(
    *,
    set_id: str,
    operator_id: int,
    share_profit: Decimal,
    share_oci: Decimal,
    share_dividend: Decimal,
    impairment: Decimal,
) -> List[Dict[str, object]]:
    lines: List[Dict[str, object]] = []

    if share_profit != 0:
        if share_profit > 0:
            lines.append(
                _line(
                    set_id=set_id,
                    operator_id=operator_id,
                    subject_code="EM_LTI",
                    debit=share_profit,
                    credit=Decimal("0"),
                    note="权益法确认投资收益（借长期股权投资）",
                )
            )
            lines.append(
                _line(
                    set_id=set_id,
                    operator_id=operator_id,
                    subject_code="EM_INVEST_INCOME",
                    debit=Decimal("0"),
                    credit=share_profit,
                    note="权益法确认投资收益（贷投资收益）",
                )
            )
        else:
            amt = abs(share_profit)
            lines.append(
                _line(
                    set_id=set_id,
                    operator_id=operator_id,
                    subject_code="EM_INVEST_INCOME",
                    debit=amt,
                    credit=Decimal("0"),
                    note="权益法确认投资亏损（借投资收益）",
                )
            )
            lines.append(
                _line(
                    set_id=set_id,
                    operator_id=operator_id,
                    subject_code="EM_LTI",
                    debit=Decimal("0"),
                    credit=amt,
                    note="权益法确认投资亏损（贷长期股权投资）",
                )
            )

    if share_oci != 0:
        if share_oci > 0:
            lines.append(
                _line(
                    set_id=set_id,
                    operator_id=operator_id,
                    subject_code="EM_LTI",
                    debit=share_oci,
                    credit=Decimal("0"),
                    note="按权益法确认其他综合收益份额（借长期股权投资）",
                )
            )
            lines.append(
                _line(
                    set_id=set_id,
                    operator_id=operator_id,
                    subject_code="EM_OCI",
                    debit=Decimal("0"),
                    credit=share_oci,
                    note="按权益法确认其他综合收益份额（贷其他综合收益）",
                )
            )
        else:
            amt = abs(share_oci)
            lines.append(
                _line(
                    set_id=set_id,
                    operator_id=operator_id,
                    subject_code="EM_OCI",
                    debit=amt,
                    credit=Decimal("0"),
                    note="按权益法冲减其他综合收益份额（借其他综合收益）",
                )
            )
            lines.append(
                _line(
                    set_id=set_id,
                    operator_id=operator_id,
                    subject_code="EM_LTI",
                    debit=Decimal("0"),
                    credit=amt,
                    note="按权益法冲减其他综合收益份额（贷长期股权投资）",
                )
            )

    if share_dividend != 0:
        if share_dividend > 0:
            lines.append(
                _line(
                    set_id=set_id,
                    operator_id=operator_id,
                    subject_code="EM_CASH",
                    debit=share_dividend,
                    credit=Decimal("0"),
                    note="收到被投资单位分红（借货币资金）",
                )
            )
            lines.append(
                _line(
                    set_id=set_id,
                    operator_id=operator_id,
                    subject_code="EM_LTI",
                    debit=Decimal("0"),
                    credit=share_dividend,
                    note="收到被投资单位分红（贷长期股权投资）",
                )
            )
        else:
            amt = abs(share_dividend)
            lines.append(
                _line(
                    set_id=set_id,
                    operator_id=operator_id,
                    subject_code="EM_LTI",
                    debit=amt,
                    credit=Decimal("0"),
                    note="分红冲回（借长期股权投资）",
                )
            )
            lines.append(
                _line(
                    set_id=set_id,
                    operator_id=operator_id,
                    subject_code="EM_CASH",
                    debit=Decimal("0"),
                    credit=amt,
                    note="分红冲回（贷货币资金）",
                )
            )

    if impairment > 0:
        lines.append(
            _line(
                set_id=set_id,
                operator_id=operator_id,
                subject_code="EM_IMPAIRMENT_LOSS",
                debit=impairment,
                credit=Decimal("0"),
                note="长期股权投资减值（借减值损失）",
            )
        )
        lines.append(
            _line(
                set_id=set_id,
                operator_id=operator_id,
                subject_code="EM_LTI",
                debit=Decimal("0"),
                credit=impairment,
                note="长期股权投资减值（贷长期股权投资）",
            )
        )

    return lines


def generate_equity_method(payload: Dict[str, object], operator_id: object = 1) -> Dict[str, object]:
    group_id = _parse_positive_int(payload.get("consolidation_group_id") or payload.get("group_id"), "consolidation_group_id")
    associate_entity_id = _parse_positive_int(payload.get("associate_entity_id"), "associate_entity_id")
    as_of = _parse_date(payload.get("as_of") or payload.get("acquisition_date"), "as_of")
    operator = _parse_positive_int(operator_id, "operator_id")

    opening_carrying = _to_decimal(payload.get("opening_carrying_amount"), "opening_carrying_amount")
    ownership_pct = _parse_ratio(payload.get("ownership_pct"), "ownership_pct")
    net_income = _to_decimal(payload.get("net_income"), "net_income")
    oci = _to_decimal(payload.get("other_comprehensive_income"), "other_comprehensive_income")
    dividends = _to_decimal(payload.get("dividends"), "dividends")
    impairment = _to_decimal(payload.get("impairment"), "impairment")
    if impairment < 0:
        raise ConsolidationEquityMethodError("impairment_invalid")

    share_profit = (net_income * ownership_pct).quantize(Decimal("0.01"))
    share_oci = (oci * ownership_pct).quantize(Decimal("0.01"))
    share_dividend = (dividends * ownership_pct).quantize(Decimal("0.01"))
    closing_carrying = (opening_carrying + share_profit + share_oci - share_dividend - impairment).quantize(Decimal("0.01"))

    set_id = _set_id(group_id, as_of, associate_entity_id)
    lines = _build_lines(
        set_id=set_id,
        operator_id=operator,
        share_profit=share_profit,
        share_oci=share_oci,
        share_dividend=share_dividend,
        impairment=impairment.quantize(Decimal("0.01")),
    )
    if not lines:
        raise ConsolidationEquityMethodError("no_adjustment_required")

    upserted = regenerate_generated_adjustment_set(
        group_id=group_id,
        period=_period(as_of),
        operator_id=operator,
        set_id=set_id,
        rule_code=RULE_CODE,
        evidence_ref=set_id,
        tag=TAG,
        generated_lines=lines,
    )
    item = dict(upserted.get("item") or {})
    actual_lines = list(item.get("lines") or lines)
    return {
        "group_id": group_id,
        "associate_entity_id": associate_entity_id,
        "as_of": as_of.isoformat(),
        "period": _period(as_of),
        "adjustment_set_id": set_id,
        "set_id": set_id,
        "rule_code": RULE_CODE,
        "opening_carrying_amount": float(opening_carrying),
        "ownership_pct": float(ownership_pct),
        "share_profit": float(share_profit),
        "share_oci": float(share_oci),
        "share_dividend": float(share_dividend),
        "impairment": float(impairment),
        "closing_carrying_amount": float(closing_carrying),
        "preview_lines": actual_lines,
        "line_count": len(actual_lines),
        "reused_existing_set": bool(upserted.get("reused_existing_set")),
        "changed": bool(item.get("changed", True)),
    }
