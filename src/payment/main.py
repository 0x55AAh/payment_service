from fastapi import FastAPI, Depends

from payment.infrastructure.config.settings import settings
from payment.presentation.api.dependencies import verify_api_key
from payment.infrastructure.database.mappers import start_mappers

# Инициализация логирования
settings.setup_logging()

# Инициализация мапперов БД
start_mappers()

from payment.presentation.api.v1 import payments

def create_app() -> FastAPI:
    app = FastAPI(
        title="Payment Service",
        description="Async Payment Processing Service",
        version="1.0.2",
        dependencies=[Depends(verify_api_key)]
    )

    app.include_router(payments.router, prefix="/api/v1")

    return app

app = create_app()
