import pytest


@pytest.mark.asyncio
async def test_waitlist_reports_database_failure_instead_of_false_success(client, monkeypatch):
    from app.routes import waitlist

    class FailingSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def execute(self, _statement, _params):
            raise RuntimeError("database unavailable")

        async def commit(self):
            raise AssertionError("commit should not run after execute fails")

    monkeypatch.setattr(waitlist, "async_session", lambda: FailingSession())

    response = await client.post("/api/waitlist", json={"email": "person@example.com"})

    assert response.status_code == 503
    assert response.json()["detail"] == "Waitlist is temporarily unavailable. Please try again."
