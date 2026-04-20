from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from payment.domain.entities.outbox import OutboxMessage
from payment.domain.entities.payment import Payment
from payment.domain.value_objects.payment_enums import PaymentStatus


class IPaymentRepository(ABC):
    """
    Интерфейс репозитория для управления платежами и сообщениями Outbox.

    Этот интерфейс определяет контракт для взаимодействия с хранилищем данных,
    обеспечивая сохранение состояния платежей и реализацию паттерна Transactional Outbox.
    Используется в слое приложения (Use Cases) для абстрагирования от конкретной реализации БД.
    """

    @abstractmethod
    async def save(self, payment: Payment, outbox_message: OutboxMessage | None = None) -> None:
        """
        Сохраняет платеж и (опционально) сообщение в Outbox в рамках одной транзакции.

        Args:
            payment: Доменная сущность платежа для сохранения.
            outbox_message: Необязательное сообщение Outbox, которое должно быть сохранено атомарно с платежом.
        """
        pass

    @abstractmethod
    async def get_by_id(self, payment_id: UUID | str) -> Payment | None:
        """
        Получает платеж по его уникальному идентификатору.

        Args:
            payment_id: UUID или строковое представление идентификатора платежа.

        Returns:
            Экземпляр Payment или None, если платеж не найден.
        """
        pass

    @abstractmethod
    async def get_by_idempotency_key(self, key: str) -> Payment | None:
        """
        Получает платеж по ключу идемпотентности.

        Args:
            key: Уникальный ключ идемпотентности, переданный клиентом.

        Returns:
            Экземпляр Payment или None, если платеж с таким ключом не существует.
        """
        pass

    @abstractmethod
    async def get_unprocessed_outbox_messages(self, limit: int = 10) -> list[OutboxMessage]:
        """
        Получает список необработанных сообщений из Outbox.
        Используется Outbox Relay для периодической отправки событий в брокер.

        Args:
            limit: Максимальное количество сообщений для получения за один раз.

        Returns:
            Список объектов OutboxMessage, ожидающих обработки.
        """
        pass

    @abstractmethod
    async def mark_outbox_as_processed(self, message_id: UUID | str) -> None:
        """
        Помечает сообщение Outbox как успешно обработанное.

        Args:
            message_id: Идентификатор обработанного сообщения.
        """
        pass

    @abstractmethod
    async def update_payment_status(
        self, 
        payment_id: UUID | str, 
        status: PaymentStatus, 
        processed_at: datetime | None = None,
        outbox_message: OutboxMessage | None = None
    ) -> None:
        """
        Обновляет статус платежа и (опционально) добавляет новое сообщение в Outbox.

        Args:
            payment_id: Идентификатор обновляемого платежа.
            status: Новый статус платежа.
            processed_at: Время обработки платежа.
            outbox_message: Необязательное сообщение Outbox (например, о завершении обработки),
                            которое должно быть сохранено атомарно с обновлением статуса.
        """
        pass
