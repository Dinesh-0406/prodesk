from functools import lru_cache

from app.core.config import settings
from app.integrations.ai.base import AIProvider


@lru_cache
def get_ai_provider() -> AIProvider:
    if settings.AI_PROVIDER == "openai":
        from app.integrations.ai.openai_provider import OpenAIProvider

        return OpenAIProvider(settings.OPENAI_API_KEY, settings.OPENAI_MODEL, settings.OPENAI_TIMEOUT_SECONDS)
    from app.integrations.ai.mock import MockAIProvider

    return MockAIProvider()


__all__ = ["AIProvider", "get_ai_provider"]
