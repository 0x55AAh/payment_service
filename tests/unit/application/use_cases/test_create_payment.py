import pytest
from payment.application.use_cases.create_payment import CreatePaymentUseCase
from payment.presentation.schemas.payment import PaymentCreateSchema
from payment.domain.value_objects.payment_enums import Currency, PaymentStatus

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
