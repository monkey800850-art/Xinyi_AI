import json
from datetime import date
from decimal import Decimal
from typing import Dict, List

from sqlalchemy import text

from app.db_router import get_connection_provider


class ConsolidationReportGenerationError(RuntimeError):
    pass


RULE_CODE = "CONS_REPORTS_GEN"
SOURCE = "generated"


def _parse_positive_int(value: object, field: str) -> int:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationReportGenerationError(f"{field}_required")
    try:
        parsed = int(raw)
    except Exception as err:
        raise ConsolidationReportGenerationError(f"{field}_invalid") from err
    if parsed <= 0:
        raise ConsolidationReportGenerationError(f"{field}_invalid")
    return parsed


def _parse_period(value: object, field: str) -> str:
    raw = str(value or "").strip()
    if len(raw) != 7 or raw[4] != "-":
        raise ConsolidationReportGenerationError(f"{field}_invalid")
    yy = raw[:4]
    mm = raw[5:]
    if not yy.isdigit() or not mm.isdigit():
        raise ConsolidationReportGenerationError(f"{field}_invalid")
    month = int(mm)
    if month < 1 or month > 12:
        raise ConsolidationReportGenerationError(f"{field}_invalid")
    return f"{int(yy):04d}-{month:02d}"


def _as_of_to_period(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationReportGenerationError("as_of_required")
    try:
        parsed = date.fromisoformat(raw)
    except Exception as err:
        raise ConsolidationReportGenerationError("as_of_invalid") from err
    return parsed.strftime("%Y-%m")


def _to_decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value if value is not None else "0"))
    except Exception:
        return Decimal("0")


def _parse_lines_json(value: object) -> List[Dict[str, object]]:
    try:
        parsed = json.loads(str(value or "[]"))
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _ensure_report_snapshot_table(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS consolidation_report_snapshots (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                group_id BIGINT NOT NULL,
                period VARCHAR(7) NOT NULL,
                report_code VARCHAR(64) NOT NULL,
                template_code VARCHAR(64) NOT NULL,
                source VARCHAR(32) NOT NULL DEFAULT 'generated',
                rule_code VARCHAR(64) NOT NULL DEFAULT 'CONS_REPORTS_GEN',
                batch_id VARCHAR(64) NOT NULL,
                status VARCHAR(16) NOT NULL DEFAULT 'draft',
                template_json JSON NOT NULL,
                report_json JSON NOT NULL,
                operator_id BIGINT NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uq_conso_report_snapshot (group_id, period, report_code)
            )
            """
        )
    )


def _build_templates() -> List[Dict[str, object]]:
    return [
        {"template_code": "RPT_BS_V1", "report_code": "BALANCE_SHEET", "name": "资产负债表", "sections": ["资产", "负债", "所有者权益"]},
        {"template_code": "RPT_IS_V1", "report_code": "INCOME_STATEMENT", "name": "利润表", "sections": ["营业收入", "营业成本", "期间费用", "净利润"]},
        {"template_code": "RPT_CF_V1", "report_code": "CASH_FLOW", "name": "现金流量表", "sections": ["经营活动", "投资活动", "筹资活动", "现金净增加额"]},
        {"template_code": "RPT_SE_V1", "report_code": "EQUITY_CHANGE", "name": "所有者权益变动表", "sections": ["期初权益", "当期净利润", "其他变动", "期末权益"]},
    ]


def _aggregate_subject_totals(rows: List[object]) -> Dict[str, Dict[str, Decimal]]:
    totals: Dict[str, Dict[str, Decimal]] = {}
    for row in rows:
        for line in _parse_lines_json(row.lines_json):
            if not isinstance(line, dict):
                continue
            subject_code = str(line.get("subject_code") or "").strip()
            if not subject_code:
                continue
            debit = _to_decimal(line.get("debit"))
            credit = _to_decimal(line.get("credit"))
            bucket = totals.setdefault(subject_code, {"debit": Decimal("0"), "credit": Decimal("0")})
            bucket["debit"] += debit
            bucket["credit"] += credit
    return totals


def _sum_positive(values: List[Decimal]) -> Decimal:
    total = Decimal("0")
    for v in values:
        if v > 0:
            total += v
    return total


def _build_reports(subject_totals: Dict[str, Dict[str, Decimal]]) -> List[Dict[str, object]]:
    nets: Dict[str, Decimal] = {}
    for code, bucket in subject_totals.items():
        nets[code] = (bucket["debit"] - bucket["credit"]).quantize(Decimal("0.01"))

    assets = _sum_positive([v for k, v in nets.items() if k.startswith("1")])
    liabilities = _sum_positive([abs(v) for k, v in nets.items() if k.startswith("2") and v < 0])
    equity = _sum_positive([abs(v) for k, v in nets.items() if k.startswith("3") and v < 0])

    revenue = _sum_positive([abs(v) for k, v in nets.items() if k.startswith("6") and not k.startswith("66") and v < 0])
    cost = _sum_positive([v for k, v in nets.items() if k.startswith("5") and v > 0])
    expense = _sum_positive([v for k, v in nets.items() if k.startswith("66") and v > 0])
    net_profit = (revenue - cost - expense).quantize(Decimal("0.01"))

    cash_net = sum([v for k, v in nets.items() if k.startswith("1001") or k.startswith("1002")], Decimal("0")).quantize(Decimal("0.01"))
    investing = sum([v for k, v in nets.items() if k.startswith("15")], Decimal("0")).quantize(Decimal("0.01"))
    financing = sum([v for k, v in nets.items() if k.startswith("4")], Decimal("0")).quantize(Decimal("0.01"))

    other_equity_change = sum([(-v) for k, v in nets.items() if k.startswith("3")], Decimal("0")).quantize(Decimal("0.01"))
    opening_equity = Decimal("0.00")
    closing_equity = (opening_equity + net_profit + other_equity_change).quantize(Decimal("0.01"))

    return [
        {
            "report_code": "BALANCE_SHEET",
            "name": "资产负债表",
            "items": [
                {"item_code": "asset_total", "label": "资产合计", "amount": float(assets)},
                {"item_code": "liability_total", "label": "负债合计", "amount": float(liabilities)},
                {"item_code": "equity_total", "label": "所有者权益合计", "amount": float(equity)},
                {"item_code": "liability_equity_total", "label": "负债和权益合计", "amount": float((liabilities + equity).quantize(Decimal('0.01')))},
            ],
        },
        {
            "report_code": "INCOME_STATEMENT",
            "name": "利润表",
            "items": [
                {"item_code": "revenue", "label": "营业收入", "amount": float(revenue)},
                {"item_code": "cost", "label": "营业成本", "amount": float(cost)},
                {"item_code": "expense", "label": "期间费用", "amount": float(expense)},
                {"item_code": "net_profit", "label": "净利润", "amount": float(net_profit)},
            ],
        },
        {
            "report_code": "CASH_FLOW",
            "name": "现金流量表",
            "items": [
                {"item_code": "operating_cash_net", "label": "经营活动现金净额", "amount": float(cash_net)},
                {"item_code": "investing_cash_net", "label": "投资活动现金净额", "amount": float(investing)},
                {"item_code": "financing_cash_net", "label": "筹资活动现金净额", "amount": float(financing)},
                {"item_code": "cash_net_increase", "label": "现金及现金等价物净增加额", "amount": float((cash_net + investing + financing).quantize(Decimal('0.01')))},
            ],
        },
        {
            "report_code": "EQUITY_CHANGE",
            "name": "所有者权益变动表",
            "items": [
                {"item_code": "opening_equity", "label": "期初权益", "amount": float(opening_equity)},
                {"item_code": "current_profit", "label": "当期净利润", "amount": float(net_profit)},
                {"item_code": "other_change", "label": "其他变动", "amount": float(other_equity_change)},
                {"item_code": "closing_equity", "label": "期末权益", "amount": float(closing_equity)},
            ],
        },
    ]


def generate_report_templates_and_merge_reports(payload: Dict[str, object], operator_id: object = 1) -> Dict[str, object]:
    group_id = _parse_positive_int(payload.get("consolidation_group_id") or payload.get("group_id"), "consolidation_group_id")
    period_raw = str(payload.get("period") or "").strip()
    if period_raw:
        period = _parse_period(period_raw, "period")
    else:
        period = _as_of_to_period(payload.get("as_of"))
    operator = _parse_positive_int(operator_id, "operator_id")
    batch_id = f"RPT-{group_id}-{period.replace('-', '')}"

    provider = get_connection_provider()
    with provider.begin() as conn:
        _ensure_report_snapshot_table(conn)
        exists = conn.execute(text("SELECT id FROM consolidation_groups WHERE id=:gid LIMIT 1"), {"gid": group_id}).fetchone()
        if not exists:
            raise ConsolidationReportGenerationError("consolidation_group_not_found")
        rows = conn.execute(
            text(
                """
                SELECT id, lines_json
                FROM consolidation_adjustments
                WHERE group_id=:group_id
                  AND period=:period
                  AND status IN ('draft', 'reviewed', 'locked', 'active')
                  AND COALESCE(source, '')='generated'
                  AND COALESCE(rule_code, '') <> ''
                  AND rule_code <> :rule_code
                ORDER BY id ASC
                """
            ),
            {"group_id": group_id, "period": period, "rule_code": RULE_CODE},
        ).fetchall()
        if not rows:
            raise ConsolidationReportGenerationError("no_generated_adjustments_for_report_generation")

        templates = _build_templates()
        reports = _build_reports(_aggregate_subject_totals(rows))
        report_by_code = {str(r["report_code"]): r for r in reports}

        for template in templates:
            report_code = str(template["report_code"])
            report = report_by_code.get(report_code) or {"report_code": report_code, "name": "", "items": []}
            existing = conn.execute(
                text(
                    """
                    SELECT id
                    FROM consolidation_report_snapshots
                    WHERE group_id=:group_id AND period=:period AND report_code=:report_code
                    LIMIT 1
                    """
                ),
                {"group_id": group_id, "period": period, "report_code": report_code},
            ).fetchone()
            params = {
                "group_id": group_id,
                "period": period,
                "report_code": report_code,
                "template_code": str(template["template_code"]),
                "batch_id": batch_id,
                "template_json": json.dumps(template, ensure_ascii=False),
                "report_json": json.dumps(report, ensure_ascii=False),
                "operator_id": operator,
            }
            if existing:
                conn.execute(
                    text(
                        """
                        UPDATE consolidation_report_snapshots
                        SET template_code=:template_code,
                            source='generated',
                            rule_code=:rule_code,
                            batch_id=:batch_id,
                            status='draft',
                            template_json=:template_json,
                            report_json=:report_json,
                            operator_id=:operator_id,
                            updated_at=NOW()
                        WHERE id=:id
                        """
                    ),
                    {**params, "id": int(existing.id), "rule_code": RULE_CODE},
                )
            else:
                conn.execute(
                    text(
                        """
                        INSERT INTO consolidation_report_snapshots (
                            group_id, period, report_code, template_code, source, rule_code, batch_id, status,
                            template_json, report_json, operator_id
                        ) VALUES (
                            :group_id, :period, :report_code, :template_code, 'generated', :rule_code, :batch_id, 'draft',
                            :template_json, :report_json, :operator_id
                        )
                        """
                    ),
                    {**params, "rule_code": RULE_CODE},
                )

    return {
        "group_id": group_id,
        "period": period,
        "batch_id": batch_id,
        "rule_code": RULE_CODE,
        "template_count": len(templates),
        "report_count": len(reports),
        "templates": templates,
        "reports": reports,
    }
