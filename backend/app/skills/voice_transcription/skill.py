from app.config import get_settings
from app.services.openai_client import get_openai_client


async def transcribe_audio(file_path: str) -> str:
    client = get_openai_client()
    settings = get_settings()
    with open(file_path, "rb") as audio_file:
        transcript = await client.audio.transcriptions.create(
            model=settings.openai_transcription_model,
            file=audio_file,
        )
    return transcript.text

