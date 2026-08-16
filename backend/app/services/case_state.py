from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.models.thesis import Thesis


@dataclass
class CaseReviewPressure:
    level: str
    days_old: int
    cadence_days: int
    watch_threshold: int
    review_threshold: int


@dataclass
class CaseQuality:
    kind: str
    rank: int
    days_old: int | None
    cadence_days: int | None
    monitorability: str | None
    ambiguity_note: str
    missing_break_condition: bool
    missing_must_remain_true: bool
    review_pressure: CaseReviewPressure | None


def age_in_days(date_value: datetime | None, *, now: datetime) -> int | None:
    if date_value is None:
        return None
    normalized = date_value if date_value.tzinfo is not None else date_value.replace(tzinfo=now.tzinfo)
    return max((now - normalized).days, 0)


def read_monitorability(thesis: Thesis | None) -> str | None:
    interpretation = thesis.interpretation or {} if thesis else {}
    value = interpretation.get("monitorability")
    return value if value in {"high", "medium", "low"} else None


def read_ambiguity_note(thesis: Thesis | None) -> str:
    interpretation = thesis.interpretation or {} if thesis else {}
    value = interpretation.get("ambiguity_note")
    return value.strip() if isinstance(value, str) else ""


def get_case_review_pressure(thesis: Thesis | None, *, now: datetime) -> CaseReviewPressure | None:
    if thesis is None:
        return None

    days_old = age_in_days(thesis.updated_at, now=now)
    if days_old is None:
        return None

    cadence_days = max(thesis.review_cadence_days or 30, 14)
    monitorability = read_monitorability(thesis)
    watch_threshold = max(cadence_days, 21)
    review_threshold = max(cadence_days * 3, 120)

    if thesis.confidence == "high":
        watch_threshold = max(watch_threshold - 7, 21)
        review_threshold = max(review_threshold - 14, 90)
    if monitorability == "low":
        watch_threshold = max(watch_threshold - 7, 14)
        review_threshold = max(review_threshold - 14, 75)

    if days_old >= review_threshold:
        return CaseReviewPressure(
            level="review",
            days_old=days_old,
            cadence_days=cadence_days,
            watch_threshold=watch_threshold,
            review_threshold=review_threshold,
        )
    if days_old >= watch_threshold:
        return CaseReviewPressure(
            level="watch",
            days_old=days_old,
            cadence_days=cadence_days,
            watch_threshold=watch_threshold,
            review_threshold=review_threshold,
        )
    return None


def classify_case_quality(thesis: Thesis | None, *, now: datetime) -> CaseQuality:
    if thesis is None or not (thesis.why_own_it or "").strip():
        return CaseQuality(
            kind="missing",
            rank=0,
            days_old=None,
            cadence_days=None,
            monitorability=None,
            ambiguity_note="",
            missing_break_condition=True,
            missing_must_remain_true=True,
            review_pressure=None,
        )

    monitorability = read_monitorability(thesis)
    ambiguity_note = read_ambiguity_note(thesis)
    cadence_days = max(thesis.review_cadence_days or 30, 14)
    days_old = age_in_days(thesis.updated_at, now=now)
    missing_break = not (thesis.what_would_change_my_mind or "").strip()
    missing_hold = not (thesis.must_remain_true or "").strip()
    review_pressure = get_case_review_pressure(thesis, now=now)

    if monitorability == "low" or ambiguity_note or (missing_break and missing_hold):
        return CaseQuality(
            kind="weak",
            rank=1,
            days_old=days_old,
            cadence_days=cadence_days,
            monitorability=monitorability,
            ambiguity_note=ambiguity_note,
            missing_break_condition=missing_break,
            missing_must_remain_true=missing_hold,
            review_pressure=review_pressure,
        )
    if review_pressure:
        return CaseQuality(
            kind="review_overdue",
            rank=2,
            days_old=days_old,
            cadence_days=cadence_days,
            monitorability=monitorability,
            ambiguity_note=ambiguity_note,
            missing_break_condition=missing_break,
            missing_must_remain_true=missing_hold,
            review_pressure=review_pressure,
        )
    if monitorability != "high" or missing_break or missing_hold:
        return CaseQuality(
            kind="workable",
            rank=3,
            days_old=days_old,
            cadence_days=cadence_days,
            monitorability=monitorability,
            ambiguity_note=ambiguity_note,
            missing_break_condition=missing_break,
            missing_must_remain_true=missing_hold,
            review_pressure=review_pressure,
        )
    return CaseQuality(
        kind="sharp",
        rank=4,
        days_old=days_old,
        cadence_days=cadence_days,
        monitorability=monitorability,
        ambiguity_note=ambiguity_note,
        missing_break_condition=missing_break,
        missing_must_remain_true=missing_hold,
        review_pressure=review_pressure,
    )
