import logging
from fastapi import APIRouter, Header, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from payment.presentation.schemas.payment import PaymentCreateSchema, PaymentResponseSchema, PaymentDetailSchema
from payment.application.use_cases.create_payment import CreatePaymentUseCase
from payment.application.use_cases.get_payment import GetPaymentUseCase
from payment.infrastructure.database.repositories.payment_repository import SqlAlchemyPaymentRepository
from payment.infrastructure.database.session import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["payments"])

@router.post("", response_model=PaymentResponseSchema, status_code=status.HTTP_202_ACCEPTED)
async def create_payment(
    payload: PaymentCreateSchema,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Создание нового платежа.
    """
    logger.info(f"API: Received request to create payment with idempotency key: {idempotency_key}")
    repository = SqlAlchemyPaymentRepository(db)
    use_case = CreatePaymentUseCase(repository)
    payment = await use_case.execute(payload, idempotency_key)
    return payment

@router.get("/{payment_id}", response_model=PaymentDetailSchema)
async def get_payment(
    payment_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Получение информации о платеже.
    """
    logger.info(f"API: Received request to get payment {payment_id}")
    repository = SqlAlchemyPaymentRepository(db)
    use_case = GetPaymentUseCase(repository)
    payment = await use_case.execute(payment_id)
    
    if not payment:
        logger.warning(f"API: Payment {payment_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    
    return payment
