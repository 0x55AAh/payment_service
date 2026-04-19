from decimal import Decimal

import pytest
from pydantic import ValidationError

from payment.domain.value_objects.payment_enums import Currency
from payment.presentation.schemas.payment import PaymentCreateSchema


def test_payment_create_schema_success():
    data = {
        "amount": 100.0,
        "currency": "USD",
        "description": "Valid payment",
        "webhook_url": "http://example.com/callback"
    }
    schema = PaymentCreateSchema(**data)
    assert schema.amount == Decimal("100.0")
    assert schema.currency == Currency.USD
    assert str(schema.webhook_url) == "http://example.com/callback"

def test_payment_create_schema_invalid_amount():
    data = {
        "amount": -10.0,
        "currency": "USD",
        "description": "Invalid amount",
        "webhook_url": "http://example.com/callback"
    }
    with pytest.raises(ValidationError) as exc:
        PaymentCreateSchema(**data)
    assert "Input should be greater than 0" in str(exc.value)

def test_payment_create_schema_invalid_currency():
    data = {
        "amount": 100.0,
        "currency": "INVALID",
        "description": "Invalid currency",
        "webhook_url": "http://example.com/callback"
    }
    with pytest.raises(ValidationError) as exc:
        PaymentCreateSchema(**data)
    assert "Input should be 'RUB', 'USD' or 'EUR'" in str(exc.value)

def test_payment_create_schema_invalid_url():
    data = {
        "amount": 100.0,
        "currency": "USD",
        "description": "Invalid URL",
        "webhook_url": "not-a-url"
    }
    with pytest.raises(ValidationError) as exc:
        PaymentCreateSchema(**data)
    assert "Input should be a valid URL" in str(exc.value)
