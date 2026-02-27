import json
from typing import Dict, Optional

from sqlalchemy import text

from app.db import get_engine


def log_audit(
    module: str,
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    operator: str = "",
    role: str = "",
    detail: Optional[Dict[str, object]] = None,
):
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO audit_logs (module, action, entity_type, entity_id, operator, operator_role, detail)
                VALUES (:module, :action, :entity_type, :entity_id, :operator, :operator_role, :detail)
                """
            ),
            {
                "module": module,
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "operator": operator or "",
                "operator_role": role or "",
                "detail": json.dumps(detail or {}, ensure_ascii=False),
            },
        )
