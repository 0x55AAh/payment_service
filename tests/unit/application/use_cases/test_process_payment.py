import pytest
import asyncio
from payment.domain.entities.payment import Payment
from payment.application.use_cases.process_payment import ProcessPaymentUseCase
from payment.domain.value_objects.payment_enums import Currency, PaymentStatus

@pytest.mark.asyncio
async def test_process_payment_succeeded(payment_repo, monkeypatch):
    # Setup: create a payment in PENDING status
    payment = Payment(
        amount=75.0,
        currency=Currency.USD,
        description="Payment to process",
        idempotency_key="process-key-1",
        webhook_url="http://example.com/callback"
    )
    await payment_repo.save(payment)
    
    # Mock asyncio.sleep to speed up tests
    async def mock_sleep(delay):
        return
    monkeypatch.setattr("asyncio.sleep", mock_sleep)
    # Mock random.random to return < 0.9 (success)
    monkeypatch.setattr("random.random", lambda: 0.5)
    # Mock random.uniform for the delay calculation
    monkeypatch.setattr("random.uniform", lambda a, b: 3.0)
    
    use_case = ProcessPaymentUseCase(payment_repo)
    new_status = await use_case.execute(str(payment.id))
    
    assert new_status == PaymentStatus.SUCCEEDED
    
    # Check if updated in repo
    updated_payment = await payment_repo.get_by_id(str(payment.id))
    assert updated_payment.status == PaymentStatus.SUCCEEDED
    assert updated_payment.processed_at is not None

    # Check outbox message
    assert len(payment_repo.outbox) == 1
    msg = payment_repo.outbox[0]
    assert msg.event_type == "payments.processed"
    assert msg.payload["payment_id"] == str(payment.id)
    assert msg.payload["status"] == PaymentStatus.SUCCEEDED.value
    assert msg.payload["webhook_url"] == "http://example.com/callback"

@pytest.mark.asyncio
async def test_process_payment_failed(payment_repo, monkeypatch):
    # Setup: create a payment in PENDING status
    payment = Payment(
        amount=150.0,
        currency=Currency.EUR,
        description="Payment that should fail",
        idempotency_key="process-key-2",
        webhook_url="http://example.com/callback"
    )
    await payment_repo.save(payment)
    
    # Mock asyncio.sleep
    async def mock_sleep(delay):
        return
    monkeypatch.setattr("asyncio.sleep", mock_sleep)
    # Mock random.random to return >= 0.9 (failure)
    monkeypatch.setattr("random.random", lambda: 0.95)
    
    use_case = ProcessPaymentUseCase(payment_repo)
    new_status = await use_case.execute(str(payment.id))
    
    assert new_status == PaymentStatus.FAILED
    
    # Check if updated in repo
    updated_payment = await payment_repo.get_by_id(str(payment.id))
    assert updated_payment.status == PaymentStatus.FAILED
    assert updated_payment.processed_at is not None

    # Check outbox message
    assert len(payment_repo.outbox) == 1
    msg = payment_repo.outbox[0]
    assert msg.event_type == "payments.processed"
    assert msg.payload["status"] == PaymentStatus.FAILED.value
