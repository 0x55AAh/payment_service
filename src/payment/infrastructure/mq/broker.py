from faststream.rabbit import RabbitBroker
from payment.infrastructure.config.settings import settings

broker = RabbitBroker(settings.RABBITMQ_URL)
