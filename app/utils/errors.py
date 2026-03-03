from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4


class APIError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        details: Dict[str, Any] | None = None,
        status_code: int = 400,
    ):
        super().__init__(message)
        self.code = str(code or "bad_request")
        self.message = str(message or "bad_request")
        self.details = details or {}
        self.status_code = int(status_code or 400)


def build_api_error_response(
    *,
    code: str,
    message: str,
    details: Dict[str, Any] | None = None,
    request_id: str | None = None,
    path: str = "",
    method: str = "",
) -> Dict[str, Any]:
    req_id = str(request_id or "").strip() or str(uuid4())
    return {
        "ok": False,
        "error": {
            "code": str(code or "bad_request"),
            "message": str(message or "bad_request"),
            "details": details or {},
        },
        "audit": {
            "request_id": req_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "path": str(path or ""),
            "method": str(method or "").upper(),
        },
    }
