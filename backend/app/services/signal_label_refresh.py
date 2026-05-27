"""Refresh stale signal labels for active thesis signals.

A signal is stale when:
- last_fired_at is NULL or older than STALE_UNFIRED_DAYS (hasn't been surfacing events)
- AND COALESCE(label_refreshed_at, created_at) is older than STALE_LABEL_DAYS

Stale signals get their entity_name and signal_label refreshed via a single
batched Haiku call per claim, keeping claim_text unchanged.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import async_session
from app.models.thesis_claim import ThesisClaim
from app.models.thesis_entity import ThesisEntity
from app.models.thesis_signal import ThesisSignal
from app.services.ai_utils import strip_code_fences

logger = logging.getLogger(__name__)

STALE_UNFIRED_DAYS = 90
STALE_LABEL_DAYS = 60

_REFRESH_PROMPT = """\
Refresh the monitoring signal labels for this investment claim.

Claim: {claim_text}

Signals with potentially stale vocabulary:
{signals_json}

Return a JSON array — one entry per signal_id — with updated labels:
[
  {{
    "signal_id": "<preserve exactly>",
    "entity_name": "<company or entity name, update if stale>",
    "signal_label": "<search-ready 4-8 word phrase including ticker or company name + specific metric>",
    "signal_config_json": {{}}
  }}
]

Rules:
- Preserve every signal_id exactly as given
- signal_label must name the company/ticker and the specific metric: e.g. "NVDA data center revenue growth"
- Update vocabulary to current market terminology — do not keep labels that no longer match how analysts discuss this topic
- Do not invent new signals; only refresh the ones provided
- Return only the JSON array, no prose
"""


def _normalize_dt(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _is_stale(signal: ThesisSignal, now: datetime) -> bool:
    unfired_cutoff = now - timedelta(days=STALE_UNFIRED_DAYS)
    label_cutoff = now - timedelta(days=STALE_LABEL_DAYS)
    unfired = signal.last_fired_at is None or _normalize_dt(signal.last_fired_at) < unfired_cutoff
    label_ts = signal.label_refreshed_at or signal.created_at
    label_old = _normalize_dt(label_ts) < label_cutoff
    return unfired and label_old


async def _refresh_claim(
    claim: ThesisClaim,
    stale_signals: list[ThesisSignal],
    entity_map: dict[uuid.UUID, ThesisEntity],
    now: datetime,
) -> int:
    if not stale_signals or not settings.anthropic_api_key:
        return 0
    try:
        import anthropic

        signals_input = [
            {
                "signal_id": str(s.id),
                "entity_name": (entity_map.get(s.entity_id) or ThesisEntity()).entity_name or "",
                "signal_type": s.signal_type,
                "current_label": s.signal_label or "",
            }
            for s in stale_signals
        ]
        prompt = _REFRESH_PROMPT.format(
            claim_text=claim.claim_text,
            signals_json=json.dumps(signals_input, indent=2),
        )
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            timeout=20,
        )
        updates: list[dict[str, Any]] = json.loads(
            strip_code_fences(response.content[0].text.strip())
        )
        signal_by_id = {str(s.id): s for s in stale_signals}
        count = 0
        for upd in updates:
            signal = signal_by_id.get(str(upd.get("signal_id", "")))
            if not signal:
                continue
            new_label = (upd.get("signal_label") or "").strip()
            if new_label and len(new_label) <= 255:
                signal.signal_label = new_label
            new_config = upd.get("signal_config_json")
            if isinstance(new_config, dict):
                signal.signal_config_json = new_config
            entity = entity_map.get(signal.entity_id)
            if entity:
                new_name = (upd.get("entity_name") or "").strip()
                if new_name and len(new_name) <= 255:
                    entity.entity_name = new_name
            signal.label_refreshed_at = now
            count += 1
        return count
    except Exception as exc:
        logger.warning("Signal label refresh failed for claim %s: %s", claim.id, exc)
        return 0


async def refresh_stale_signal_labels() -> None:
    now = datetime.now(timezone.utc)
    total = 0

    async with async_session() as db:
        # Load all active signals with their entity → claim chain
        result = await db.execute(
            select(ThesisSignal)
            .where(ThesisSignal.active.is_(True))
            .options(
                selectinload(ThesisSignal.entity).selectinload(ThesisEntity.claim)
            )
        )
        all_signals = list(result.scalars().all())

        stale = [s for s in all_signals if _is_stale(s, now)]
        if not stale:
            logger.info("Signal label refresh: no stale signals found")
            return

        logger.info("Signal label refresh: %d stale signals across %d entities", len(stale), len({s.entity_id for s in stale}))

        # Group stale signals by claim
        claims_map: dict[uuid.UUID, ThesisClaim] = {}
        entity_map: dict[uuid.UUID, ThesisEntity] = {}
        signals_by_claim: dict[uuid.UUID, list[ThesisSignal]] = {}

        for signal in stale:
            entity = signal.entity
            if entity is None:
                continue
            entity_map[entity.id] = entity
            claim = entity.claim
            if claim is None:
                continue
            claims_map[claim.id] = claim
            signals_by_claim.setdefault(claim.id, []).append(signal)

        for claim_id, signals in signals_by_claim.items():
            claim = claims_map[claim_id]
            refreshed = await _refresh_claim(claim, signals, entity_map, now)
            total += refreshed

        await db.commit()

    logger.info("Signal label refresh complete: %d labels updated", total)
