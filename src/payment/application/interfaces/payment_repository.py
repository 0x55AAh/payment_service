from abc import ABC, abstractmethod
from typing import Optional, List, Any
from payment.domain.entities.payment import Payment
from payment.domain.entities.outbox import OutboxMessage

class IPaymentRepository(ABC):
    @abstractmethod
    async def save(self, payment: Payment, outbox_message: Optional[OutboxMessage] = None) -> None:
        pass

    @abstractmethod
    async def get_by_id(self, payment_id: str) -> Optional[Payment]:
        pass

    @abstractmethod
    async def get_by_idempotency_key(self, key: str) -> Optional[Payment]:
        pass

    @abstractmethod
    async def get_unprocessed_outbox_messages(self, limit: int = 10) -> List[OutboxMessage]:
        pass

    @abstractmethod
    async def mark_outbox_as_processed(self, message_id: str) -> None:
        pass

    @abstractmethod
    async def update_payment_status(
        self, 
        payment_id: str, 
        status: Any, 
        processed_at: Optional[Any] = None,
        outbox_message: Optional[OutboxMessage] = None
    ) -> None:
        pass
