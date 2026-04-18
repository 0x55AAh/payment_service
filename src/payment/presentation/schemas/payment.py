from decimal import Decimal
from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID
from pydantic import BaseModel, Field, HttpUrl, ConfigDict
from payment.domain.value_objects.payment_enums import PaymentStatus, Currency

class PaymentCreateSchema(BaseModel):
    amount: Decimal = Field(..., gt=0)
    currency: Currency
    description: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    webhook_url: HttpUrl

class PaymentResponseSchema(BaseModel):
    payment_id: UUID = Field(alias="id")
    status: PaymentStatus
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )

class PaymentDetailSchema(BaseModel):
    id: UUID
    amount: Decimal
    currency: Currency
    description: str
    metadata: Dict[str, Any]
    status: PaymentStatus
    idempotency_key: str
    webhook_url: str
    created_at: datetime
    processed_at: Optional[datetime] = None

    model_config = ConfigDict(
        from_attributes=True
    )
