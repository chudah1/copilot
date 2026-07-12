from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models.coverage_pass import CoveragePass
from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis
from app.config import settings
from app.services.soak_monitor import (
    SoakBasketEntry,
    build_soak_report,
    load_soak_basket_config,
    render_soak_report_markdown,
)


def test_load_soak_basket_config(tmp_path):
    path = tmp_path / "basket.json"
    path.write_text(
        json.dumps(
            {
                "holdings": [
                    {"label": "ASML control", "ticker": "ASML"},
                    {
                        "holding_id": "11111111-1111-1111-1111-111111111111",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    entries = load_soak_basket_config(path)

    assert entries == [
        SoakBasketEntry(label="ASML control", ticker="ASML", holding_id=None),
        SoakBasketEntry(
            label="11111111-1111-1111-1111-111111111111",
            ticker=None,
            holding_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        ),
    ]


@pytest.mark.asyncio
async def test_build_soak_report_summarizes_latest_pass_and_events(db, test_user):
    now = datetime.now(timezone.utc)
    holding = Holding(
        user_id=test_user.id,
        ticker="ASML",
        name="ASML Holding",
        quantity=1,
        average_cost_basis=100,
        current_price=110,
        current_value=110,
    )
    db.add(holding)
    await db.flush()

    thesis = Thesis(
        user_id=test_user.id,
        holding_id=holding.id,
        status="active",
        thesis_kind="company",
        why_own_it="High-NA and EUV demand stay strong.",
        confidence="medium",
        review_cadence_days=7,
        source="user",
    )
    db.add(thesis)
    await db.flush()

    coverage = CoveragePass(
        thesis_id=thesis.id,
        holding_id=holding.id,
        run_id="monitoring_run:test",
        triggered_by="monitoring_run",
        started_at=now - timedelta(hours=2),
        finished_at=now - timedelta(hours=2) + timedelta(minutes=1),
        payload={
            "sources": {
                "gemini_news": {"queried": True, "candidates_returned": 5},
                "edgar_8k": {"queried": True, "candidates_returned": 0, "error": "timeout"},
            },
            "stages": [
                ["candidates_generated", 10],
                ["after_noise_filter", 7],
                ["after_classification", 5],
                ["after_same_event_merge", 3],
                ["events_persisted", 2],
            ],
            "events_persisted": 2,
        },
    )
    db.add(coverage)

    event_one = MonitoringEvent(
        holding_id=holding.id,
        thesis_id=thesis.id,
        event_type="gemini_news",
        severity="info",
        title="ASML stock target raised at Bernstein",
        summary="Bernstein lifted its ASML target.",
        created_at=now - timedelta(hours=1),
    )
    event_two = MonitoringEvent(
        holding_id=holding.id,
        thesis_id=thesis.id,
        event_type="price_move",
        severity="warning",
        title="ASML shares jump 4%",
        summary="A strong session followed the analyst note.",
        created_at=now - timedelta(minutes=30),
    )
    db.add_all([event_one, event_two])
    await db.commit()

    report = await build_soak_report(
        db,
        basket=[SoakBasketEntry(label="ASML soak", ticker="ASML")],
        start_at=now - timedelta(days=1),
        end_at=now + timedelta(minutes=5),
        timezone_name="Europe/London",
    )

    assert report.unresolved == []
    assert len(report.summaries) == 1
    summary = report.summaries[0]
    assert summary.label == "ASML soak"
    assert summary.latest_triggered_by == "monitoring_run"
    assert summary.latest_stage_counts["after_same_event_merge"] == 3
    assert summary.pass_count == 1
    assert summary.total_events_persisted == 2
    assert summary.total_same_event_merges == 2
    assert summary.source_error_count == 1
    assert summary.partial_failure_count == 0
    assert summary.recent_event_count == 2
    assert len(summary.recent_events) == 2

    rendered = render_soak_report_markdown(report)
    assert "Monitoring Soak Report" in rendered
    assert "ASML soak (`ASML`)" in rendered
    assert "10 -> 7 -> 5 -> 3 -> 2" in rendered


@pytest.mark.asyncio
async def test_monitoring_soak_report_endpoint_returns_report(client, db, test_user):
    now = datetime.now(timezone.utc)
    holding = Holding(
        user_id=test_user.id,
        ticker="MSFT",
        name="Microsoft",
        quantity=1,
        average_cost_basis=100,
        current_price=105,
        current_value=105,
    )
    db.add(holding)
    await db.flush()

    thesis = Thesis(
        user_id=test_user.id,
        holding_id=holding.id,
        status="active",
        thesis_kind="company",
        why_own_it="Cloud durability.",
        confidence="medium",
        review_cadence_days=7,
        source="user",
    )
    db.add(thesis)
    await db.flush()

    db.add(
        CoveragePass(
            thesis_id=thesis.id,
            holding_id=holding.id,
            run_id="check_now:test",
            triggered_by="check_now",
            started_at=now - timedelta(hours=1),
            finished_at=now - timedelta(minutes=59),
            payload={
                "sources": {"gemini_news": {"queried": True, "candidates_returned": 2}},
                "stages": [
                    ["candidates_generated", 4],
                    ["after_noise_filter", 3],
                    ["after_classification", 2],
                    ["after_same_event_merge", 1],
                    ["events_persisted", 1],
                ],
                "events_persisted": 1,
            },
        )
    )
    db.add(
        MonitoringEvent(
            holding_id=holding.id,
            thesis_id=thesis.id,
            event_type="gemini_news",
            severity="info",
            title="Microsoft cloud bookings improve",
            summary="Bookings improved on stronger enterprise demand.",
            created_at=now - timedelta(minutes=30),
        )
    )
    await db.commit()

    original_token = settings.metrics_token
    settings.metrics_token = "test-metrics-token"
    try:
        response = await client.post(
            "/api/monitoring/soak-report",
            headers={"X-Metrics-Token": "test-metrics-token"},
            json={
                "days": 3,
                "timezone_name": "Europe/London",
                "holdings": [
                    {
                        "label": "MSFT control",
                        "holding_id": str(holding.id),
                    }
                ],
            },
        )
    finally:
        settings.metrics_token = original_token

    assert response.status_code == 200
    body = response.json()
    assert body["timezone_name"] == "Europe/London"
    assert "Monitoring Soak Report" in body["markdown"]
    assert body["summaries"][0]["label"] == "MSFT control"
    assert body["summaries"][0]["latest_stage_counts"]["after_same_event_merge"] == 1
