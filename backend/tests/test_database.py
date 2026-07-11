import pytest
from sqlalchemy.exc import InterfaceError

import app.database as database
from app.database import _resolve_database_url


def test_resolve_database_url_keeps_sqlite():
    url = "sqlite+aiosqlite:///./copilot_investor.db"
    assert _resolve_database_url(url) == url


def test_resolve_database_url_falls_back_for_incomplete_local_postgres():
    assert _resolve_database_url("postgresql+asyncpg://localhost:5432/copilot_investor") == "sqlite+aiosqlite:///./copilot_investor.db"


def test_resolve_database_url_keeps_configured_postgres_with_username():
    url = "postgresql+asyncpg://copilot:secret@localhost:5432/copilot_investor"
    assert _resolve_database_url(url) == url


@pytest.mark.asyncio
async def test_get_db_suppresses_closed_connection_rollback_on_cleanup(monkeypatch):
    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            await self.close()

        async def close(self):
            raise InterfaceError(
                None,
                None,
                RuntimeError("cannot call Transaction.rollback(): the underlying connection is closed"),
            )

    monkeypatch.setattr(database, "async_session", lambda: FakeSession())

    gen = database.get_db()
    session = await gen.__anext__()
    assert session is not None
    await gen.aclose()


@pytest.mark.asyncio
async def test_get_db_still_raises_other_interface_errors(monkeypatch):
    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            await self.close()

        async def close(self):
            raise InterfaceError(
                None,
                None,
                RuntimeError("some other interface failure"),
            )

    monkeypatch.setattr(database, "async_session", lambda: FakeSession())

    gen = database.get_db()
    session = await gen.__anext__()
    assert session is not None
    with pytest.raises(InterfaceError):
        await gen.aclose()
