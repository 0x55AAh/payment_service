# Архитектурная документация: Взаимодействие сервисов

В данном документе описана архитектура взаимодействия компонентов платежного сервиса в различных режимах развертывания.

## Основные компоненты
1.  **API Service**: Принимает внешние запросы, создает записи о платежах и события в таблице Outbox в рамках одной транзакции.
2.  **Database (PostgreSQL)**: Хранит состояние платежей и очередь Outbox.
3.  **Outbox Relay**: Опрашивает таблицу Outbox и публикует сообщения в RabbitMQ.
4.  **Message Broker (RabbitMQ)**: Обеспечивает передачу сообщений между издателями и подписчиками.
5.  **Consumer (Worker)**: Обрабатывает сообщения из RabbitMQ (бизнес-логика оплаты, отправка вебхуков).

---

## 1. Схема взаимодействия (Single Instance)

При запуске в один экземпляр процесс выглядит как линейная цепочка.

```mermaid
sequenceDiagram
    participant User
    participant API
    participant DB
    participant Relay
    participant RabbitMQ
    participant Consumer
    participant Webhook

    User->>API: POST /payments (Создать платеж)
    API->>DB: INSERT Payment + INSERT Outbox (Atomic Transaction)
    DB-->>API: Success
    API-->>User: 201 Created (payment_id)

    loop Every 1 sec
        Relay->>DB: SELECT * FROM outbox WHERE processed=False
        DB-->>Relay: Message List
        Relay->>RabbitMQ: Publish(payments.processed)
        Relay->>DB: UPDATE outbox SET processed=True
    end

    RabbitMQ->>Consumer: Deliver Message
    Consumer->>Webhook: HTTP POST (Callback)
    Webhook-->>Consumer: 200 OK
```

---

## 2. Схема при масштабировании (Multiple Nodes)

При горизонтальном масштабировании (`--scale api=2 --scale relay=2 --scale consumer=3`) система обеспечивает надежность и отсутствие дублей за счет механизмов БД и брокера.

### API Nodes
- Несколько узлов API работают параллельно за Load Balancer.
- **Stateless**: Узлы не знают друг о друге, взаимодействуя только с общей БД.

### Outbox Relay (Scaling via SKIP LOCKED)
- Несколько экземпляров Relay опрашивают одну таблицу.
- **Механизм**: Используется `FOR UPDATE SKIP LOCKED`. Каждый Relay захватывает свою порцию строк, не блокируя остальных. Это исключает дублирование публикации сообщений.

### Consumers (Competing Consumers)
- Несколько воркеров подписаны на одну очередь.
- **Механизм**: RabbitMQ распределяет сообщения между свободными воркерами (Round-robin).
- **Идемпотентность**: Если один и тот же платеж по какой-то причине попал в обработку дважды, воркер проверяет статус в БД и делает Early Return.

```mermaid
graph TD
    LB[Load Balancer] --> API1[API Node 1]
    LB --> API2[API Node 2]
    
    API1 --> DB[(Shared PostgreSQL)]
    API2 --> DB
    
    DB <--> Relay1[Relay Node 1: SKIP LOCKED]
    DB <--> Relay2[Relay Node 2: SKIP LOCKED]
    
    Relay1 --> RMQ{RabbitMQ Broker}
    Relay2 --> RMQ
    
    RMQ --> C1[Consumer 1]
    RMQ --> C2[Consumer 2]
    RMQ --> C3[Consumer 3]
    
    C1 --> WH[External Webhooks]
    C2 --> WH
    C3 --> WH
```

---

## Гарантии доставки
- **At-least-once**: Благодаря Transactional Outbox, сообщение гарантированно попадет в RabbitMQ, даже если API упадет сразу после ответа пользователю.
- **Reliability**: Если Relay упадет в середине цикла, транзакция в БД не зафиксируется, и другой экземпляр Relay подхватит эти же сообщения.
- **Scalability**: Система масштабируется линейно добавлением новых узлов без изменения кода.
