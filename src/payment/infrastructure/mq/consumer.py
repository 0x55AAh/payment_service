import logging
from typing import Any

import httpx
from faststream import FastStream
from faststream.rabbit import RabbitQueue, RabbitExchange
from tenacity import retry, stop_after_attempt, wait_exponential

from payment.application.schemas.integration_events import PaymentCreated, PaymentProcessed
from payment.application.use_cases.process_payment import ProcessPaymentUseCase
from payment.domain.value_objects.payment_enums import PaymentStatus
from payment.infrastructure.config.settings import settings
from payment.infrastructure.database.repositories.payment_repository import SqlAlchemyPaymentRepository
from payment.infrastructure.database.session import async_session
from payment.infrastructure.mq.broker import broker

settings.setup_logging()
logger = logging.getLogger(__name__)

# Настройка DLQ
DLQ_ROUTING_KEY = "payments.new.dead"

dlq_exchange = RabbitExchange("payments.dlx")
dlq_queue = RabbitQueue("payments.dlq")

main_queue = RabbitQueue(
    "payments.new",
    arguments={
        "x-dead-letter-exchange": "payments.dlx",
        "x-dead-letter-routing-key": DLQ_ROUTING_KEY
    }
)

processed_queue = RabbitQueue(
    "payments.processed",
    arguments={
        "x-dead-letter-exchange": "payments.dlx",
        "x-dead-letter-routing-key": DLQ_ROUTING_KEY
    }
)

app = FastStream(broker)
http_client: httpx.AsyncClient | None = None

@app.after_startup
async def setup_resources() -> None:
    """Явная декларация DLX/DLQ и инициализация HTTP-клиента"""
    global http_client
    http_client = httpx.AsyncClient()
    
    await broker.declare_exchange(dlq_exchange)
    queue = await broker.declare_queue(dlq_queue)
    await queue.bind(dlq_exchange.name, routing_key=DLQ_ROUTING_KEY)
    logger.info("DLX/DLQ configuration and HTTP client initialized")

@app.after_shutdown
async def close_resources() -> None:
    """Закрытие HTTP-клиента при завершении приложения"""
    global http_client
    if http_client:
        await http_client.aclose()
        logger.info("HTTP client closed")

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=10),
    before_sleep=lambda retry_state: logger.warning(
        f"Retrying webhook send (attempt {retry_state.attempt_number})..."
    )
)
async def send_webhook(url: str, payload: dict[str, Any]) -> None:
    """
    Отправка webhook с ретраем через tenacity.

    Выполняет POST-запрос по указанному URL с JSON-телом.
    В случае сетевых ошибок или ответов с кодами 4xx/5xx выполняется
    повторная попытка (до 3 раз) с экспоненциальной задержкой.
    Использует общий долгоживущий http_client.

    Args:
        url: URL-адрес для отправки уведомления.
        payload: Данные в формате словаря, которые будут сериализованы в JSON.

    Raises:
        httpx.HTTPStatusError: Если запрос завершился с ошибкой статуса после всех попыток.
        httpx.RequestError: Если возникла сетевая ошибка при отправке запроса.
        RuntimeError: Если http_client не инициализирован.
    """
    if http_client is None:
        raise RuntimeError("HTTP client is not initialized")
        
    logger.info(f"Sending webhook to {url}...")
    response = await http_client.post(url, json=payload, timeout=5.0)
    response.raise_for_status()
    logger.info(f"Webhook sent to {url} with status {response.status_code}")

async def process_payment_data(payment_id: str) -> PaymentStatus:
    """
    Выполняет основную логику обработки платежа.

    1. Открывает асинхронную сессию БД.
    2. Инициализирует репозиторий и Use Case.
    3. Вызывает сценарий обработки (эмуляция задержки, расчет результата, обновление БД).
    4. Коммитит изменения.

    Args:
        payment_id: Уникальный идентификатор платежа.

    Returns:
        PaymentStatus: Полученный в ходе обработки статус платежа.
    """
    async with async_session() as session:
        repo = SqlAlchemyPaymentRepository(session)
        use_case = ProcessPaymentUseCase(repo)
        new_status = await use_case.execute(payment_id)
        await session.commit()
        return new_status

retry_saga_step = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=10),
    before_sleep=lambda retry_state: logger.warning(
        f"Retrying saga step {retry_state.fn.__name__} "  # type: ignore[union-attr]
        f"(attempt {retry_state.attempt_number})..."
    )
)

class PaymentSaga:
    """
    Класс, инкапсулирующий шаги саги обработки платежа.
    
    Реализует логику хореографии через обработку событий из очередей RabbitMQ.
    """

    @staticmethod
    @broker.subscriber(main_queue)
    @retry_saga_step
    async def handle_payment_created(event: PaymentCreated) -> None:
        """
        Обработчик новых платежей из очереди RabbitMQ.

        1. Вызывает вспомогательную функцию для обработки платежа (БД и бизнес-логика).
        2. Сама обработка теперь создает Outbox сообщение для вебхука.

        Args:
            event: Объект события с данными платежа.
        """
        # Выполнение бизнес-логики обработки
        await process_payment_data(str(event.payment_id))

    @staticmethod
    @broker.subscriber(processed_queue)
    @retry_saga_step
    async def handle_payment_processed(event: PaymentProcessed) -> None:
        """
        Обработчик завершенных платежей для отправки вебхуков.

        1. Извлекает URL и payload из сообщения.
        2. Отправляет webhook с результатом обработки.

        Args:
            event: Объект события с результатом обработки.
        """
        if event.webhook_url:
            await send_webhook(str(event.webhook_url), {
                "payment_id": str(event.payment_id),
                "status": event.status.value if hasattr(event.status, 'value') else event.status,
                "processed_at": event.processed_at.isoformat() if event.processed_at else None
            })

    @staticmethod
    @broker.subscriber(dlq_queue)
    @retry_saga_step
    async def handle_dead_letters(data: dict[str, Any]) -> None:
        """
        Обработчик сообщений, попавших в Dead Letter Queue (DLQ).

        Логирует факт попадания сообщения в DLQ для последующего анализа и ручного вмешательства.

        Args:
            data: Содержимое необработанного сообщения.
        """
        logger.error(f"Message moved to DLQ: {data}")
        # Здесь можно добавить логику оповещения админов или сохранения в специальную таблицу
