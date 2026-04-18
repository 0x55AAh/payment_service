import pytest
from unittest.mock import AsyncMock, patch
from payment.infrastructure.mq.relay import OutboxRelay
from typing import Optional, List, Dict, Any
from payment.application.interfaces.payment_repository import IPaymentRepository
from payment.domain.entities.payment import Payment
from payment.domain.entities.outbox import OutboxMessage

class InMemoryPaymentRepository(IPaymentRepository):
    def __init__(self):
        self.payments: Dict[str, Payment] = {}
        self.outbox: List[OutboxMessage] = []

    async def save(self, payment: Payment, outbox_message: Optional[OutboxMessage] = None) -> None:
        self.payments[str(payment.id)] = payment
        if outbox_message:
            self.outbox.append(outbox_message)

    async def get_by_id(self, payment_id: str) -> Optional[Payment]:
        return self.payments.get(payment_id)

    async def get_by_idempotency_key(self, key: str) -> Optional[Payment]:
        for payment in self.payments.values():
            if payment.idempotency_key == key:
                return payment
        return None

    async def get_unprocessed_outbox_messages(self, limit: int = 10) -> List[OutboxMessage]:
        return [msg for msg in self.outbox if not msg.processed][:limit]

    async def mark_outbox_as_processed(self, message_id: str) -> None:
        for msg in self.outbox:
            if str(msg.id) == message_id:
                msg.processed = True
                break

    async def update_payment_status(
        self, 
        payment_id: str, 
        status: Any, 
        processed_at: Optional[Any] = None,
        outbox_message: Optional[OutboxMessage] = None
    ) -> None:
        if payment_id in self.payments:
            self.payments[payment_id].status = status
            if processed_at:
                self.payments[payment_id].processed_at = processed_at
        if outbox_message:
            self.outbox.append(outbox_message)

@pytest.fixture
def relay():
    return OutboxRelay(limit=5)

@pytest.fixture
def repo():
    return InMemoryPaymentRepository()

@pytest.mark.asyncio
async def test_fetch_messages(relay, repo):
    # Setup: add some messages to outbox
    msg1 = OutboxMessage(event_type="test.event", payload={"id": 1})
    msg2 = OutboxMessage(event_type="test.event", payload={"id": 2})
    repo.outbox.extend([msg1, msg2])
    
    messages = await relay.fetch_messages(repo)
    
    assert len(messages) == 2
    assert messages[0].id == msg1.id
    assert messages[1].id == msg2.id

@pytest.mark.asyncio
async def test_process_message_success(relay, repo):
    # Setup
    msg = OutboxMessage(event_type="test.event", payload={"data": "test"})
    repo.outbox.append(msg)
    
    with patch("payment.infrastructure.mq.relay.broker.publish", new_callable=AsyncMock) as mock_publish:
        await relay.process_message(msg, repo)
        
        # Verify broker called
        mock_publish.assert_called_once_with(msg.payload, queue=msg.event_type)
        
        # Verify marked as processed in repo
        assert repo.outbox[0].processed is True

@pytest.mark.asyncio
async def test_run_single_batch(relay, repo, monkeypatch):
    """
    Тестируем логику цикла в методе run.
    Чтобы избежать бесконечного цикла, мы заставим его выбросить исключение после первой итерации
    или просто проверим вызовы через моки.
    """
    msg = OutboxMessage(event_type="test.event", payload={"data": "test"})
    repo.outbox.append(msg)
    
    # Мокаем зависимости, чтобы run не лез в реальную БД и брокер
    mock_session = AsyncMock()
    mock_session_factory = patch("payment.infrastructure.mq.relay.async_session", return_value=mock_session)
    mock_session.__aenter__.return_value = mock_session
    
    # Мокаем SqlAlchemyPaymentRepository, чтобы использовать наш InMemoryPaymentRepository
    mock_repo_class = patch("payment.infrastructure.mq.relay.SqlAlchemyPaymentRepository", return_value=repo)
    
    # Мокаем broker context manager
    mock_broker_cm = AsyncMock()
    mock_broker = patch("payment.infrastructure.mq.relay.broker", mock_broker_cm)
    
    # Мокаем asyncio.sleep, чтобы он бросал StopIteration (или аналогичное), чтобы прервать while True
    class ExitLoop(Exception): pass
    
    async def mock_sleep(seconds):
        raise ExitLoop()
        
    monkeypatch.setattr("asyncio.sleep", mock_sleep)
    
    with mock_session_factory, mock_repo_class, mock_broker:
        with patch.object(OutboxRelay, "process_message", new_callable=AsyncMock) as mock_process:
            try:
                await relay.run()
            except ExitLoop:
                pass
            
            # Проверяем, что процесс сообщения был вызван
            mock_process.assert_called_once_with(msg, repo)
            # Проверяем, что коммит был вызван
            mock_session.commit.assert_called()

@pytest.mark.asyncio
async def test_run_rollback_on_error(relay, repo, monkeypatch):
    msg = OutboxMessage(event_type="test.event", payload={"data": "test"})
    repo.outbox.append(msg)
    
    mock_session = AsyncMock()
    mock_session_factory = patch("payment.infrastructure.mq.relay.async_session", return_value=mock_session)
    mock_session.__aenter__.return_value = mock_session
    mock_repo_class = patch("payment.infrastructure.mq.relay.SqlAlchemyPaymentRepository", return_value=repo)
    mock_broker_cm = AsyncMock()
    mock_broker = patch("payment.infrastructure.mq.relay.broker", mock_broker_cm)
    
    class ExitLoop(Exception): pass
    async def mock_sleep(seconds): raise ExitLoop()
    monkeypatch.setattr("asyncio.sleep", mock_sleep)
    
    with mock_session_factory, mock_repo_class, mock_broker:
        with patch.object(OutboxRelay, "process_message", side_effect=Exception("Publish failed")):
            try:
                await relay.run()
            except ExitLoop:
                pass
            
                # Проверяем, что был откат
                mock_session.rollback.assert_called()

@pytest.mark.asyncio
async def test_run_empty_outbox_sleeps(relay, repo, monkeypatch):
    """Проверка, что если сообщений нет, вызывается sleep(5)"""
    mock_session = AsyncMock()
    mock_session_factory = patch("payment.infrastructure.mq.relay.async_session", return_value=mock_session)
    mock_session.__aenter__.return_value = mock_session
    mock_repo_class = patch("payment.infrastructure.mq.relay.SqlAlchemyPaymentRepository", return_value=repo)
    mock_broker_cm = AsyncMock()
    mock_broker = patch("payment.infrastructure.mq.relay.broker", mock_broker_cm)
    
    sleep_calls = []
    class StopLoop(Exception): pass
    async def mock_sleep(seconds):
        sleep_calls.append(seconds)
        if seconds == 5: # Первое попадание в if not messages
             raise StopLoop()
        return

    monkeypatch.setattr("asyncio.sleep", mock_sleep)
    
    with mock_session_factory, mock_repo_class, mock_broker:
        try:
            await relay.run()
        except StopLoop:
            pass
            
    assert 5 in sleep_calls
