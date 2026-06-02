"""The /health endpoint must surface failing background jobs so a silent failure
(which would leave the dashboard stale) is visible to monitoring."""
import pytest

from app.jobs import scheduler


@pytest.fixture(autouse=True)
def _clear_job_health():
    scheduler.JOB_HEALTH.clear()
    yield
    scheduler.JOB_HEALTH.clear()


async def test_health_ok_when_no_failures(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["failed_jobs"] == []


async def test_health_degraded_when_a_job_errored(client):
    scheduler._record_job_health("monitoring_run", "error")
    scheduler._record_job_health("portfolio_sync", "ok")

    resp = await client.get("/health")
    assert resp.status_code == 200  # always 200 so the platform doesn't restart-loop
    data = resp.json()
    assert data["status"] == "degraded"
    assert data["failed_jobs"] == ["monitoring_run"]
    # status surfaced, but no error strings leak on the public endpoint
    assert set(data["jobs"]["monitoring_run"].keys()) == {"status", "at"}


async def test_health_degraded_on_missed_job(client):
    scheduler._record_job_health("digest_builder", "missed")
    resp = await client.get("/health")
    assert resp.json()["status"] == "degraded"
    assert "digest_builder" in resp.json()["failed_jobs"]
