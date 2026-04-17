from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from uuid import UUID, uuid4
from payment.domain.value_objects.payment_enums import PaymentStatus, Currency

@dataclass
class Payment:
    amount: float
    currency: Currency
    description: str
    idempotency_key: str
    webhook_url: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)
    status: PaymentStatus = PaymentStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: Optional[datetime] = None

    def mark_as_succeeded(self):
        self.status = PaymentStatus.SUCCEEDED
        self.processed_at = datetime.now(timezone.utc)

    def mark_as_failed(self):
        self.status = PaymentStatus.FAILED
        self.processed_at = datetime.now(timezone.utc)
