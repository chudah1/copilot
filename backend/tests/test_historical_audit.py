import pytest
from app.models.thesis import Thesis


def test_thesis_has_historical_audit_columns():
    t = Thesis.__table__
    assert "historical_audit_status" in t.c
    assert "historical_audit_results" in t.c
