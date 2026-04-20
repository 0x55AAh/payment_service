from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

@dataclass
class OutboxMessage:
    """
    Сущность сообщения Outbox для реализации паттерна Transactional Outbox.
    
    Используется для надежной доставки событий во внешние системы (например, RabbitMQ)
    путем их предварительного сохранения в той же транзакции базы данных, что и основные изменения.

    Attributes:
        id (UUID): Уникальный идентификатор сообщения.
        event_type (str): Тип события (например, 'payments.created').
        payload (dict[str, Any]): Данные события в формате JSON-совместимого словаря.
        processed (bool): Флаг, указывающий, было ли сообщение успешно отправлено брокеру.
        created_at (datetime): Дата и время создания сообщения (с часовым поясом).
    """
    id: UUID = field(default_factory=uuid4)
    event_type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    processed: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
