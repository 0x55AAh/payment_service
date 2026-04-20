from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader

from payment.infrastructure.config.settings import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

async def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    Проверяет валидность API-ключа из заголовка запроса.
    
    Использует схему APIKeyHeader для извлечения ключа из заголовка 'X-API-Key'.
    Сравнивает полученный ключ со значением из настроек приложения.

    Args:
        api_key (str): Значение API-ключа, полученное из заголовка.

    Returns:
        str: Валидный API-ключ.

    Raises:
        HTTPException: Если API-ключ не совпадает с установленным в конфигурации (401 Unauthorized).
    """
    if api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )
    return api_key
