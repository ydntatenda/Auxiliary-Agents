from google import genai

from app.config import get_settings


def get_gemini_client() -> genai.Client:
    settings = get_settings()
    return genai.Client(api_key=settings.google_api_key)

