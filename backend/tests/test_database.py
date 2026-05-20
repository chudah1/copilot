from app.database import _resolve_database_url


def test_resolve_database_url_keeps_sqlite():
    url = "sqlite+aiosqlite:///./copilot_investor.db"
    assert _resolve_database_url(url) == url


def test_resolve_database_url_falls_back_for_incomplete_local_postgres():
    assert _resolve_database_url("postgresql+asyncpg://localhost:5432/copilot_investor") == "sqlite+aiosqlite:///./copilot_investor.db"


def test_resolve_database_url_keeps_configured_postgres_with_username():
    url = "postgresql+asyncpg://copilot:secret@localhost:5432/copilot_investor"
    assert _resolve_database_url(url) == url
