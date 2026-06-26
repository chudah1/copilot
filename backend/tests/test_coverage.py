"""Tests for the per-signal coverage diagnostics service + route."""
import uuid
from datetime import datetime, timedelta, timezone

from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis
from app.models.thesis_claim import ThesisClaim
from app.models.thesis_decomposition import ThesisDecomposition
from app.models.thesis_entity import ThesisEntity
from app.models.thesis_signal import ThesisSignal
from app.services.coverage import compute_thesis_coverage


async def _setup_thesis_with_two_signals(db, test_user):
    holding = Holding(
        user_id=test_user.id,
        ticker="AAPL",
        name="Apple",
        quantity=10,
        average_cost_basis=100,
        current_price=200,
        current_value=2000,
    )
    db.add(holding)
    await db.flush()

    thesis = Thesis(
        user_id=test_user.id,
        holding_id=holding.id,
        status="active",
        thesis_kind="company",
        why_own_it="Services flywheel.",
        confidence="medium",
        review_cadence_days=7,
        source="user",
    )
    db.add(thesis)
    await db.flush()

    decomp = ThesisDecomposition(thesis_id=thesis.id, status="confirmed", version=1)
    db.add(decomp)
    await db.flush()

    claim = ThesisClaim(
        decomposition_id=decomp.id,
        claim_text="Services revenue grows above 12% YoY",
        claim_type="growth",
        position=0,
    )
    db.add(claim)
    await db.flush()

    entity = ThesisEntity(claim_id=claim.id, entity_name="Apple Inc", entity_type="held_company")
    db.add(entity)
    await db.flush()

    revenue_signal = ThesisSignal(
        entity_id=entity.id,
        signal_type="revenue_growth",
        signal_label="AAPL Services revenue growth",
        signal_config_json={},
        active=True,
    )
    margin_signal = ThesisSignal(
        entity_id=entity.id,
        signal_type="earnings_growth",
        signal_label="AAPL Services gross margin trend",
        signal_config_json={},
        active=True,
    )
    db.add_all([revenue_signal, margin_signal])
    await db.flush()
    return thesis, holding, claim, revenue_signal, margin_signal


async def test_coverage_marks_signal_uncovered_when_no_event_touched_it(db, test_user):
    """The launch-readiness question Codex wanted instrumented: for each
    active signal, was it touched at all in the recent window? An event that
    only binds to one of two signals should leave the other as uncovered."""
    thesis, holding, _claim, rev_signal, margin_signal = await _setup_thesis_with_two_signals(db, test_user)

    event = MonitoringEvent(
        holding_id=holding.id,
        thesis_id=thesis.id,
        event_type="gemini_news",
        severity="info",
        title="Services revenue up",
        summary="Services up 16%",
        signal_id=rev_signal.id,
        raw_data={
            "evidence": {
                "matched_signal_ids": [str(rev_signal.id)],
                "matched_signal_labels": ["AAPL Services revenue growth"],
            }
        },
    )
    db.add(event)
    await db.commit()

    report = await compute_thesis_coverage(db, thesis.id)
    assert report.covered_count == 1
    assert report.uncovered_count == 1

    by_id = {s.signal_id: s for s in report.signals}
    assert by_id[rev_signal.id].covered is True
    assert by_id[rev_signal.id].matched_event_count == 1
    assert by_id[margin_signal.id].covered is False
    assert by_id[margin_signal.id].matched_event_count == 0


async def test_coverage_picks_up_secondary_multi_binding_signals(db, test_user):
    """Without multi-binding, a Gemini article that touches BOTH revenue and
    margin would count only for the primary; the rest would silently look
    uncovered. matched_signal_ids should fix this."""
    thesis, holding, _claim, rev_signal, margin_signal = await _setup_thesis_with_two_signals(db, test_user)

    event = MonitoringEvent(
        holding_id=holding.id,
        thesis_id=thesis.id,
        event_type="gemini_news",
        severity="info",
        title="Services strong on both fronts",
        summary="Revenue 16%, margin 75%",
        signal_id=rev_signal.id,
        raw_data={
            "evidence": {
                "matched_signal_ids": [str(rev_signal.id), str(margin_signal.id)],
                "matched_signal_labels": [
                    "AAPL Services revenue growth",
                    "AAPL Services gross margin trend",
                ],
            }
        },
    )
    db.add(event)
    await db.commit()

    report = await compute_thesis_coverage(db, thesis.id)
    assert report.covered_count == 2
    assert report.uncovered_count == 0


async def test_coverage_reports_max_confidence_and_strong_binding_flag(db, test_user):
    """Strong (explicit / high-cosine / high-LLM) bindings should render
    differently from weak inferred ones. Codex's rule: under 0.80 = inferred."""
    thesis, holding, _claim, rev_signal, margin_signal = await _setup_thesis_with_two_signals(db, test_user)

    strong = MonitoringEvent(
        holding_id=holding.id,
        thesis_id=thesis.id,
        event_type="gemini_news",
        severity="info",
        title="Revenue strong",
        summary="x",
        signal_id=rev_signal.id,
        raw_data={"evidence": {"matched_signal_ids": [str(rev_signal.id)]}},
    )
    weak = MonitoringEvent(
        holding_id=holding.id,
        thesis_id=thesis.id,
        event_type="gemini_news",
        severity="info",
        title="Margin maybe",
        summary="x",
        signal_id=margin_signal.id,
        raw_data={
            "evidence": {
                "matched_signal_ids": [str(margin_signal.id)],
                "match_confidence_by_signal": {str(margin_signal.id): 0.62},
            }
        },
    )
    db.add_all([strong, weak])
    await db.commit()

    report = await compute_thesis_coverage(db, thesis.id)
    by_id = {s.signal_id: s for s in report.signals}
    # Strong binding has no confidence recorded — render as strong.
    assert by_id[rev_signal.id].max_confidence is None
    assert by_id[rev_signal.id].is_strong_binding is True
    # Weak binding has the cosine score — render as inferred.
    assert by_id[margin_signal.id].max_confidence == 0.62
    assert by_id[margin_signal.id].is_strong_binding is False


async def test_coverage_excludes_events_outside_window(db, test_user):
    """The window is what makes 'thin coverage this week' meaningful. An old
    event shouldn't make a currently-unwatched signal look fresh."""
    thesis, holding, _claim, rev_signal, _margin = await _setup_thesis_with_two_signals(db, test_user)

    old = MonitoringEvent(
        holding_id=holding.id,
        thesis_id=thesis.id,
        event_type="gemini_news",
        severity="info",
        title="Old news",
        summary="x",
        signal_id=rev_signal.id,
        raw_data={"evidence": {"matched_signal_ids": [str(rev_signal.id)]}},
        created_at=datetime.now(timezone.utc) - timedelta(days=30),
    )
    db.add(old)
    await db.commit()

    report = await compute_thesis_coverage(db, thesis.id, window_days=7)
    by_id = {s.signal_id: s for s in report.signals}
    assert by_id[rev_signal.id].covered is False


async def test_coverage_handles_thesis_without_decomposition(db, test_user):
    """A thesis with no confirmed decomposition has no signals to score
    against — flag it explicitly so the UI can prompt the user to finish
    onboarding instead of showing an empty 'all signals uncovered' panel."""
    holding = Holding(
        user_id=test_user.id, ticker="MSFT", name="Microsoft",
        quantity=1, average_cost_basis=100, current_price=100, current_value=100,
    )
    db.add(holding)
    await db.flush()
    thesis = Thesis(
        user_id=test_user.id, holding_id=holding.id, status="draft",
        thesis_kind="company", why_own_it="x", confidence="medium",
        review_cadence_days=7, source="user",
    )
    db.add(thesis)
    await db.commit()

    report = await compute_thesis_coverage(db, thesis.id)
    assert report.no_decomposition is True
    assert report.signals == []


async def test_coverage_pass_builder_records_sources_and_stages(db, test_user):
    """The builder accumulates source results and stage counts during a pass
    and writes a single CoveragePass row. This is the data behind 'which
    stage failed' for Codex's diagnostic question."""
    from app.models.coverage_pass import CoveragePass
    from app.models.thesis import Thesis
    from app.services.coverage import CoveragePassBuilder

    holding = Holding(
        user_id=test_user.id, ticker="NVDA", name="NVIDIA",
        quantity=1, average_cost_basis=100, current_price=100, current_value=100,
    )
    db.add(holding)
    await db.flush()
    thesis = Thesis(
        user_id=test_user.id, holding_id=holding.id, status="active",
        thesis_kind="company", why_own_it="GPU dominance.",
        confidence="medium", review_cadence_days=7, source="user",
    )
    db.add(thesis)
    await db.flush()

    builder = CoveragePassBuilder(
        thesis_id=thesis.id,
        holding_id=holding.id,
        run_id="check_now:test-run",
        triggered_by="check_now",
    )
    builder.record_source("qualitative_market_data", candidates_returned=8)
    builder.record_source(
        "earnings_call_transcripts",
        candidates_returned=1,
        details={
            "requested_quarters": ["2026Q1"],
            "returned_quarters": ["2026Q1"],
            "available_transcripts": 1,
        },
    )
    builder.record_source("edgar_8k", candidates_returned=2)
    builder.record_source("gemini_news", candidates_returned=0, error="429 RESOURCE_EXHAUSTED")
    builder.record_stage("candidates_generated", 10)
    builder.record_stage("after_match", 10)
    builder.record_stage("after_relevance_filter", 4)
    builder.record_stage("after_classification", 4)
    builder.record_events_persisted(4)

    await builder.persist(db)
    await db.commit()

    result = await db.execute(
        CoveragePass.__table__.select().where(CoveragePass.thesis_id == thesis.id)
    )
    rows = result.all()
    assert len(rows) == 1
    row = rows[0]
    assert row.run_id == "check_now:test-run"
    assert row.triggered_by == "check_now"
    payload = row.payload
    # Sources record both success counts and failure errors.
    assert payload["sources"]["gemini_news"]["error"].startswith("429")
    assert payload["sources"]["qualitative_market_data"]["candidates_returned"] == 8
    assert payload["sources"]["earnings_call_transcripts"]["details"]["requested_quarters"] == ["2026Q1"]
    # Stages preserve order — the funnel reads top-to-bottom.
    stage_names = [row[0] for row in payload["stages"]]
    assert stage_names == [
        "candidates_generated", "after_match",
        "after_relevance_filter", "after_classification",
    ]
    assert payload["events_persisted"] == 4


async def test_coverage_passes_route_returns_recent_passes(client, auth_headers, db, test_user):
    """API surfaces the funnel data so the UI can answer 'where did our
    candidates go' on the last check-now pass."""
    from app.models.coverage_pass import CoveragePass
    from datetime import datetime, timezone

    thesis, holding, _claim, _rev, _margin = await _setup_thesis_with_two_signals(db, test_user)
    db.add(CoveragePass(
        thesis_id=thesis.id,
        holding_id=holding.id,
        run_id="check_now:1",
        triggered_by="check_now",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        payload={
            "sources": {"gemini_news": {"queried": True, "candidates_returned": 5}},
            "stages": [["candidates_generated", 10], ["after_classification", 4]],
            "events_persisted": 4,
        },
    ))
    await db.commit()

    response = await client.get(f"/api/monitoring/theses/{thesis.id}/coverage/passes", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["run_id"] == "check_now:1"
    assert body[0]["payload"]["events_persisted"] == 4


async def test_coverage_route_returns_per_signal_report(client, auth_headers, db, test_user):
    """End-to-end through the API route to make sure schema + auth checks
    line up. The UI shells out to this for the 'thin coverage' display."""
    thesis, holding, _claim, rev_signal, margin_signal = await _setup_thesis_with_two_signals(db, test_user)

    event = MonitoringEvent(
        holding_id=holding.id,
        thesis_id=thesis.id,
        event_type="gemini_news",
        severity="info",
        title="Revenue up",
        summary="x",
        signal_id=rev_signal.id,
        raw_data={"evidence": {"matched_signal_ids": [str(rev_signal.id)]}},
    )
    db.add(event)
    await db.commit()

    response = await client.get(f"/api/monitoring/theses/{thesis.id}/coverage", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["covered_count"] == 1
    assert body["uncovered_count"] == 1
    signals_by_id = {s["signal_id"]: s for s in body["signals"]}
    assert signals_by_id[str(rev_signal.id)]["covered"] is True
    assert signals_by_id[str(margin_signal.id)]["covered"] is False
