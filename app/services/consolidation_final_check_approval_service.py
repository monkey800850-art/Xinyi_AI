import json
from datetime import date
from decimal import Decimal
from typing import Dict

from sqlalchemy import text

from app.db_router import get_connection_provider
from app.services.consolidation_audit_service import log_consolidation_audit


class ConsolidationFinalCheckApprovalError(RuntimeError):
    pass


RULE_CODE = "CONS29_FINAL_CHECK_APPROVAL"


def _parse_positive_int(value: object, field: str) -> int:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationFinalCheckApprovalError(f"{field}_required")
    try:
        parsed = int(raw)
    except Exception as err:
        raise ConsolidationFinalCheckApprovalError(f"{field}_invalid") from err
    if parsed <= 0:
        raise ConsolidationFinalCheckApprovalError(f"{field}_invalid")
    return parsed


def _parse_period(value: object) -> str:
    raw = str(value or "").strip()
    if len(raw) != 7 or raw[4] != "-":
        raise ConsolidationFinalCheckApprovalError("period_invalid")
    yy = raw[:4]
    mm = raw[5:]
    if not yy.isdigit() or not mm.isdigit():
        raise ConsolidationFinalCheckApprovalError("period_invalid")
    month = int(mm)
    if month < 1 or month > 12:
        raise ConsolidationFinalCheckApprovalError("period_invalid")
    return f"{int(yy):04d}-{month:02d}"


def _as_of_to_period(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationFinalCheckApprovalError("as_of_required")
    try:
        parsed = date.fromisoformat(raw)
    except Exception as err:
        raise ConsolidationFinalCheckApprovalError("as_of_invalid") from err
    return parsed.strftime("%Y-%m")


def _to_decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value if value is not None else "0"))
    except Exception:
        return Decimal("0")


def _ensure_approval_table(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS consolidation_approval_flows (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                group_id BIGINT NOT NULL,
                period VARCHAR(7) NOT NULL,
                batch_id VARCHAR(64) NOT NULL,
                check_result VARCHAR(16) NOT NULL DEFAULT 'failed',
                approval_status VARCHAR(16) NOT NULL DEFAULT 'submitted',
                approver_id BIGINT NULL,
                operator_id BIGINT NOT NULL DEFAULT 0,
                check_note VARCHAR(255) NULL,
                check_payload_json JSON NULL,
                approved_at DATETIME NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uq_conso_approval_flow (group_id, period)
            )
            """
        )
    )


def _fetch_balance_sheet_delta(conn, group_id: int, period: str) -> Decimal:
    row = conn.execute(
        text(
            """
            SELECT report_json
            FROM consolidation_report_snapshots
            WHERE group_id=:group_id
              AND period=:period
              AND report_code='BALANCE_SHEET'
            ORDER BY id DESC
            LIMIT 1
            """
        ),
        {"group_id": group_id, "period": period},
    ).fetchone()
    if not row:
        raise ConsolidationFinalCheckApprovalError("balance_sheet_not_found")
    try:
        report = json.loads(str(row.report_json or "{}"))
    except Exception:
        report = {}
    items = report.get("items") if isinstance(report, dict) else []
    if not isinstance(items, list):
        items = []
    kv = {str(i.get("item_code") or ""): _to_decimal(i.get("amount")) for i in items if isinstance(i, dict)}
    assets = kv.get("asset_total", Decimal("0"))
    liab_eq = kv.get("liability_equity_total", Decimal("0"))
    return (assets - liab_eq).quantize(Decimal("0.01"))


def run_final_check_and_approval_flow(payload: Dict[str, object], operator_id: object = 1) -> Dict[str, object]:
    group_id = _parse_positive_int(payload.get("consolidation_group_id") or payload.get("group_id"), "consolidation_group_id")
    period_raw = str(payload.get("period") or "").strip()
    period = _parse_period(period_raw) if period_raw else _as_of_to_period(payload.get("as_of"))
    operator = _parse_positive_int(operator_id, "operator_id")
    approver_id_raw = payload.get("approver_id")
    approver_id = int(approver_id_raw) if str(approver_id_raw or "").strip().isdigit() else operator
    auto_approve_raw = str(payload.get("auto_approve", "1")).strip().lower()
    auto_approve = auto_approve_raw not in {"0", "false", "no", "off"}

    required_reports = {"BALANCE_SHEET", "INCOME_STATEMENT", "CASH_FLOW", "EQUITY_CHANGE"}
    batch_id = f"FINAL-{group_id}-{period.replace('-', '')}"

    provider = get_connection_provider()
    with provider.begin() as conn:
        _ensure_approval_table(conn)
        exists = conn.execute(text("SELECT id FROM consolidation_groups WHERE id=:gid LIMIT 1"), {"gid": group_id}).fetchone()
        if not exists:
            raise ConsolidationFinalCheckApprovalError("consolidation_group_not_found")

        merge_row = conn.execute(
            text(
                """
                SELECT id, batch_id, status
                FROM consolidation_adjustments
                WHERE group_id=:group_id
                  AND period=:period
                  AND rule_code='MERGE_JOURNAL_POST_BALANCE'
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"group_id": group_id, "period": period},
        ).fetchone()
        if not merge_row:
            raise ConsolidationFinalCheckApprovalError("merge_journal_not_found")

        report_rows = conn.execute(
            text(
                """
                SELECT report_code, status
                FROM consolidation_report_snapshots
                WHERE group_id=:group_id
                  AND period=:period
                """
            ),
            {"group_id": group_id, "period": period},
        ).fetchall()
        available_reports = {str(r.report_code or "") for r in report_rows}
        missing_reports = sorted(required_reports - available_reports)
        if missing_reports:
            raise ConsolidationFinalCheckApprovalError(f"missing_reports:{','.join(missing_reports)}")

        delta = _fetch_balance_sheet_delta(conn, group_id, period)
        check_passed = delta == 0
        check_note = "final_check_passed" if check_passed else f"balance_sheet_delta={str(delta)}"
        approval_status = "approved" if (check_passed and auto_approve) else ("submitted" if check_passed else "rejected")
        check_result = "passed" if check_passed else "failed"
        check_payload = {
            "group_id": group_id,
            "period": period,
            "merge_batch_id": str(merge_row.batch_id or ""),
            "merge_status": str(merge_row.status or ""),
            "missing_reports": missing_reports,
            "balance_sheet_delta": float(delta),
            "auto_approve": auto_approve,
        }

        existing_flow = conn.execute(
            text(
                """
                SELECT id
                FROM consolidation_approval_flows
                WHERE group_id=:group_id AND period=:period
                LIMIT 1
                """
            ),
            {"group_id": group_id, "period": period},
        ).fetchone()
        if existing_flow:
            conn.execute(
                text(
                    """
                    UPDATE consolidation_approval_flows
                    SET batch_id=:batch_id,
                        check_result=:check_result,
                        approval_status=:approval_status,
                        approver_id=:approver_id,
                        operator_id=:operator_id,
                        check_note=:check_note,
                        check_payload_json=:check_payload_json,
                        approved_at=CASE WHEN :approval_status='approved' THEN NOW() ELSE NULL END,
                        updated_at=NOW()
                    WHERE id=:id
                    """
                ),
                {
                    "id": int(existing_flow.id),
                    "batch_id": batch_id,
                    "check_result": check_result,
                    "approval_status": approval_status,
                    "approver_id": approver_id,
                    "operator_id": operator,
                    "check_note": check_note,
                    "check_payload_json": json.dumps(check_payload, ensure_ascii=False),
                },
            )
            flow_id = int(existing_flow.id)
        else:
            result = conn.execute(
                text(
                    """
                    INSERT INTO consolidation_approval_flows (
                        group_id, period, batch_id, check_result, approval_status, approver_id, operator_id,
                        check_note, check_payload_json, approved_at
                    ) VALUES (
                        :group_id, :period, :batch_id, :check_result, :approval_status, :approver_id, :operator_id,
                        :check_note, :check_payload_json,
                        CASE WHEN :approval_status='approved' THEN NOW() ELSE NULL END
                    )
                    """
                ),
                {
                    "group_id": group_id,
                    "period": period,
                    "batch_id": batch_id,
                    "check_result": check_result,
                    "approval_status": approval_status,
                    "approver_id": approver_id,
                    "operator_id": operator,
                    "check_note": check_note,
                    "check_payload_json": json.dumps(check_payload, ensure_ascii=False),
                },
            )
            flow_id = int(result.lastrowid or 0)

        flow = conn.execute(
            text(
                """
                SELECT id, group_id, period, batch_id, check_result, approval_status,
                       approver_id, operator_id, check_note, check_payload_json, approved_at, created_at, updated_at
                FROM consolidation_approval_flows
                WHERE id=:id
                LIMIT 1
                """
            ),
            {"id": flow_id},
        ).fetchone()

    out = {
        "group_id": group_id,
        "period": period,
        "rule_code": RULE_CODE,
        "final_check_passed": check_passed,
        "balance_sheet_delta": float(delta),
        "missing_reports": missing_reports,
        "approval_flow": {
            "id": int(flow.id or 0),
            "batch_id": str(flow.batch_id or ""),
            "check_result": str(flow.check_result or ""),
            "approval_status": str(flow.approval_status or ""),
            "approver_id": int(flow.approver_id or 0) if flow.approver_id is not None else None,
            "operator_id": int(flow.operator_id or 0) if flow.operator_id is not None else None,
            "check_note": str(flow.check_note or ""),
            "check_payload_json": str(flow.check_payload_json or "{}"),
            "approved_at": str(flow.approved_at or ""),
            "created_at": str(flow.created_at or ""),
            "updated_at": str(flow.updated_at or ""),
        },
    }
    log_consolidation_audit(
        action="cons29_final_check_approval",
        group_id=group_id,
        status="success" if check_passed else "failed",
        code=200 if check_passed else 409,
        operator_id=operator,
        payload={
            "period": period,
            "approval_status": str(flow.approval_status or ""),
            "check_result": str(flow.check_result or ""),
            "delta": float(delta),
        },
        note=str(flow.check_note or ""),
    )
    return out
