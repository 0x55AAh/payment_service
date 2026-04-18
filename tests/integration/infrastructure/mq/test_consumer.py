import pytest
import httpx
from unittest.mock import patch, MagicMock
from payment.infrastructure.mq.consumer import send_webhook
import payment.infrastructure.mq.consumer as consumer

@pytest.fixture(autouse=True)
def setup_http_client():
    """Фикстура для инициализации http_client перед тестами"""
    consumer.http_client = httpx.AsyncClient()
    yield
    # Не закрываем, так как в тестах мы мокаем post, 
    # но для чистоты можно было бы закрыть.
    # В данном случае просто обнуляем.
    consumer.http_client = None

@pytest.mark.asyncio
async def test_send_webhook_success():
    url = "http://example.com/webhook"
    payload = {"status": "success"}
    
    with patch.object(consumer.http_client, "post") as mock_post:
        mock_response = httpx.Response(200, request=httpx.Request("POST", url))
        mock_post.return_value = mock_response
        
        await send_webhook(url, payload)
        
        mock_post.assert_called_once()

@pytest.mark.asyncio
async def test_send_webhook_retry_then_success(monkeypatch):
    """Тестируем, что send_webhook делает ретраи при ошибках."""
    url = "http://example.com/webhook"
    payload = {"status": "success"}
    
    # Чтобы тесты не шли долго, уберем задержку ретраев
    from tenacity import wait_none
    monkeypatch.setattr("payment.infrastructure.mq.consumer.wait_exponential", lambda **kwargs: wait_none())

    with patch.object(consumer.http_client, "post") as mock_post:
        # Мокаем ответ, который выбрасывает ошибку при raise_for_status
        fail_response = httpx.Response(500, request=httpx.Request("POST", url))
        
        success_response = httpx.Response(200, request=httpx.Request("POST", url))
        
        # 2 раза упадем, на 3-й успех
        mock_post.side_effect = [fail_response, fail_response, success_response]
        
        await send_webhook(url, payload)
        
        assert mock_post.call_count == 3

@pytest.mark.asyncio
async def test_send_webhook_max_retries_reached(monkeypatch):
    url = "http://example.com/webhook"
    payload = {"status": "success"}
    
    from tenacity import wait_none
    monkeypatch.setattr("payment.infrastructure.mq.consumer.wait_exponential", lambda **kwargs: wait_none())

    with patch.object(consumer.http_client, "post") as mock_post:
        fail_response = httpx.Response(500, request=httpx.Request("POST", url))
        mock_post.return_value = fail_response
        
        # tenacity по умолчанию выбрасывает RetryError, если reraise=False
        from tenacity import RetryError
        with pytest.raises(RetryError):
            await send_webhook(url, payload)
        
        assert mock_post.call_count == 3
