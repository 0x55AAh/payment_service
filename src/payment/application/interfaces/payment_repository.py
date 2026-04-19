from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from payment.domain.entities.outbox import OutboxMessage
from payment.domain.entities.payment import Payment
from payment.domain.value_objects.payment_enums import PaymentStatus


class IPaymentRepository(ABC):
    @abstractmethod
    async def save(self, payment: Payment, outbox_message: OutboxMessage | None = None) -> None:
        pass

    @abstractmethod
    async def get_by_id(self, payment_id: UUID | str) -> Payment | None:
        pass

    @abstractmethod
    async def get_by_idempotency_key(self, key: str) -> Payment | None:
        pass

    @abstractmethod
    async def get_unprocessed_outbox_messages(self, limit: int = 10) -> list[OutboxMessage]:
        pass

    @abstractmethod
    async def mark_outbox_as_processed(self, message_id: UUID | str) -> None:
        pass

    @abstractmethod
    async def update_payment_status(
        self, 
        payment_id: UUID | str, 
        status: PaymentStatus, 
        processed_at: datetime | None = None,
        outbox_message: OutboxMessage | None = None
    ) -> None:
        pass
