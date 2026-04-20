import logging

from payment.application.interfaces.payment_repository import IPaymentRepository
from payment.domain.entities.outbox import OutboxMessage
from payment.domain.entities.payment import Payment
from payment.presentation.schemas.payment import PaymentCreateSchema

logger = logging.getLogger(__name__)

class CreatePaymentUseCase:
    """
    Бизнес-логика создания нового платежа.

    Выполняет проверку на идемпотентность, создает сущность платежа
    и подготавливает сообщение для Outbox.
    """
    def __init__(self, payment_repo: IPaymentRepository):
        self.payment_repo = payment_repo

    async def execute(self, payload: PaymentCreateSchema, idempotency_key: str) -> Payment:
        """
        Выполняет сценарий создания платежа.

        Args:
            payload: Данные для создания платежа (сумма, валюта и т.д.).
            idempotency_key: Уникальный ключ идемпотентности.

        Returns:
            Payment: Созданная или существующая сущность платежа.

        Raises:
            ValueError: Если ключ идемпотентности пуст.
        """
        if not idempotency_key or not idempotency_key.strip():
            logger.error("Attempt to create payment without idempotency key")
            raise ValueError("Idempotency-Key is mandatory and cannot be empty")

        # Проверка на идемпотентность
        existing_payment = await self.payment_repo.get_by_idempotency_key(idempotency_key)
        if existing_payment:
            logger.info(f"Payment already exists for idempotency_key: {idempotency_key}. Returning existing payment {existing_payment.id}")
            return existing_payment

        # Создание сущности платежа
        payment = Payment(
            amount=payload.amount,
            currency=payload.currency,
            description=payload.description,
            idempotency_key=idempotency_key,
            webhook_url=str(payload.webhook_url),
            metadata=payload.metadata
        )

        logger.info(f"Creating new payment: {payment.id} for amount {payment.amount} {payment.currency}")

        # Подготовка сообщения для Outbox (согласно техзаданию)
        # При создании платежа публикуется событие в очередь payments.new
        outbox_message = OutboxMessage(
            event_type="payments.new",
            payload={
                "payment_id": str(payment.id),
                "amount": str(payment.amount),
                "currency": payment.currency,
                "webhook_url": payment.webhook_url
            }
        )

        # Сохранение в БД (в рамках одной транзакции в репозитории)
        # Примечание: В идеале здесь должен быть Unit of Work, 
        # но для упрощения пока доверим это репозиторию или сервису.
        await self.payment_repo.save(payment, outbox_message)
        logger.info(f"Payment {payment.id} and outbox message {outbox_message.id} saved successfully")

        return payment
