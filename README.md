# Payment Processing Service

Асинхронный микросервис для процессинга платежей на базе FastAPI, SQLAlchemy и RabbitMQ.

## Технологии

- **Framework:** FastAPI + Pydantic v2
- **Database:** PostgreSQL + SQLAlchemy 2.0 (Async)
- **Migrations:** Alembic
- **Broker:** RabbitMQ (FastStream)
- **Containerization:** Docker + Docker Compose
- **Testing:** Pytest

## Архитектура

Проект построен по принципам **Domain-Driven Design (DDD)**:
- `src/domain`: Ядро бизнес-логики (Entities, Value Objects).
- `src/application`: Сценарии использования (Use Cases) и интерфейсы.
- `src/infrastructure`: Реализация репозиториев, работа с БД, очереди и конфигурация.
- `src/presentation`: API эндпоинты (v1) и схемы Pydantic.

## Запуск проекта

### 1. Подготовка окружения

Создайте файл `.env` в корне проекта (можно скопировать из `.env.example`, если он есть, или использовать значения по умолчанию):

```env
API_KEY=test_api_key
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=payment_service
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/payment_service
RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
```

### 2. Запуск через Docker Compose

```bash
docker compose up -d --build
```

Это поднимет:
- PostgreSQL (порт 5432)
- RabbitMQ (порт 5672, management UI на 15672)
- API (порт 8000)
- Consumer (фоновый обработчик FastStream)
- Relay (перенос сообщений из Outbox в RabbitMQ)

### 3. Применение миграций

После запуска контейнеров необходимо создать таблицы в базе данных:

```bash
docker compose exec api alembic upgrade head
```

## Масштабирование (Scaling)

Архитектура сервиса поддерживает горизонтальное масштабирование всех основных компонентов:

- **API:** Stateless-приложение, может работать за любым балансировщиком нагрузки.
- **Consumer:** Несколько экземпляров могут слушать одну очередь RabbitMQ (паттерн Competing Consumers).
- **Relay:** Поддерживает конкурентную обработку таблицы Outbox благодаря использованию `FOR UPDATE SKIP LOCKED`.

Для запуска нескольких экземпляров сервисов используйте флаг `--scale`:

```bash
# Пример: 2 инстанса API, 3 воркера (Consumer) и 2 релея (Relay)
docker compose up -d --scale api=2 --scale consumer=3 --scale relay=2
```

> **Примечание:** При масштабировании API на одной хост-машине через Docker Compose возникнет конфликт портов. В реальной среде (Kubernetes/Swarm) это решается автоматически. Для локальных тестов масштабирования API рекомендуется убрать маппинг портов или использовать внешний балансировщик.

## Тестирование

### Запуск unit и интеграционных тестов

Локально (требуется установленный `pytest` и `pytest-asyncio`):
```bash
pytest
```

Или внутри контейнера:
```bash
docker compose exec api pytest
```

## Примеры использования API

Для всех запросов требуется заголовок `X-API-Key`. Значение по умолчанию: `test_api_key`.

### 1. Создание платежа

Для создания платежа обязателен заголовок `Idempotency-Key` (UUID) для защиты от дублей.

```bash
curl -X POST http://localhost:8000/api/v1/payments \
  -H "X-API-Key: test_api_key" \
  -H "Idempotency-Key: $(uuidgen)" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 100.50,
    "currency": "RUB",
    "description": "Оплата заказа #123",
    "metadata": {"customer_id": "987"},
    "webhook_url": "https://example.com/callback"
  }'
```

### 2. Получение информации о платеже

```bash
curl -X GET http://localhost:8000/api/v1/payments/{payment_id} \
  -H "X-API-Key: test_api_key"
```

## Гарантии доставки (Outbox Pattern) и Сага (Choreography)

Сервис реализует **Transactional Outbox Pattern** в сочетании с **Choreography-based Saga** для обеспечения надежности ("at-least-once" delivery) и асинхронной обработки:

1. **Создание платежа (API):**
   - В одной транзакции создается запись `payments` и сообщение в таблице `outbox` с типом `payments.new`.
2. **Публикация события (Relay):**
   - Фоновый процесс `relay` считывает необработанные сообщения из `outbox` и публикует их в RabbitMQ (`payments.new`).
3. **Обработка платежа (Consumer step 1: `handle_payment_new`):**
   - Консьюмер получает сообщение, выполняет `ProcessPaymentUseCase` (эмуляция задержки и выбор результата).
   - В одной транзакции обновляет статус платежа и создает новое сообщение `outbox` с типом `payments.processed`.
4. **Уведомление (Consumer step 2: `handle_payment_processed`):**
   - После того как `relay` опубликует `payments.processed`, срабатывает второй шаг саги.
   - Выполняется отправка вебхука клиенту с финальным статусом платежа.

Это гарантирует, что даже в случае сбоев на любом этапе, система сможет возобновить обработку и довести платеж до финального состояния.
