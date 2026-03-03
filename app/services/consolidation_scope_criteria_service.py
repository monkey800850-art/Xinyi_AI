from datetime import date
from typing import Dict

from sqlalchemy import text

from app.db_router import get_connection_provider
from app.services.consolidation_parameters_service import (
    ConsolidationParameterError,
    get_trial_balance_scope_config,
    upsert_consolidation_parameters_contract,
)


class ConsolidationScopeCriteriaError(RuntimeError):
    pass


RULE_CODE = "CONS_SCOPE_CRITERIA_CONFIG"


def _parse_positive_int(value: object, field: str) -> int:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationScopeCriteriaError(f"{field}_required")
    try:
        parsed = int(raw)
    except Exception as err:
        raise ConsolidationScopeCriteriaError(f"{field}_invalid") from err
    if parsed <= 0:
        raise ConsolidationScopeCriteriaError(f"{field}_invalid")
    return parsed


def _normalize_text(value: object, field: str, default: str, max_len: int = 64) -> str:
    txt = str(value or "").strip() or default
    if not txt:
        raise ConsolidationScopeCriteriaError(f"{field}_required")
    return txt[:max_len]


def _normalize_bool_flag(value: object) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    raw = str(value or "").strip().lower()
    return "1" if raw in {"1", "true", "yes", "y", "on"} else "0"


def _table_columns(conn, table_name: str) -> set[str]:
    rows = conn.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name=:table_name
            """
        ),
        {"table_name": table_name},
    ).fetchall()
    return {str(r[0] or "").strip().lower() for r in rows}


def _ensure_sys_rules_table(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS sys_rules (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                rule_key VARCHAR(128) NOT NULL UNIQUE,
                rule_value VARCHAR(255) NOT NULL,
                description VARCHAR(255) NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
            """
        )
    )


def _upsert_sys_rule(conn, key: str, value: str, description: str) -> None:
    existing = conn.execute(text("SELECT id FROM sys_rules WHERE rule_key=:rule_key LIMIT 1"), {"rule_key": key}).fetchone()
    if existing:
        conn.execute(
            text(
                """
                UPDATE sys_rules
                SET rule_value=:rule_value, description=:description, updated_at=NOW()
                WHERE rule_key=:rule_key
                """
            ),
            {"rule_key": key, "rule_value": value, "description": description},
        )
    else:
        conn.execute(
            text(
                """
                INSERT INTO sys_rules (rule_key, rule_value, description)
                VALUES (:rule_key, :rule_value, :description)
                """
            ),
            {"rule_key": key, "rule_value": value, "description": description},
        )


def _resolve_effective_as_of(start_period: str) -> date:
    return date.fromisoformat(f"{start_period}-01")


def configure_merger_scope_and_criteria(payload: Dict[str, object], operator_id: object = 1) -> Dict[str, object]:
    group_id = _parse_positive_int(payload.get("consolidation_group_id") or payload.get("group_id"), "consolidation_group_id")
    operator = _parse_positive_int(operator_id, "operator_id")

    start_period = _normalize_text(payload.get("start_period"), "start_period", "2025-01", max_len=7)
    note = _normalize_text(payload.get("note"), "note", "cons27", max_len=32)
    method = _normalize_text(payload.get("consolidation_method"), "consolidation_method", "full", max_len=16).lower()
    default_scope = _normalize_text(payload.get("default_scope"), "default_scope", "raw", max_len=16).lower()
    currency = _normalize_text(payload.get("currency"), "currency", "CNY", max_len=16).upper()
    fx_rate_policy = _normalize_text(payload.get("fx_rate_policy"), "fx_rate_policy", "closing_rate", max_len=32)
    accounting_policy = _normalize_text(payload.get("accounting_policy"), "accounting_policy", "group_standard", max_len=64)
    period_elimination = _normalize_bool_flag(payload.get("period_elimination"))

    upsert_payload = {
        "consolidation_group_id": group_id,
        "start_period": start_period,
        "note": note,
        "consolidation_method": method,
        "default_scope": default_scope,
        "effective_from": str(payload.get("effective_from") or f"{start_period}-01"),
        "operator_id": operator,
    }
    try:
        contract_result = upsert_consolidation_parameters_contract(upsert_payload)
    except ConsolidationParameterError as err:
        raise ConsolidationScopeCriteriaError(str(err)) from err

    provider = get_connection_provider()
    with provider.begin() as conn:
        _ensure_sys_rules_table(conn)
        cols = _table_columns(conn, "sys_rules")
        if not {"rule_key", "rule_value"}.issubset(cols):
            raise ConsolidationScopeCriteriaError("sys_rules_model_not_ready")
        group_exists = conn.execute(text("SELECT id FROM consolidation_groups WHERE id=:gid LIMIT 1"), {"gid": group_id}).fetchone()
        if not group_exists:
            raise ConsolidationScopeCriteriaError("consolidation_group_not_found")

        _upsert_sys_rule(conn, f"consolidation:currency:{group_id}", currency, "CONS-27 reporting currency")
        _upsert_sys_rule(conn, f"consolidation:fx_rate_policy:{group_id}", fx_rate_policy, "CONS-27 FX policy")
        _upsert_sys_rule(conn, f"consolidation:accounting_policy:{group_id}", accounting_policy, "CONS-27 accounting policy")
        _upsert_sys_rule(conn, f"consolidation:period_elimination:{group_id}", period_elimination, "CONS-27 period elimination switch")

        as_of = _resolve_effective_as_of(start_period)
        scope_cfg = get_trial_balance_scope_config(conn, group_id, as_of)

    return {
        "group_id": group_id,
        "rule_code": RULE_CODE,
        "scope_contract": contract_result.get("item") or {},
        "criteria": {
            "currency": currency,
            "fx_rate_policy": fx_rate_policy,
            "accounting_policy": accounting_policy,
            "period_elimination": period_elimination == "1",
        },
        "effective_scope_config": scope_cfg,
        "as_of_for_effect_check": _resolve_effective_as_of(start_period).isoformat(),
    }
