from datetime import datetime

from payment.domain.entities.payment import Payment
from payment.domain.value_objects.payment_enums import PaymentStatus, Currency


def test_payment_initial_state():
    payment = Payment(
        amount=100.0,
        currency=Currency.USD,
        description="Test payment",
        idempotency_key="key-1",
        webhook_url="http://example.com"
    )
    
    assert payment.status == PaymentStatus.PENDING
    assert payment.processed_at is None
    assert isinstance(payment.created_at, datetime)

def test_payment_mark_as_succeeded():
    payment = Payment(
        amount=100.0,
        currency=Currency.USD,
        description="Test payment",
        idempotency_key="key-1",
        webhook_url="http://example.com"
    )
    
    payment.mark_as_succeeded()
    
    assert payment.status == PaymentStatus.SUCCEEDED
    assert isinstance(payment.processed_at, datetime)

def test_payment_mark_as_failed():
    payment = Payment(
        amount=100.0,
        currency=Currency.USD,
        description="Test payment",
        idempotency_key="key-1",
        webhook_url="http://example.com"
    )
    
    payment.mark_as_failed()
    
    assert payment.status == PaymentStatus.FAILED
    assert isinstance(payment.processed_at, datetime)
