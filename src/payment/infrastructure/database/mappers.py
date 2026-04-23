import uuid

from sqlalchemy import Table, Column, String, Numeric, JSON, Enum, DateTime, Boolean, MetaData
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import registry
from sqlalchemy.exc import ArgumentError

from payment.domain.entities.outbox import OutboxMessage
from payment.domain.entities.payment import Payment
from payment.domain.value_objects.payment_enums import PaymentStatus, Currency

metadata = MetaData()
mapper_registry = registry(metadata=metadata)

payment_table = Table(
    "payments",
    metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="Уникальный идентификатор платежа"),
    Column("amount", Numeric(precision=10, scale=2), nullable=False, comment="Сумма платежа"),
    Column("currency", Enum(Currency), nullable=False, comment="Валюта"),
    Column("description", String(255), nullable=False, comment="Описание"),
    Column("metadata", JSON, nullable=False, default=dict, comment="Метаданные"),
    Column("status", Enum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING, comment="Статус"),
    Column("idempotency_key", String(255), unique=True, index=True, nullable=False, comment="Ключ идемпотентности"),
    Column("webhook_url", String(255), nullable=False, comment="URL уведомлений"),
    Column("created_at", DateTime(timezone=True), index=True, nullable=False, comment="Дата создания"),
    Column("processed_at", DateTime(timezone=True), nullable=True, comment="Дата обработки"),
    comment="Таблица для хранения информации о платежах"
)

outbox_table = Table(
    "outbox",
    metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="Идентификатор сообщения"),
    Column("event_type", String(100), nullable=False, comment="Тип события"),
    Column("payload", JSON, nullable=False, comment="Данные события"),
    Column("processed", Boolean, index=True, nullable=False, default=False, comment="Флаг обработки"),
    Column("created_at", DateTime(timezone=True), index=True, nullable=False, comment="Дата создания"),
    comment="Таблица для реализации паттерна Transactional Outbox"
)

def start_mappers() -> None:
    """
    Инициализирует императивный маппинг SQLAlchemy.

    Связывает доменные сущности (Payment, OutboxMessage) с соответствующими
    таблицами базы данных (payment_table, outbox_table).
    Это позволяет использовать доменные модели напрямую при работе с ORM,
    избегая необходимости создания отдельных декларативных моделей.

    Использование try-except предотвращает повторную инициализацию мапперов
    при многократном вызове функции (например, в тестах или при перезапуске приложения).
    """
    try:
        mapper_registry.map_imperatively(Payment, payment_table)
        mapper_registry.map_imperatively(OutboxMessage, outbox_table)
    except ArgumentError:
        # Мапперы уже инициализированы
        pass
