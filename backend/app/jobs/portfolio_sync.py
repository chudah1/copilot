import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.broker_connection import BrokerConnection
from app.models.holding import Holding
from app.services.encryption import decrypt
from app.services.trading212 import Trading212Client
from app.services.valuation import apply_broker_position

logger = logging.getLogger(__name__)


async def run_portfolio_sync():
    import time
    started = time.monotonic()
    logger.info("Starting portfolio sync job")

    async with async_session() as db:
        result = await db.execute(
            select(BrokerConnection).where(BrokerConnection.status == "active")
        )
        connections = result.scalars().all()

        for conn in connections:
            try:
                api_key = decrypt(conn.encrypted_api_key)
                client = Trading212Client(api_key=api_key)
                positions = await client.fetch_positions()

                existing = await db.execute(
                    select(Holding).where(Holding.broker_connection_id == conn.id)
                )
                existing_by_ticker = {h.ticker: h for h in existing.scalars().all()}

                now = datetime.now(timezone.utc)
                for pos in positions:
                    ticker = pos.ticker.upper()
                    holding = existing_by_ticker.get(ticker)
                    if holding is None:
                        holding = Holding(
                            user_id=conn.user_id,
                            broker_connection_id=conn.id,
                            ticker=ticker,
                            name=ticker.replace("_US_EQ", "").replace("_", " "),
                            quantity=pos.quantity,
                            average_cost_basis=pos.average_price,
                        )
                        db.add(holding)
                    # Broker prices are in the instrument's native currency; convert
                    # cost and value to GBP via the single valuation path so the
                    # 4-hourly sync can't overwrite GBP fields with raw native numbers.
                    await apply_broker_position(
                        holding,
                        quantity=pos.quantity,
                        native_price=pos.current_price,
                        native_avg_cost=pos.average_price,
                        now=now,
                    )

                conn.last_synced_at = datetime.now(timezone.utc)
                await db.commit()
                logger.info(f"Synced {len(positions)} positions for connection {conn.id}")

            except PermissionError:
                conn.status = "disconnected"
                await db.commit()
                logger.warning("Connection %s disconnected — API key revoked", conn.id)
            except Exception as e:
                conn.status = "error"
                await db.commit()
                logger.error("Sync failed for connection %s: %s", conn.id, e, exc_info=True)

    elapsed = time.monotonic() - started
    logger.info("Portfolio sync job complete — %d connections checked in %.1fs", len(connections), elapsed)
