from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.database import make_async_engine
from app.services.soak_monitor import (
    SoakBasketEntry,
    build_soak_report,
    load_soak_basket_config,
    render_soak_report_markdown,
    soak_window_for_days,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a DB-backed monitoring soak report.")
    parser.add_argument("--config", help="Path to a soak basket JSON file.")
    parser.add_argument("--ticker", action="append", default=[], help="Ticker to include in the soak basket.")
    parser.add_argument("--holding-id", action="append", default=[], help="Holding UUID to include in the soak basket.")
    parser.add_argument("--days", type=int, default=3, help="How many trailing days to include.")
    parser.add_argument("--tz", default="Europe/London", help="Display timezone, e.g. Europe/London.")
    parser.add_argument("--output", help="Optional path to write the Markdown report.")
    return parser.parse_args()


def _basket_from_args(args: argparse.Namespace) -> list[SoakBasketEntry]:
    entries: list[SoakBasketEntry] = []
    if args.config:
        entries.extend(load_soak_basket_config(args.config))
    entries.extend(SoakBasketEntry(label=ticker.upper(), ticker=ticker.upper()) for ticker in args.ticker)
    for raw in args.holding_id:
        holding_id = uuid.UUID(raw)
        entries.append(SoakBasketEntry(label=str(holding_id), holding_id=holding_id))
    if not entries:
        raise SystemExit("Provide --config, --ticker, or --holding-id.")
    return entries


async def _run() -> int:
    args = _parse_args()
    basket = _basket_from_args(args)
    start_at, end_at = soak_window_for_days(days=args.days, timezone_name=args.tz)

    engine = make_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with session_factory() as db:
            report = await build_soak_report(
                db,
                basket=basket,
                start_at=start_at,
                end_at=end_at,
                timezone_name=args.tz,
            )
        output = render_soak_report_markdown(report)
        if args.output:
            Path(args.output).write_text(output, encoding="utf-8")
        sys.stdout.write(output)
        return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
