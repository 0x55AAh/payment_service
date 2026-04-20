from enum import Enum

class PaymentStatus(str, Enum):
    """Статусы жизненного цикла платежа."""
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"

class Currency(str, Enum):
    """Поддерживаемые валюты."""
    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"
