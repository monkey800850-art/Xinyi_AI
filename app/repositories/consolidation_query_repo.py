from __future__ import annotations

from typing import Dict, List

from sqlalchemy import text

from app.db_router import get_connection_provider


class ConsolidationQueryRepo:
    def fetch_consolidated_data(self, limit: int = 20) -> Dict[str, object]:
        limit = max(1, min(int(limit or 20), 200))
        provider = get_connection_provider()
        with provider.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id, group_code, group_name
                    FROM consolidation_groups
                    ORDER BY id DESC
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            ).fetchall()

        items: List[Dict[str, object]] = [
            {"id": int(r.id), "group_code": str(r.group_code or ""), "group_name": str(r.group_name or "")}
            for r in rows
        ]
        return {"items": items, "count": len(items)}
