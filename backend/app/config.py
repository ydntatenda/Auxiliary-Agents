from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://agentic_ops:agentic_ops@localhost:5432/agentic_ops"
    frontend_origin: str = "http://localhost:5173"
    upload_dir: Path = Path("./uploads")

    openai_api_key: str | None = None
    google_api_key: str | None = None

    openai_extraction_model: str = "gpt-5.4"
    openai_render_model: str = "gpt-5.4"
    openai_clarification_model: str = "gpt-5.4"
    openai_transcription_model: str = "whisper-1"
    gemini_video_model: str = "gemini-2.5-pro"

    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    clarification_provider: Literal["openai", "openrouter"] = "openai"
    openrouter_clarification_model: str = "moonshotai/kimi-k2.6"

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
