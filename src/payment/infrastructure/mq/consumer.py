import asyncio
import logging
import random
import httpx
from datetime import datetime, timezone
from tenacity import retry, stop_after_attempt, wait_exponential
from faststream import FastStream
from faststream.rabbit import RabbitQueue, RabbitExchange
from payment.infrastructure.mq.broker import broker
from payment.infrastructure.database.session import async_session
from payment.infrastructure.database.repositories.payment_repository import SqlAlchemyPaymentRepository
from payment.domain.value_objects.payment_enums import PaymentStatus
from payment.infrastructure.config.settings import settings

settings.setup_logging()
logger = logging.getLogger(__name__)

# Настройка DLQ
dlq_exchange = RabbitExchange("payments.dlx", type="direct")
dlq_queue = RabbitQueue("payments.dlq", routing_key="payments.new.dead")

main_queue = RabbitQueue(
    "payments.new",
    dead_letter_exchange="payments.dlx",
    dead_letter_routing_key="payments.new.dead"
)

app = FastStream(broker)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=10),
    before_sleep=lambda retry_state: logger.warning(
        f"Retrying webhook send (attempt {retry_state.attempt_number})..."
    )
)
async def send_webhook(url: str, payload: dict):
    """Отправка webhook с ретраем через tenacity"""
    async with httpx.AsyncClient() as client:
        logger.info(f"Sending webhook to {url}...")
        response = await client.post(url, json=payload, timeout=5.0)
        response.raise_for_status()
        logger.info(f"Webhook sent to {url} with status {response.status_code}")

@broker.subscriber(main_queue, retry=3)
async def handle_payment_new(data: dict):
    payment_id = data.get("payment_id")
    webhook_url = data.get("webhook_url")
    
    logger.info(f"Processing payment {payment_id}...")
    
    # 1. Эмуляция обработки (2-5 сек)
    delay = random.uniform(2, 5)
    await asyncio.sleep(delay)
    
    # 2. Определение результата (90% успех)
    is_success = random.random() < 0.9
    new_status = PaymentStatus.SUCCEEDED if is_success else PaymentStatus.FAILED
    
    # 3. Обновление статуса в БД
    async with async_session() as session:
        repo = SqlAlchemyPaymentRepository(session)
        await repo.update_payment_status(
            payment_id=payment_id,
            status=new_status,
            processed_at=datetime.now(timezone.utc)
        )
        await session.commit()
    
    logger.info(f"Payment {payment_id} updated to {new_status}")
    
    # 4. Отправка webhook
    if webhook_url:
        await send_webhook(webhook_url, {
            "payment_id": payment_id,
            "status": new_status.value,
            "processed_at": datetime.now(timezone.utc).isoformat()
        })

@broker.subscriber(dlq_queue)
async def handle_dead_letters(data: dict):
    logger.error(f"Message moved to DLQ: {data}")
    # Здесь можно добавить логику оповещения админов или сохранения в специальную таблицу

if __name__ == "__main__":
    # FastStream обычно запускается через CLI, но для простоты добавим возможность запуска скриптом
    asyncio.run(app.run())
