"""Regression tests for the metric_threshold event-type literal fix.

The monitoring pipeline emits event_type "metric_threshold" for a breached
metric watch hint, but `_event_title` and `determine_verdict` previously
branched on the non-existent literal "metric_threshold_breach" — so metric
breaches silently got a generic title and a severity-derived (often softer)
verdict instead of the explicit "threatens".
"""
from app.services.monitoring_pipeline import _event_title
from app.services.signal_matching import determine_verdict


def test_metric_threshold_verdict_is_threatens():
    candidate = {"event_type": "metric_threshold", "evidence": {"metric": "revenue_growth_yoy"}}
    # Even at "warning" severity, a metric breach is an explicit threat — not the
    # severity-fallback "review" it used to return.
    assert determine_verdict("warning", candidate) == "threatens"


def test_metric_threshold_event_title_names_the_metric():
    candidate = {"event_type": "metric_threshold", "evidence": {"metric": "revenue_growth_yoy"}}
    title = _event_title("NVDA", candidate, None)
    assert title == "NVDA: revenue growth yoy threshold breached"


def test_metric_threshold_title_falls_back_without_metric():
    candidate = {"event_type": "metric_threshold", "evidence": {}}
    assert _event_title("NVDA", candidate, None) == "NVDA metric alert"
