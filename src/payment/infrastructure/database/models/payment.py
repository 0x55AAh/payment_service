from decimal import Decimal
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Numeric, JSON, Enum as SQLEnum, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from payment.infrastructure.database.models.base import Base
from payment.domain.value_objects.payment_enums import PaymentStatus, Currency

def get_utc_now():
    return datetime.now(timezone.utc)

class PaymentModel(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    amount: Mapped[Decimal] = mapped_column(Numeric(precision=10, scale=2))
    currency: Mapped[Currency] = mapped_column(SQLEnum(Currency))
    description: Mapped[str] = mapped_column(String(255))
    metadata_json: Mapped[dict] = mapped_column(JSON, name="metadata", default=dict)
    status: Mapped[PaymentStatus] = mapped_column(SQLEnum(PaymentStatus), default=PaymentStatus.PENDING)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    webhook_url: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class OutboxModel(Base):
    __tablename__ = "outbox"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict] = mapped_column(JSON)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now)
