import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from payment.infrastructure.database.models.base import Base
from payment.infrastructure.database.repositories.payment_repository import SqlAlchemyPaymentRepository
from payment.domain.entities.payment import Payment
from payment.domain.entities.outbox import OutboxMessage
from payment.domain.value_objects.payment_enums import Currency, PaymentStatus

# Используем SQLite для интеграционных тестов репозитория
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.mark.asyncio
async def test_repository_save_and_get(db_session):
    repo = SqlAlchemyPaymentRepository(db_session)
    payment = Payment(
        amount=100.0,
        currency=Currency.USD,
        description="Repo test",
        idempotency_key="repo-key-1",
        webhook_url="http://example.com"
    )
    
    await repo.save(payment)
    await db_session.commit()
    
    saved_payment = await repo.get_by_id(payment.id)
    assert saved_payment is not None
    assert saved_payment.id == payment.id
    assert saved_payment.amount == 100.0
    assert saved_payment.idempotency_key == "repo-key-1"

@pytest.mark.asyncio
async def test_repository_get_by_idempotency_key(db_session):
    repo = SqlAlchemyPaymentRepository(db_session)
    payment = Payment(
        amount=50.0,
        currency=Currency.RUB,
        description="Idempotency test",
        idempotency_key="unique-key",
        webhook_url="http://example.com"
    )
    
    await repo.save(payment)
    await db_session.commit()
    
    found = await repo.get_by_idempotency_key("unique-key")
    assert found is not None
    assert found.id == payment.id

@pytest.mark.asyncio
async def test_repository_outbox_operations(db_session):
    repo = SqlAlchemyPaymentRepository(db_session)
    msg = OutboxMessage(event_type="test.event", payload={"data": 123})
    
    # Save payment with outbox
    payment = Payment(amount=10.0, currency=Currency.EUR, description="Outbox test", idempotency_key="k1", webhook_url="http://url")
    await repo.save(payment, outbox_message=msg)
    await db_session.commit()
    
    # Fetch unprocessed
    messages = await repo.get_unprocessed_outbox_messages(limit=10)
    assert len(messages) == 1
    assert messages[0].id == msg.id
    assert messages[0].event_type == "test.event"
    
    # Mark as processed
    await repo.mark_outbox_as_processed(msg.id)
    await db_session.commit()
    
    messages_after = await repo.get_unprocessed_outbox_messages(limit=10)
    assert len(messages_after) == 0

@pytest.mark.asyncio
async def test_repository_update_status(db_session):
    repo = SqlAlchemyPaymentRepository(db_session)
    payment = Payment(amount=10.0, currency=Currency.EUR, description="Update test", idempotency_key="k2", webhook_url="http://url")
    await repo.save(payment)
    await db_session.commit()
    
    import datetime
    processed_at = datetime.datetime.now(datetime.timezone.utc)
    await repo.update_payment_status(payment.id, PaymentStatus.SUCCEEDED, processed_at=processed_at)
    await db_session.commit()
    
    updated = await repo.get_by_id(payment.id)
    assert updated.status == PaymentStatus.SUCCEEDED
    # SQLite might lose timezone info or store as string, but let's check it's present
    assert updated.processed_at is not None
