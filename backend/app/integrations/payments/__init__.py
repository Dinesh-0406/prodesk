from functools import lru_cache

from app.core.config import settings
from app.integrations.payments.base import PaymentProvider


@lru_cache
def get_payment_provider() -> PaymentProvider:
    if settings.PAYMENT_PROVIDER == "razorpay":
        from app.integrations.payments.razorpay import RazorpayProvider

        return RazorpayProvider(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET, settings.RAZORPAY_WEBHOOK_SECRET)
    from app.integrations.payments.mock import MockPaymentProvider

    return MockPaymentProvider(settings.MOCK_PAYMENT_SECRET, settings.FRONTEND_URL)


__all__ = ["PaymentProvider", "get_payment_provider"]
