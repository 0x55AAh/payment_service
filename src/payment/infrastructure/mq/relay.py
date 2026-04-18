import asyncio
import logging
import signal
from typing import List
from payment.infrastructure.database.session import async_session
from payment.infrastructure.database.repositories.payment_repository import SqlAlchemyPaymentRepository
from payment.infrastructure.mq.broker import broker
from payment.infrastructure.config.settings import settings
from payment.domain.entities.outbox import OutboxMessage
from payment.application.interfaces.payment_repository import IPaymentRepository

settings.setup_logging()
logger = logging.getLogger(__name__)

class OutboxRelay:
    """
    Класс, отвечающий за перенос сообщений из таблицы Outbox в RabbitMQ.

    Реализует паттерн Transactional Outbox Relay, обеспечивая надежную
    доставку событий ("at-least-once" delivery) из базы данных в брокер сообщений.
    """
    def __init__(self, limit: int = 10):
        self.limit = limit
        self._stop_event = asyncio.Event()

    def stop(self, *args):
        """Останавливает цикл обработки."""
        logger.info("Stopping Outbox Relay...")
        self._stop_event.set()

    async def fetch_messages(self, repo: IPaymentRepository) -> List[OutboxMessage]:
        """
        Получает порцию необработанных сообщений из репозитория.

        Args:
            repo: Репозиторий для доступа к таблице Outbox.

        Returns:
            List[OutboxMessage]: Список сообщений для отправки.
        """
        return await repo.get_unprocessed_outbox_messages(limit=self.limit)

    async def process_message(self, msg: OutboxMessage, repo: IPaymentRepository):
        """
        Обрабатывает одно сообщение: публикует его в брокер и помечает как обработанное.

        Args:
            msg: Сообщение из Outbox.
            repo: Репозиторий для обновления статуса сообщения.
        """
        logger.info(f"Publishing message {msg.id} to {msg.event_type}")
        await broker.publish(msg.payload, queue=msg.event_type)
        await repo.mark_outbox_as_processed(str(msg.id))

    async def run(self):
        """
        Запускает основной цикл Relay процесса.

        1. Устанавливает обработчики сигналов для Graceful Shutdown.
        2. Устанавливает соединение с брокером.
        3. В цикле опрашивает базу данных, пока не получен сигнал остановки.
        4. Обрабатывает сообщения пачками в рамках отдельных транзакций.
        """
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self.stop)

        logger.info("Starting Outbox Relay...")
        async with broker:
            while not self._stop_event.is_set():
                async with async_session() as session:
                    repo = SqlAlchemyPaymentRepository(session)
                    messages = await self.fetch_messages(repo)
                    
                    if not messages:
                        try:
                            await asyncio.wait_for(self._stop_event.wait(), timeout=5)
                        except asyncio.TimeoutError:
                            pass
                        continue
                    
                    for msg in messages:
                        if self._stop_event.is_set():
                            break
                        try:
                            await self.process_message(msg, repo)
                            await session.commit()
                        except Exception as e:
                            logger.error(f"Error processing outbox message {msg.id}: {e}")
                            await session.rollback()
                
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=1)
                except asyncio.TimeoutError:
                    pass
        
        logger.info("Outbox Relay stopped gracefully.")

async def run_relay():
    """Точка входа для запуска Relay процесса."""
    relay = OutboxRelay()
    await relay.run()

if __name__ == "__main__":
    asyncio.run(run_relay())
