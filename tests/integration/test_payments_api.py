import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from payment.infrastructure.database.models.base import Base
from payment.infrastructure.database.session import get_db_session
from payment.main import app

# Используем SQLite в памяти для тестов
# Примечание: для полноценных интеграционных тестов лучше использовать Postgres,
# но для демонстрации и быстроты подойдет SQLite с aiosqlite.
# Однако SQLite не поддерживает некоторые типы Postgres (например, ENUM может вести себя по-другому).
# Поскольку в нашем проекте используются PostgreSQL ENUM, проверим, заработает ли это с SQLite.

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL)
TestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    import asyncio
    
    # Использование SQLite в памяти для тестов требует careful handling of UUIDs.
    # В SQLAlchemy 2.0+ для SQLite рекомендуется использовать native UUID если возможно 
    # или обрабатывать их как строки.
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def _teardown():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    loop.run_until_complete(_setup())
    yield
    loop.run_until_complete(_teardown())
    loop.close()

# Remove the old _setup_db fixture

async def override_get_db_session():
    async with TestingSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

app.dependency_overrides[get_db_session] = override_get_db_session

client = TestClient(app)

@pytest.mark.asyncio
async def test_create_payment_api_success(setup_db):
    idempotency_key = str(uuid.uuid4())
    payload = {
        "amount": 100.50,
        "currency": "RUB",
        "description": "Test payment from integration test",
        "metadata": {"user_id": "test_user"},
        "webhook_url": "https://example.com/webhook"
    }
    
    response = client.post(
        "/api/v1/payments",
        json=payload,
        headers={
            "X-API-Key": "test_api_key",
            "Idempotency-Key": idempotency_key
        }
    )
    
    assert response.status_code == 202
    data = response.json()
    assert "id" in data
    assert data["status"].upper() == "PENDING"
    
    # Проверка идемпотентности
    response_retry = client.post(
        "/api/v1/payments",
        json=payload,
        headers={
            "X-API-Key": "test_api_key",
            "Idempotency-Key": idempotency_key
        }
    )
    assert response_retry.status_code == 202
    assert response_retry.json()["id"] == data["id"]

@pytest.mark.asyncio
async def test_get_payment_api_success(setup_db):
    # Сначала создаем платеж
    idempotency_key = str(uuid.uuid4())
    payload = {
        "amount": 50.0,
        "currency": "USD",
        "description": "Get payment test",
        "webhook_url": "https://example.com/webhook"
    }
    
    create_res = client.post(
        "/api/v1/payments",
        json=payload,
        headers={
            "X-API-Key": "test_api_key",
            "Idempotency-Key": idempotency_key
        }
    )
    payment_id = create_res.json()["id"]
    
    # Теперь получаем его
    response = client.get(
        f"/api/v1/payments/{payment_id}",
        headers={"X-API-Key": "test_api_key"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == payment_id
    assert float(data["amount"]) == 50.0
    assert data["currency"].upper() == "USD"

@pytest.mark.asyncio
async def test_get_payment_not_found(setup_db):
    random_id = str(uuid.uuid4())
    response = client.get(
        f"/api/v1/payments/{random_id}",
        headers={"X-API-Key": "test_api_key"}
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Payment not found"

@pytest.mark.asyncio
async def test_create_payment_missing_idempotency_key(setup_db):
    payload = {
        "amount": 10.0,
        "currency": "EUR",
        "description": "Missing key"
    }
    response = client.post(
        "/api/v1/payments",
        json=payload,
        headers={"X-API-Key": "test_api_key"}
    )
    # FastAPI возвращает 422 для пропущенных обязательных заголовков
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_create_payment_invalid_amount(setup_db):
    idempotency_key = str(uuid.uuid4())
    payload = {
        "amount": -5.0,
        "currency": "USD",
        "description": "Negative amount",
        "webhook_url": "https://example.com/webhook"
    }
    response = client.post(
        "/api/v1/payments",
        json=payload,
        headers={
            "X-API-Key": "test_api_key",
            "Idempotency-Key": idempotency_key
        }
    )
    assert response.status_code == 422
    assert "greater than 0" in str(response.json())

@pytest.mark.asyncio
async def test_create_payment_invalid_currency(setup_db):
    idempotency_key = str(uuid.uuid4())
    payload = {
        "amount": 100.0,
        "currency": "YEN",
        "description": "Unsupported currency",
        "webhook_url": "https://example.com/webhook"
    }
    response = client.post(
        "/api/v1/payments",
        json=payload,
        headers={
            "X-API-Key": "test_api_key",
            "Idempotency-Key": idempotency_key
        }
    )
    assert response.status_code == 422
