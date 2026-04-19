from fastapi.testclient import TestClient

from payment.main import app

client = TestClient(app)

def test_api_auth_missing_header():
    # Проверка на эндпоинте получения платежа
    response = client.get("/api/v1/payments/some-uuid")
    # FastAPI Security вернет 401 "Not authenticated", если заголовок отсутствует
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"

def test_api_auth_invalid_key():
    # Проверка на эндпоинте создания платежа
    response = client.post(
        "/api/v1/payments",
        headers={"X-API-Key": "wrong_key"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API Key"
