import asyncio

from app.config import get_settings
from app.services.gemini_client import get_gemini_client


SCREEN_ANALYSIS_PROMPT = """
You are watching a screen recording of an employee performing a work task
while narrating what they're doing.

Produce a structured log with two parallel tracks, interleaved chronologically:

ACTIONS: timestamped UI events visible on screen.
  Format: [MM:SS] <actor> <verb> <object>
  Examples:
    [00:14] User opens "Citation Appeals" tab in T2 Flex
    [01:32] User types in the notes field

NARRATION: timestamped statements from the audio track.
  Format: [MM:SS] "<verbatim quote>"

Rules:
- Be precise about what you can see: form field names, button labels, menu items
- Describe field values as roles, not specific values
  (e.g. "enters the appellant's name" not "enters Jennifer Martinez")
- If something is unclear or off-screen, mark as [unclear: <best guess>]
- Do NOT fabricate steps you cannot see or hear

At the end, on a new line, list under "TOOLS:" any applications or systems
the employee used (e.g. "T2 Flex, Outlook, Excel").
"""


async def analyze_screen_recording(file_path: str) -> str:
    client = get_gemini_client()
    settings = get_settings()
    uploaded = await asyncio.to_thread(client.files.upload, file=file_path)
    response = await asyncio.to_thread(
        client.models.generate_content,
        model=settings.gemini_video_model,
        contents=[uploaded, SCREEN_ANALYSIS_PROMPT],
    )
    return response.text or ""

