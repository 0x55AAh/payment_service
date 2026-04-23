from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from payment.application.interfaces.payment_repository import IPaymentRepository
from payment.domain.entities.outbox import OutboxMessage
from payment.domain.entities.payment import Payment
from payment.domain.value_objects.payment_enums import PaymentStatus


class SqlAlchemyPaymentRepository(IPaymentRepository):
    """
    Реализация репозитория платежей с использованием SQLAlchemy.
    
    Обеспечивает сохранение доменных сущностей Payment и OutboxMessage в базу данных,
    а также их получение. Благодаря использованию императивного маппинга, работает
    напрямую с доменными объектами.
    """
    def __init__(self, session: AsyncSession):
        """
        Инициализирует репозиторий сессией базы данных.

        :param session: Асинхронная сессия SQLAlchemy.
        """
        self.session = session

    async def save(self, payment: Payment, outbox_message: OutboxMessage | None = None) -> None:
        """
        Сохраняет новый платеж или обновляет существующий.
        Опционально сохраняет сообщение Outbox в рамках той же транзакции.

        :param payment: Доменная сущность платежа.
        :param outbox_message: Опциональное сообщение Outbox для паттерна Transactional Outbox.
        """
        # Мы используем merge, чтобы обработать существующие записи (идемпотентность на уровне БД)
        await self.session.merge(payment)
        
        if outbox_message:
            self.session.add(outbox_message)
            
        await self.session.flush()

    async def get_by_id(self, payment_id: UUID | str) -> Payment | None:
        """
        Получает платеж по его уникальному идентификатору.

        :param payment_id: UUID или строковое представление UUID платежа.
        :return: Сущность Payment или None, если платеж не найден.
        """
        import uuid
        if isinstance(payment_id, str):
            try:
                payment_id = uuid.UUID(payment_id)
            except ValueError:
                pass
        result = await self.session.execute(
            select(Payment).where(Payment.id == payment_id)  # type: ignore[arg-type]
        )
        return result.scalar_one_or_none()

    async def get_by_idempotency_key(self, key: str) -> Payment | None:
        """
        Получает платеж по ключу идемпотентности.

        :param key: Ключ идемпотентности запроса.
        :return: Сущность Payment или None, если платеж не найден.
        """
        result = await self.session.execute(
            select(Payment).where(Payment.idempotency_key == key)  # type: ignore[arg-type, misc]
        )
        return result.scalar_one_or_none()

    async def get_unprocessed_outbox_messages(self, limit: int = 10) -> list[OutboxMessage]:
        """
        Получает список необработанных сообщений Outbox.
        Использует блокировку SKIP LOCKED для поддержки параллельной работы нескольких Relay.

        :param limit: Максимальное количество сообщений для получения.
        :return: Список сущностей OutboxMessage.
        """
        result = await self.session.execute(
            select(OutboxMessage)
            .where(OutboxMessage.processed == False)  # type: ignore[arg-type]
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(result.scalars().all())

    async def delete_processed_outbox_messages(self, older_than: datetime) -> int:
        """
        Удаляет старые обработанные сообщения Outbox для поддержания производительности.

        :param older_than: Удалять сообщения, созданные раньше этого времени.
        :return: Количество удаленных сообщений.
        """
        result = await self.session.execute(
            delete(OutboxMessage)
            .where(OutboxMessage.processed == True)        # type: ignore[arg-type]
            .where(OutboxMessage.created_at < older_than)  # type: ignore[arg-type]
        )
        return result.rowcount  # type: ignore

    async def mark_outbox_as_processed(self, message_id: UUID | str) -> None:
        """
        Помечает сообщение Outbox как обработанное.

        :param message_id: Идентификатор сообщения.
        """
        await self.session.execute(
            update(OutboxMessage)
            .where(OutboxMessage.id == message_id)  # type: ignore[arg-type]
            .values(processed=True)
        )

    async def update_payment_status(
        self, 
        payment_id: UUID | str, 
        status: PaymentStatus, 
        processed_at: datetime | None = None,
        outbox_message: OutboxMessage | None = None
    ) -> None:
        """
        Обновляет статус платежа и время его обработки.
        Опционально сохраняет сообщение Outbox в той же транзакции.

        :param payment_id: Идентификатор платежа.
        :param status: Новый статус платежа.
        :param processed_at: Время обработки платежа.
        :param outbox_message: Опциональное сообщение Outbox.
        """
        values: dict[str, Any] = {"status": status}
        if processed_at:
            values["processed_at"] = processed_at
            
        await self.session.execute(
            update(Payment).where(Payment.id == payment_id).values(**values)  # type: ignore[arg-type]
        )

        if outbox_message:
            self.session.add(outbox_message)
            
        await self.session.flush()
