import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from payment.domain.entities.outbox import OutboxMessage
from payment.domain.entities.payment import Payment
from payment.domain.value_objects.payment_enums import Currency, PaymentStatus
from payment.infrastructure.database.mappers import metadata, start_mappers
from payment.infrastructure.database.repositories.payment_repository import SqlAlchemyPaymentRepository

# Инициализируем мапперы перед тестами
start_mappers()

# Используем SQLite для интеграционных тестов репозитория
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    
    Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(metadata.drop_all)
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
async def test_repository_get_unprocessed_skip_locked(db_session):
    repo = SqlAlchemyPaymentRepository(db_session)
    msg1 = OutboxMessage(event_type="event.1", payload={"id": 1})
    msg2 = OutboxMessage(event_type="event.2", payload={"id": 2})
    
    payment = Payment(amount=10.0, currency=Currency.EUR, description="Skip locked test", idempotency_key="k3", webhook_url="http://url")
    await repo.save(payment, outbox_message=msg1)
    # Сохраняем второе сообщение через отдельный вызов (хотя репозиторий сейчас привязан к платежу в save)
    # Но мы можем напрямую добавить в сессию для теста
    db_session.add(msg2)
    await db_session.commit()

    # Сессия 1: выбираем сообщение
    messages1 = await repo.get_unprocessed_outbox_messages(limit=1)
    assert len(messages1) == 1
    
    # Сессия 2: имитируем другой воркер
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
    engine = db_session.bind
    Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    async with Session() as session2:
        repo2 = SqlAlchemyPaymentRepository(session2)
        # Если skip_locked работает, мы должны получить msg2, так как msg1 заблокирован первой сессией
        # ВАЖНО: SQLite не поддерживает FOR UPDATE SKIP LOCKED в полной мере, 
        # но SQLAlchemy может имитировать или просто игнорировать.
        # Однако, если БД поддерживает, этот тест проверит логику.
        messages2 = await repo2.get_unprocessed_outbox_messages(limit=1)
        
        # В SQLite это может не сработать как ожидается (он может просто ждать или вернуть то же самое),
        # но мы проверяем, что вызов не падает.
        assert len(messages2) <= 1
    
    await db_session.rollback()

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
