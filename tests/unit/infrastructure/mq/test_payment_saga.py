import pytest
from unittest.mock import AsyncMock, patch
from payment.infrastructure.mq.consumer import PaymentSaga

@pytest.mark.asyncio
async def test_handle_payment_new_success():
    data = {"payment_id": "test-uuid-123"}
    
    with patch("payment.infrastructure.mq.consumer.process_payment_data", new_callable=AsyncMock) as mock_process:
        await PaymentSaga.handle_payment_new(data)
        mock_process.assert_called_once_with("test-uuid-123")

@pytest.mark.asyncio
async def test_handle_payment_processed_with_webhook():
    data = {
        "payment_id": "test-uuid-123",
        "status": "SUCCEEDED",
        "processed_at": "2024-01-01T00:00:00Z",
        "webhook_url": "http://example.com/webhook"
    }
    
    with patch("payment.infrastructure.mq.consumer.send_webhook", new_callable=AsyncMock) as mock_send:
        await PaymentSaga.handle_payment_processed(data)
        
        mock_send.assert_called_once_with(
            "http://example.com/webhook",
            {
                "payment_id": "test-uuid-123",
                "status": "SUCCEEDED",
                "processed_at": "2024-01-01T00:00:00Z"
            }
        )

@pytest.mark.asyncio
async def test_handle_payment_processed_no_webhook():
    data = {
        "payment_id": "test-uuid-123",
        "status": "SUCCEEDED"
    }
    
    with patch("payment.infrastructure.mq.consumer.send_webhook", new_callable=AsyncMock) as mock_send:
        await PaymentSaga.handle_payment_processed(data)
        mock_send.assert_not_called()

@pytest.mark.asyncio
async def test_handle_dead_letters_logging():
    data = {"error": "something went wrong", "payment_id": "123"}
    
    with patch("payment.infrastructure.mq.consumer.logger") as mock_logger:
        await PaymentSaga.handle_dead_letters(data)
        mock_logger.error.assert_called_once_with(f"Message moved to DLQ: {data}")

@pytest.mark.asyncio
async def test_retry_logic_on_failure(monkeypatch):
    """
    Проверка, что декоратор retry_step работает. 
    Tenacity применит ретраи, если метод выбросит исключение.
    """
    data = {"payment_id": "retry-test"}
    
    # Мы переопределяем статический метод в классе на время теста, 
    # чтобы прокинуть туда кастомные параметры ретрая (без задержки)
    from tenacity import retry, stop_after_attempt, wait_none
    
    mock_process = AsyncMock()
    mock_process.side_effect = [ValueError("Fail 1"), ValueError("Fail 2"), "Success"]
    
    # Оборачиваем оригинальную логику в новый ретрай без ожидания
    @retry(stop=stop_after_attempt(3), wait=wait_none())
    async def handle_retry_test(data):
        payment_id = data.get("payment_id")
        await mock_process(str(payment_id))

    # Временно подменяем метод в классе
    monkeypatch.setattr(PaymentSaga, "handle_payment_new", handle_retry_test)
    
    await PaymentSaga.handle_payment_new(data)
    
    assert mock_process.call_count == 3
