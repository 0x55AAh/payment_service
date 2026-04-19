import logging
from uuid import UUID

from payment.application.interfaces.payment_repository import IPaymentRepository
from payment.domain.entities.payment import Payment

logger = logging.getLogger(__name__)

class GetPaymentUseCase:
    """
    Бизнес-логика получения информации о платеже.
    """
    def __init__(self, payment_repo: IPaymentRepository):
        self.payment_repo = payment_repo

    async def execute(self, payment_id: UUID | str) -> Payment | None:
        """
        Ищет платеж по его идентификатору.

        Args:
            payment_id: Идентификатор платежа.

        Returns:
            Payment | None: Сущность платежа или None, если не найден.
        """
        logger.info(f"Fetching information for payment {payment_id}")
        payment = await self.payment_repo.get_by_id(payment_id)
        if not payment:
            logger.warning(f"Payment {payment_id} not found")
        return payment
