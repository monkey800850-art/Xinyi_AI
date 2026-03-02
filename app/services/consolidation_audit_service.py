import json
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import text

from app.db_router import get_connection_provider


def log_consolidation_audit(
    action: str,
    group_id: Optional[int],
    status: str,
    code: int,
    operator_id: Optional[int] = None,
    payload: Optional[Dict[str, Any]] = None,
    note: str = "",
) -> None:
    provider = get_connection_provider()
    with provider.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO consolidation_audit_log
                    (ts, operator_id, action, group_id, payload_json, result_status, result_code, note)
                VALUES
                    (:ts, :operator_id, :action, :group_id, :payload_json, :result_status, :result_code, :note)
                """
            ),
            {
                "ts": datetime.now(),
                "operator_id": int(operator_id) if operator_id is not None else None,
                "action": str(action or "").strip(),
                "group_id": int(group_id) if group_id is not None else None,
                "payload_json": json.dumps(payload or {}, ensure_ascii=False),
                "result_status": str(status or "").strip(),
                "result_code": int(code),
                "note": str(note or "").strip(),
            },
        )
