from sqlalchemy import text
from app.db import get_engine


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
