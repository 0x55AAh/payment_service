import asyncio
import logging
import random
from datetime import datetime, timezone
from payment.application.interfaces.payment_repository import IPaymentRepository
from payment.domain.value_objects.payment_enums import PaymentStatus
from payment.domain.entities.outbox import OutboxMessage

logger = logging.getLogger(__name__)

class ProcessPaymentUseCase:
    """
    Бизнес-логика обработки платежа.

    Эмулирует внешнюю систему обработки платежей с задержкой и случайным результатом,
    после чего обновляет статус платежа в базе данных.
    """
    def __init__(self, payment_repo: IPaymentRepository):
        self.payment_repo = payment_repo

    async def execute(self, payment_id: str) -> PaymentStatus:
        """
        Выполняет сценарий обработки платежа.

        1. Проверяет текущий статус платежа (идемпотентность).
        2. Эмулирует задержку обработки (2-5 сек).
        3. Определяет результат (успех/провал).
        4. Обновляет статус в БД.

        Args:
            payment_id: Идентификатор платежа для обработки.

        Returns:
            PaymentStatus: Новый статус платежа.
        """
        payment = await self.payment_repo.get_by_id(payment_id)
        
        # 1. Проверка текущего статуса платежа (идемпотентность)
        if payment and payment.status in [PaymentStatus.SUCCEEDED, PaymentStatus.FAILED]:
            logger.info(f"Payment {payment_id} is already in final state: {payment.status}. Skipping processing.")
            return payment.status

        logger.info(f"Processing payment {payment_id}...")
        
        # 2. Эмуляция обработки (2-5 сек)
        delay = random.uniform(2, 5)
        await asyncio.sleep(delay)
        
        # 3. Определение результата (90% успех)
        is_success = random.random() < 0.9
        new_status = PaymentStatus.SUCCEEDED if is_success else PaymentStatus.FAILED
        
        # 4. Обновление статуса в БД и подготовка Outbox сообщения
        webhook_url = payment.webhook_url if payment else None

        processed_at = datetime.now(timezone.utc)
        
        outbox_message = None
        if webhook_url:
            outbox_message = OutboxMessage(
                event_type="payments.processed",
                payload={
                    "payment_id": payment_id,
                    "status": new_status.value,
                    "processed_at": processed_at.isoformat(),
                    "webhook_url": webhook_url
                }
            )

        await self.payment_repo.update_payment_status(
            payment_id=payment_id,
            status=new_status,
            processed_at=processed_at,
            outbox_message=outbox_message
        )
        
        logger.info(f"Payment {payment_id} updated to {new_status} (outbox created: {bool(outbox_message)})")
        return new_status
