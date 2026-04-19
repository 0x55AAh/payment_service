import pytest

from payment.application.use_cases.get_payment import GetPaymentUseCase
from payment.domain.entities.payment import Payment
from payment.domain.value_objects.payment_enums import Currency


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
