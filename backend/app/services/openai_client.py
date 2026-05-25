from openai import AsyncOpenAI

from app.config import get_settings


def get_openai_client() -> AsyncOpenAI:
    settings = get_settings()
    return AsyncOpenAI(api_key=settings.openai_api_key)

