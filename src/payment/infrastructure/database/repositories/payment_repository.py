from typing import Optional, List, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from payment.application.interfaces.payment_repository import IPaymentRepository
from payment.domain.entities.payment import Payment
from payment.domain.entities.outbox import OutboxMessage
from payment.infrastructure.database.models.payment import PaymentModel, OutboxModel

class SqlAlchemyPaymentRepository(IPaymentRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, payment: Payment, outbox_message: Optional[OutboxMessage] = None) -> None:
        # Конвертация entity -> model
        payment_model = PaymentModel(
            id=payment.id,
            amount=payment.amount,
            currency=payment.currency,
            description=payment.description,
            metadata_json=payment.metadata,
            status=payment.status,
            idempotency_key=payment.idempotency_key,
            webhook_url=payment.webhook_url,
            created_at=payment.created_at,
            processed_at=payment.processed_at
        )
        
        # Мы используем merge, чтобы обработать существующие записи (идемпотентность на уровне БД)
        await self.session.merge(payment_model)
        
        if outbox_message:
            outbox_model = OutboxModel(
                id=outbox_message.id,
                event_type=outbox_message.event_type,
                payload=outbox_message.payload,
                processed=outbox_message.processed,
                created_at=outbox_message.created_at
            )
            self.session.add(outbox_model)
            
        await self.session.flush()

    async def get_by_id(self, payment_id: str) -> Optional[Payment]:
        import uuid
        if isinstance(payment_id, str):
            try:
                payment_id = uuid.UUID(payment_id)
            except ValueError:
                pass
        result = await self.session.execute(
            select(PaymentModel).where(PaymentModel.id == payment_id)
        )
        model = result.scalar_one_or_none()
        if model:
            return self._to_entity(model)
        return None

    async def get_by_idempotency_key(self, key: str) -> Optional[Payment]:
        result = await self.session.execute(
            select(PaymentModel).where(PaymentModel.idempotency_key == key)
        )
        model = result.scalar_one_or_none()
        if model:
            return self._to_entity(model)
        return None

    async def get_unprocessed_outbox_messages(self, limit: int = 10) -> List[OutboxMessage]:
        result = await self.session.execute(
            select(OutboxModel)
            .where(OutboxModel.processed == False)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        models = result.scalars().all()
        return [
            OutboxMessage(
                id=m.id,
                event_type=m.event_type,
                payload=m.payload,
                processed=m.processed,
                created_at=m.created_at
            ) for m in models
        ]

    async def mark_outbox_as_processed(self, message_id: str) -> None:
        await self.session.execute(
            update(OutboxModel).where(OutboxModel.id == message_id).values(processed=True)
        )

    async def update_payment_status(
        self, 
        payment_id: str, 
        status: Any, 
        processed_at: Optional[Any] = None,
        outbox_message: Optional[OutboxMessage] = None
    ) -> None:
        values = {"status": status}
        if processed_at:
            values["processed_at"] = processed_at
            
        await self.session.execute(
            update(PaymentModel).where(PaymentModel.id == payment_id).values(**values)
        )

        if outbox_message:
            outbox_model = OutboxModel(
                id=outbox_message.id,
                event_type=outbox_message.event_type,
                payload=outbox_message.payload,
                processed=outbox_message.processed,
                created_at=outbox_message.created_at
            )
            self.session.add(outbox_model)
            
        await self.session.flush()

    def _to_entity(self, model: PaymentModel) -> Payment:
        return Payment(
            id=model.id,
            amount=float(model.amount),
            currency=model.currency,
            description=model.description,
            metadata=model.metadata_json,
            status=model.status,
            idempotency_key=model.idempotency_key,
            webhook_url=model.webhook_url,
            created_at=model.created_at,
            processed_at=model.processed_at
        )
