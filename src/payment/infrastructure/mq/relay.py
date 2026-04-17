import asyncio
import logging
from payment.infrastructure.database.session import async_session
from payment.infrastructure.database.repositories.payment_repository import SqlAlchemyPaymentRepository
from payment.infrastructure.mq.broker import broker
from payment.infrastructure.config.settings import settings

settings.setup_logging()
logger = logging.getLogger(__name__)

async def run_relay():
    logger.info("Starting Outbox Relay...")
    async with broker:
        while True:
            async with async_session() as session:
                repo = SqlAlchemyPaymentRepository(session)
                messages = await repo.get_unprocessed_outbox_messages(limit=10)
                
                if not messages:
                    await asyncio.sleep(5)
                    continue
                
                for msg in messages:
                    try:
                        logger.info(f"Publishing message {msg.id} to {msg.event_type}")
                        await broker.publish(
                            msg.payload,
                            queue=msg.event_type,
                        )
                        await repo.mark_outbox_as_processed(str(msg.id))
                        await session.commit()
                    except Exception as e:
                        logger.error(f"Error publishing message {msg.id}: {e}")
                        await session.rollback()
            
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(run_relay())
