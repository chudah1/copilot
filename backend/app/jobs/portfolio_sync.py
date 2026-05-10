import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.broker_connection import BrokerConnection
from app.models.holding import Holding
from app.services.encryption import decrypt
from app.services.trading212 import Trading212Client

logger = logging.getLogger(__name__)


async def run_portfolio_sync():
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

                for pos in positions:
                    if pos.ticker in existing_by_ticker:
                        holding = existing_by_ticker[pos.ticker]
                        holding.quantity = pos.quantity
                        holding.average_cost_basis = pos.average_price
                        holding.current_price = pos.current_price
                        holding.current_value = pos.quantity * pos.current_price
                        holding.last_updated_at = datetime.now(timezone.utc)
                    else:
                        db.add(Holding(
                            user_id=conn.user_id,
                            broker_connection_id=conn.id,
                            ticker=pos.ticker,
                            name=pos.ticker.replace("_US_EQ", "").replace("_", " "),
                            quantity=pos.quantity,
                            average_cost_basis=pos.average_price,
                            current_price=pos.current_price,
                            current_value=pos.quantity * pos.current_price,
                        ))

                conn.last_synced_at = datetime.now(timezone.utc)
                await db.commit()
                logger.info(f"Synced {len(positions)} positions for connection {conn.id}")

            except PermissionError:
                conn.status = "disconnected"
                await db.commit()
                logger.warning(f"Connection {conn.id} disconnected — API key revoked")
            except Exception as e:
                conn.status = "error"
                await db.commit()
                logger.error(f"Sync failed for connection {conn.id}: {e}")

    logger.info("Portfolio sync job complete")
