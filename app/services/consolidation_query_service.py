from __future__ import annotations

from typing import Dict

from app.repositories.consolidation_query_repo import ConsolidationQueryRepo


class ConsolidationQueryService:
    def __init__(self, repo: ConsolidationQueryRepo | None = None):
        self.repo = repo or ConsolidationQueryRepo()

    def get_consolidated_data(self, limit: int = 20) -> Dict[str, object]:
        return self.repo.fetch_consolidated_data(limit=limit)
