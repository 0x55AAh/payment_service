from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, HttpUrl

from payment.domain.value_objects.payment_enums import PaymentStatus


class PaymentNewEvent(BaseModel):
    """Событие создания нового платежа."""
    payment_id: UUID
    webhook_url: HttpUrl | None = None


class PaymentProcessedEvent(BaseModel):
    """Событие завершения обработки платежа."""
    payment_id: UUID
    status: PaymentStatus
    processed_at: datetime
    webhook_url: HttpUrl | None = None
