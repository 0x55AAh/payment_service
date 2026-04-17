import pytest
from typing import Optional, List, Dict, Any
from payment.application.interfaces.payment_repository import IPaymentRepository
from payment.domain.entities.payment import Payment
from payment.domain.entities.outbox import OutboxMessage
from payment.application.use_cases.create_payment import CreatePaymentUseCase
from payment.application.use_cases.get_payment import GetPaymentUseCase
from payment.presentation.schemas.payment import PaymentCreateSchema
from payment.domain.value_objects.payment_enums import Currency, PaymentStatus


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

    async def update_payment_status(self, payment_id: str, status: Any, processed_at: Optional[Any] = None) -> None:
        if payment_id in self.payments:
            self.payments[payment_id].status = status
            if processed_at:
                self.payments[payment_id].processed_at = processed_at

@pytest.fixture
def payment_repo():
    return InMemoryPaymentRepository()

@pytest.mark.asyncio
async def test_create_payment_success(payment_repo):
    use_case = CreatePaymentUseCase(payment_repo)
    payload = PaymentCreateSchema(
        amount=100.0,
        currency=Currency.RUB,
        description="Test payment",
        webhook_url="http://example.com/webhook",
        metadata={"order_id": "123"}
    )
    idempotency_key = "unique-key-1"

    payment = await use_case.execute(payload, idempotency_key)

    assert payment.amount == 100.0
    assert payment.idempotency_key == idempotency_key
    assert payment.status == PaymentStatus.PENDING
    
    # Check if saved in repo
    saved_payment = await payment_repo.get_by_id(str(payment.id))
    assert saved_payment is not None
    assert saved_payment.id == payment.id
    
    # Check outbox message
    assert len(payment_repo.outbox) == 1
    assert payment_repo.outbox[0].event_type == "payments.new"
    assert payment_repo.outbox[0].payload["payment_id"] == str(payment.id)

@pytest.mark.asyncio
async def test_create_payment_idempotency(payment_repo):
    use_case = CreatePaymentUseCase(payment_repo)
    payload = PaymentCreateSchema(
        amount=100.0,
        currency=Currency.RUB,
        description="Test payment",
        webhook_url="http://example.com/webhook"
    )
    idempotency_key = "same-key"

    # Create first time
    payment1 = await use_case.execute(payload, idempotency_key)
    
    # Create second time with same key
    payment2 = await use_case.execute(payload, idempotency_key)

    assert payment1.id == payment2.id
    assert len(payment_repo.payments) == 1
    assert len(payment_repo.outbox) == 1


@pytest.mark.asyncio
async def test_create_payment_empty_idempotency_key(payment_repo):
    use_case = CreatePaymentUseCase(payment_repo)
    payload = PaymentCreateSchema(
        amount=200.0,
        currency=Currency.EUR,
        description="Payment without valid key",
        webhook_url="http://example.com/webhook"
    )

    # Now it should raise ValueError
    with pytest.raises(ValueError, match="Idempotency-Key is mandatory"):
        await use_case.execute(payload, "")

    with pytest.raises(ValueError, match="Idempotency-Key is mandatory"):
        await use_case.execute(payload, "   ")

@pytest.mark.asyncio
async def test_get_payment_success(payment_repo):
    # Setup: manually save a payment
    payment = Payment(
        amount=50.0,
        currency=Currency.USD,
        description="Existing payment",
        idempotency_key="key-existing",
        webhook_url="http://example.com"
    )
    await payment_repo.save(payment)
    
    use_case = GetPaymentUseCase(payment_repo)
    result = await use_case.execute(str(payment.id))
    
    assert result is not None
    assert result.id == payment.id
    assert result.amount == 50.0

@pytest.mark.asyncio
async def test_get_payment_not_found(payment_repo):
    use_case = GetPaymentUseCase(payment_repo)
    result = await use_case.execute("non-existent-id")
    
    assert result is None
