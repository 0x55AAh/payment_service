from typing import Optional, List, Dict, Any

import pytest

from payment.application.interfaces.payment_repository import IPaymentRepository
from payment.domain.entities.outbox import OutboxMessage
from payment.domain.entities.payment import Payment


class InMemoryPaymentRepository(IPaymentRepository):
    def __init__(self):
        self.payments: Dict[str, Payment] = {}
        self.outbox: List[OutboxMessage] = []

    async def save(self, payment: Payment, outbox_message: Optional[OutboxMessage] = None) -> None:
        self.payments[str(payment.id)] = payment
        if outbox_message:
            self.outbox.append(outbox_message)

    async def get_by_id(self, payment_id: str) -> Optional[Payment]:
        return self.payments.get(payment_id)

    async def get_by_idempotency_key(self, key: str) -> Optional[Payment]:
        for payment in self.payments.values():
            if payment.idempotency_key == key:
                return payment
        return None

    async def get_unprocessed_outbox_messages(self, limit: int = 10) -> List[OutboxMessage]:
        return [msg for msg in self.outbox if not msg.processed][:limit]

    async def mark_outbox_as_processed(self, message_id: str) -> None:
        for msg in self.outbox:
            if str(msg.id) == message_id:
                msg.processed = True
                break

    async def update_payment_status(
        self, 
        payment_id: str, 
        status: Any, 
        processed_at: Optional[Any] = None,
        outbox_message: Optional[OutboxMessage] = None
    ) -> None:
        if payment_id in self.payments:
            self.payments[payment_id].status = status
            if processed_at:
                self.payments[payment_id].processed_at = processed_at
        if outbox_message:
            self.outbox.append(outbox_message)

@pytest.fixture
def payment_repo():
    return InMemoryPaymentRepository()
