from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, ConfigDict

from payment.domain.value_objects.payment_enums import PaymentStatus, Currency


class PaymentCreateSchema(BaseModel):
    """Схема для создания нового платежа."""
    amount: Decimal = Field(..., gt=0, description="Сумма платежа (должна быть больше 0)")
    currency: Currency = Field(..., description="Валюта платежа")
    description: str = Field(..., description="Описание платежа")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Дополнительные данные")
    webhook_url: HttpUrl = Field(..., description="URL для отправки уведомлений")

class PaymentResponseSchema(BaseModel):
    """Схема краткого ответа после создания платежа."""
    payment_id: UUID = Field(alias="id", description="Уникальный идентификатор платежа")
    status: PaymentStatus = Field(..., description="Текущий статус платежа")
    created_at: datetime = Field(..., description="Дата и время создания")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )

class PaymentDetailSchema(BaseModel):
    """Схема детальной информации о платеже."""
    id: UUID = Field(..., description="Уникальный идентификатор платежа")
    amount: Decimal = Field(..., description="Сумма платежа")
    currency: Currency = Field(..., description="Валюта платежа")
    description: str = Field(..., description="Описание платежа")
    metadata: dict[str, Any] = Field(..., description="Дополнительные данные")
    status: PaymentStatus = Field(..., description="Текущий статус платежа")
    idempotency_key: str = Field(..., description="Ключ идемпотентности")
    webhook_url: str = Field(..., description="URL для отправки уведомлений")
    created_at: datetime = Field(..., description="Дата и время создания")
    processed_at: datetime | None = Field(None, description="Дата и время завершения обработки")

    model_config = ConfigDict(
        from_attributes=True
    )
