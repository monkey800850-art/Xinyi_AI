from datetime import date

from sqlalchemy import text

from app.db import get_engine
from app.db_router import get_connection_provider


class ConsolidationParameterError(Exception):
    pass


def create_consolidation_parameter(payload: dict):
    required_fields = [
        "virtual_subject_id",
        "parent_subject_type",
        "parent_subject_id",
        "child_subject_type",
        "child_subject_id",
        "ownership_ratio",
        "effective_start",
        "effective_end",
    ]

    for f in required_fields:
        if not payload.get(f):
            raise ConsolidationParameterError(f"{f}_required")

    engine = get_engine()

    with engine.begin() as conn:
        result = conn.execute(
            text("""
                INSERT INTO consolidation_parameters (
                    virtual_subject_id,
                    parent_subject_type,
                    parent_subject_id,
                    child_subject_type,
                    child_subject_id,
                    ownership_ratio,
                    control_type,
                    include_in_consolidation,
                    effective_start,
                    effective_end,
                    status,
                    operator_id
                )
                VALUES (
                    :virtual_subject_id,
                    :parent_subject_type,
                    :parent_subject_id,
                    :child_subject_type,
                    :child_subject_id,
                    :ownership_ratio,
                    :control_type,
                    :include_in_consolidation,
                    :effective_start,
                    :effective_end,
                    'active',
                    :operator_id
                )
            """),
            {
                "virtual_subject_id": payload["virtual_subject_id"],
                "parent_subject_type": payload["parent_subject_type"],
                "parent_subject_id": payload["parent_subject_id"],
                "child_subject_type": payload["child_subject_type"],
                "child_subject_id": payload["child_subject_id"],
                "ownership_ratio": payload["ownership_ratio"],
                "control_type": payload.get("control_type", "control"),
                "include_in_consolidation": payload.get("include_in_consolidation", 1),
                "effective_start": payload["effective_start"],
                "effective_end": payload["effective_end"],
                "operator_id": payload.get("operator_id", 1),
            },
        )

        new_id = result.lastrowid

    return {
        "id": new_id,
        "status": "active"
    }


def list_consolidation_parameters(params: dict):
    engine = get_engine()

    sql = """
        SELECT *
        FROM consolidation_parameters
        WHERE 1=1
    """

    bind = {}

    if params.get("virtual_subject_id"):
        sql += " AND virtual_subject_id = :virtual_subject_id"
        bind["virtual_subject_id"] = params["virtual_subject_id"]

    sql += " ORDER BY id DESC"

    with engine.connect() as conn:
        rows = conn.execute(text(sql), bind).mappings().all()

    return {
        "items": [dict(r) for r in rows]
    }


def _parse_positive_int(value: object, field: str) -> int:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationParameterError(f"{field}_required")
    try:
        parsed = int(raw)
    except Exception as err:
        raise ConsolidationParameterError(f"{field}_invalid") from err
    if parsed <= 0:
        raise ConsolidationParameterError(f"{field}_invalid")
    return parsed


def _normalize_period_policy(value: object) -> str:
    policy = str(value or "").strip().lower()
    if not policy:
        raise ConsolidationParameterError("period_policy_required")
    if policy not in {"monthly", "quarterly", "yearly"}:
        raise ConsolidationParameterError("period_policy_invalid")
    return policy


def _normalize_currency(value: object) -> str:
    currency = str(value or "").strip().upper()
    if not currency:
        raise ConsolidationParameterError("currency_required")
    if not currency.isalpha() or len(currency) > 8:
        raise ConsolidationParameterError("currency_invalid")
    return currency


def _row_to_contract_item(row) -> dict:
    return {
        "id": int(row.id),
        "group_id": int(row.virtual_subject_id),
        "period_policy": str(row.control_type or ""),
        "currency": str(row.parent_subject_type or ""),
        "note": "",
        "updated_at": str(row.updated_at or ""),
    }


def list_consolidation_parameters_contract(group_id: int, tenant_id: str | None = None) -> dict:
    provider = get_connection_provider()
    with provider.connect(tenant_id=tenant_id) as conn:
        row = conn.execute(
            text(
                """
                SELECT id, virtual_subject_id, control_type, parent_subject_type, updated_at
                FROM consolidation_parameters
                WHERE virtual_subject_id=:group_id
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"group_id": int(group_id)},
        ).fetchone()
    if not row:
        return {"items": []}
    return {"items": [_row_to_contract_item(row)]}


def upsert_consolidation_parameters_contract(payload: dict, tenant_id: str | None = None) -> dict:
    group_id = _parse_positive_int(payload.get("group_id"), "group_id")
    period_policy = _normalize_period_policy(payload.get("period_policy"))
    currency = _normalize_currency(payload.get("currency"))
    operator_raw = payload.get("operator_id")
    operator_id = int(operator_raw) if str(operator_raw or "").strip().isdigit() else 1

    today = date.today().isoformat()
    provider = get_connection_provider()
    with provider.begin(tenant_id=tenant_id) as conn:
        existing = conn.execute(
            text(
                """
                SELECT id
                FROM consolidation_parameters
                WHERE virtual_subject_id=:group_id
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"group_id": group_id},
        ).fetchone()

        if existing:
            param_id = int(existing.id)
            conn.execute(
                text(
                    """
                    UPDATE consolidation_parameters
                    SET parent_subject_type=:currency,
                        parent_subject_id=:group_id,
                        child_subject_type=:period_policy,
                        child_subject_id=:group_id,
                        control_type=:period_policy,
                        ownership_ratio=1.000000,
                        include_in_consolidation=1,
                        effective_start=:today,
                        effective_end='2099-12-31',
                        status='active',
                        operator_id=:operator_id,
                        updated_at=NOW()
                    WHERE id=:id
                    """
                ),
                {
                    "id": param_id,
                    "group_id": group_id,
                    "period_policy": period_policy,
                    "currency": currency,
                    "today": today,
                    "operator_id": operator_id,
                },
            )
        else:
            result = conn.execute(
                text(
                    """
                    INSERT INTO consolidation_parameters (
                      virtual_subject_id,
                      parent_subject_type,
                      parent_subject_id,
                      child_subject_type,
                      child_subject_id,
                      ownership_ratio,
                      control_type,
                      include_in_consolidation,
                      effective_start,
                      effective_end,
                      status,
                      operator_id
                    ) VALUES (
                      :group_id,
                      :currency,
                      :group_id,
                      :period_policy,
                      :group_id,
                      1.000000,
                      :period_policy,
                      1,
                      :today,
                      '2099-12-31',
                      'active',
                      :operator_id
                    )
                    """
                ),
                {
                    "group_id": group_id,
                    "period_policy": period_policy,
                    "currency": currency,
                    "today": today,
                    "operator_id": operator_id,
                },
            )
            param_id = int(result.lastrowid or 0)

        row = conn.execute(
            text(
                """
                SELECT id, virtual_subject_id, control_type, parent_subject_type, updated_at
                FROM consolidation_parameters
                WHERE id=:id
                LIMIT 1
                """
            ),
            {"id": param_id},
        ).fetchone()

    return {"item": _row_to_contract_item(row)}
