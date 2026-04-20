from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from payment.domain.value_objects.payment_enums import PaymentStatus, Currency


@dataclass
class Payment:
    """
    Доменная сущность Платежа.
    
    Представляет собой основной объект бизнес-логики сервиса платежей. Содержит информацию
    о сумме, валюте, текущем статусе и метаданные платежа.

    Attributes:
        amount (Decimal): Сумма платежа.
        currency (Currency): Валюта платежа (например, RUB, USD).
        description (str): Описание платежа.
        idempotency_key (str): Ключ идемпотентности для предотвращения дублирования платежей.
        webhook_url (str): URL для отправки уведомлений об изменении статуса.
        metadata (dict[str, Any]): Дополнительные данные платежа в формате словаря.
        id (UUID): Уникальный идентификатор платежа.
        status (PaymentStatus): Текущий статус платежа (PENDING, SUCCEEDED, FAILED).
        created_at (datetime): Дата и время создания (с часовым поясом).
        processed_at (datetime | None): Дата и время завершения обработки (с часовым поясом).
    """
    amount: Decimal
    currency: Currency
    description: str
    idempotency_key: str
    webhook_url: str
    metadata: dict[str, Any] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)
    status: PaymentStatus = PaymentStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: datetime | None = None

    def mark_as_succeeded(self) -> None:
        """Переводит платеж в статус SUCCEEDED и устанавливает время обработки."""
        self.status = PaymentStatus.SUCCEEDED
        self.processed_at = datetime.now(timezone.utc)

    def mark_as_failed(self) -> None:
        """Переводит платеж в статус FAILED и устанавливает время обработки."""
        self.status = PaymentStatus.FAILED
        self.processed_at = datetime.now(timezone.utc)
