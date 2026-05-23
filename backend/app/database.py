import uuid as _uuid
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

from sqlalchemy import String, event, types
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = logging.getLogger(__name__)


def _resolve_database_url(url: str) -> str:
    if not url.startswith("postgresql"):
        return url
    parsed = urlparse(url)
    if parsed.hostname in {"localhost", "127.0.0.1"} and not parsed.username:
        fallback_url = "sqlite+aiosqlite:///./copilot_investor.db"
        logger.warning(
            "DATABASE_URL %s is missing a username for local Postgres; falling back to %s",
            url,
            fallback_url,
        )
        return fallback_url
    return url


def _asyncpg_engine_kwargs(url: str) -> tuple[str, dict]:
    """Strip libpq-only params from URL (asyncpg doesn't accept them) and return connect_args instead."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    ssl_mode = params.pop("sslmode", [None])[0]
    params.pop("channel_binding", None)
    clean_url = urlunparse(parsed._replace(query=urlencode({k: v[0] for k, v in params.items()})))
    connect_args = {}
    if ssl_mode in ("require", "verify-ca", "verify-full"):
        connect_args["ssl"] = True
    return clean_url, connect_args


def make_async_engine(url: str):
    """Create an async engine from a database URL, handling asyncpg SSL quirks."""
    url = _resolve_database_url(url)
    if url.startswith("postgresql"):
        url, connect_args = _asyncpg_engine_kwargs(url)
        return create_async_engine(url, echo=False, connect_args=connect_args)
    # SQLite
    eng = create_async_engine(url, echo=False, connect_args={"timeout": 5})

    @event.listens_for(eng.sync_engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, _record):
        dbapi_conn.execute("PRAGMA journal_mode=WAL")
        dbapi_conn.execute("PRAGMA synchronous=NORMAL")

    return eng


def _make_engine():
    return make_async_engine(settings.database_url)


engine = _make_engine()
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class UUIDType(types.TypeDecorator):
    """Cross-database UUID type: native UUID on PostgreSQL, String on SQLite."""

    impl = types.String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import UUID
            return dialect.type_descriptor(UUID(as_uuid=True))
        return dialect.type_descriptor(types.String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, _uuid.UUID):
            return value
        return _uuid.UUID(value)


class TZDateTime(types.TypeDecorator):
    """Cross-database timezone-aware DateTime: native TIMESTAMPTZ on PostgreSQL,
    UTC-normalised naive storage on SQLite with timezone restored on load."""

    impl = types.DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session
