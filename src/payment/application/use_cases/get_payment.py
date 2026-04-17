import logging
from typing import Optional
from payment.application.interfaces.payment_repository import IPaymentRepository
from payment.domain.entities.payment import Payment

logger = logging.getLogger(__name__)

class GetPaymentUseCase:
    def __init__(self, payment_repo: IPaymentRepository):
        self.payment_repo = payment_repo

    async def execute(self, payment_id: str) -> Optional[Payment]:
        logger.info(f"Fetching information for payment {payment_id}")
        payment = await self.payment_repo.get_by_id(payment_id)
        if not payment:
            logger.warning(f"Payment {payment_id} not found")
        return payment
