import logging
import os
from contextvars import ContextVar
from dataclasses import dataclass
from threading import Lock
from typing import Optional

from sqlalchemy import create_engine, text

from app.config import build_db_url, get_db_config

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RequestRouteContext:
    tenant_id: Optional[str] = None
    book_id: Optional[int] = None


@dataclass(frozen=True)
class RouteHint:
    tenant_id: Optional[str] = None
    book_id: Optional[int] = None


@dataclass(frozen=True)
class RouteDecision:
    mode: str
    tenant_id: Optional[str]
    book_id: Optional[int]
    db_url: str
    datasource: str
    schema_name: Optional[str]


_route_ctx: ContextVar[RequestRouteContext] = ContextVar(
    "request_route_context", default=RequestRouteContext()
)


def _to_int_or_none(value) -> Optional[int]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except Exception:
        return None


def set_request_route_context(tenant_id=None, book_id=None) -> RequestRouteContext:
    tenant_text = str(tenant_id or "").strip() or None
    parsed_book_id = _to_int_or_none(book_id)
    if book_id not in (None, "") and parsed_book_id is None:
        _logger.warning("db_router_context_invalid_book_id raw=%r", book_id)
    ctx = RequestRouteContext(tenant_id=tenant_text, book_id=parsed_book_id)
    _route_ctx.set(ctx)
    return ctx


def clear_request_route_context() -> None:
    _route_ctx.set(RequestRouteContext())


def get_request_route_context() -> RequestRouteContext:
    return _route_ctx.get()


def resolve_route_hints(tenant_id=None, book_id=None) -> RouteHint:
    ctx = get_request_route_context()
    tenant_text = str(tenant_id or "").strip() or ctx.tenant_id
    parsed_book_id = _to_int_or_none(book_id)
    if parsed_book_id is None:
        parsed_book_id = ctx.book_id
    return RouteHint(tenant_id=tenant_text, book_id=parsed_book_id)


class DbRouter:
    def __init__(self):
        self._mode = os.getenv("DB_ROUTER_MODE", "single").strip().lower()
        if self._mode not in ("single", "compat"):
            self._mode = "single"
        self._miss_strategy = os.getenv("DB_ROUTER_MISS_STRATEGY", "fallback").strip().lower()
        if self._miss_strategy not in ("fallback", "strict"):
            self._miss_strategy = "fallback"
        self._meta_engine = None
        self._meta_engine_lock = Lock()

    def _default_decision(self, hint: RouteHint) -> RouteDecision:
        cfg = get_db_config()
        db_url = build_db_url(cfg)
        return RouteDecision(
            mode=self._mode,
            tenant_id=hint.tenant_id,
            book_id=hint.book_id,
            db_url=db_url,
            datasource=f"{cfg.host}:{cfg.port}/{cfg.name}",
            schema_name=cfg.name,
        )

    def _get_meta_engine(self):
        if self._meta_engine is None:
            with self._meta_engine_lock:
                if self._meta_engine is None:
                    cfg = get_db_config()
                    self._meta_engine = create_engine(build_db_url(cfg), pool_pre_ping=True)
        return self._meta_engine

    def _query_mapping(self, tenant_code: str):
        sql = text(
            """
            SELECT ds.driver, ds.host, ds.port, ds.db_name, ds.username, ds.password, ds.charset,
                   m.schema_name
            FROM tenants t
            JOIN tenant_schema_mappings m ON m.tenant_id = t.id
            JOIN data_sources ds ON ds.id = m.datasource_id
            WHERE t.tenant_code = :tenant_code
              AND t.is_enabled = 1
              AND t.status = 'active'
              AND ds.is_enabled = 1
              AND ds.status = 'active'
              AND m.is_enabled = 1
              AND m.status = 'active'
              AND (m.valid_from IS NULL OR m.valid_from <= NOW())
              AND (m.valid_to IS NULL OR m.valid_to > NOW())
            ORDER BY m.id DESC
            LIMIT 1
            """
        )
        with self._get_meta_engine().connect() as conn:
            return conn.execute(sql, {"tenant_code": tenant_code}).fetchone()

    def _build_db_url_from_mapping_row(self, row) -> str:
        from urllib.parse import quote_plus

        driver = (row.driver or "mysql+pymysql").strip()
        username = quote_plus(str(row.username or ""))
        password = quote_plus(str(row.password or ""))
        host = str(row.host or "").strip()
        port = str(row.port or "").strip()
        db_name = str(row.db_name or "").strip()
        charset = str(row.charset or "utf8mb4").strip() or "utf8mb4"
        return f"{driver}://{username}:{password}@{host}:{port}/{db_name}?charset={charset}"

    def resolve_route(self, tenant_id=None, book_id=None) -> RouteDecision:
        hint = resolve_route_hints(tenant_id=tenant_id, book_id=book_id)
        default_decision = self._default_decision(hint)
        decision = default_decision

        if self._mode == "compat" and hint.tenant_id:
            try:
                row = self._query_mapping(hint.tenant_id)
            except Exception as err:
                if self._miss_strategy == "strict":
                    raise RuntimeError("db_route_metadata_lookup_failed") from err
                _logger.warning(
                    "db_route_lookup_failed tenant_id=%s err=%s fallback=default",
                    hint.tenant_id,
                    err,
                )
            else:
                if row:
                    db_url = self._build_db_url_from_mapping_row(row)
                    decision = RouteDecision(
                        mode=self._mode,
                        tenant_id=hint.tenant_id,
                        book_id=hint.book_id,
                        db_url=db_url,
                        datasource=f"{row.host}:{row.port}/{row.db_name}",
                        schema_name=(row.schema_name or row.db_name),
                    )
                elif self._miss_strategy == "strict":
                    raise RuntimeError(f"db_route_not_found tenant_id={hint.tenant_id}")
                else:
                    _logger.warning(
                        "db_route_not_found tenant_id=%s fallback=default",
                        hint.tenant_id,
                    )

        if hint.tenant_id or hint.book_id:
            _logger.info(
                "db_route_resolved mode=%s tenant_id=%s book_id=%s datasource=%s schema=%s",
                decision.mode,
                hint.tenant_id or "",
                hint.book_id if hint.book_id is not None else "",
                decision.datasource,
                decision.schema_name or "",
            )
        return decision


class ConnectionProvider:
    def __init__(self, router: Optional[DbRouter] = None):
        self._router = router or DbRouter()
        self._engine_cache = {}
        self._lock = Lock()

    def _get_or_create_engine(self, db_url: str):
        with self._lock:
            engine = self._engine_cache.get(db_url)
            if engine is None:
                engine = create_engine(db_url, pool_pre_ping=True)
                self._engine_cache[db_url] = engine
            return engine

    def get_engine(self, tenant_id=None, book_id=None):
        decision = self._router.resolve_route(tenant_id=tenant_id, book_id=book_id)
        return self._get_or_create_engine(decision.db_url)

    def connect(self, tenant_id=None, book_id=None):
        return self.get_engine(tenant_id=tenant_id, book_id=book_id).connect()

    def begin(self, tenant_id=None, book_id=None):
        return self.get_engine(tenant_id=tenant_id, book_id=book_id).begin()


_provider: Optional[ConnectionProvider] = None
_provider_lock = Lock()


def get_connection_provider() -> ConnectionProvider:
    global _provider
    if _provider is None:
        with _provider_lock:
            if _provider is None:
                _provider = ConnectionProvider()
    return _provider
