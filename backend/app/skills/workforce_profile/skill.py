from app.config import get_settings
from app.models.workforce import ExtractedWorkerProfile
from app.services.openai_client import get_openai_client


PROFILE_PROMPT = """
Convert the CV or resume below into a worker profile for organisational
planning. Extract only information supported by the document. Every skill,
experience item and qualification must include a short verbatim excerpt in
its evidence list with source set to the supplied filename. Do not infer age,
gender, ethnicity, health, religion, family status, political beliefs or any
other protected or sensitive characteristic. Do not infer career preferences
from employment history; leave career_preferences empty unless the document
states them explicitly. Use conservative skill levels. This is a draft which
the worker will review and confirm.

Source filename: {filename}

Document text:
{text}
"""


async def extract_worker_profile(filename: str, text: str) -> ExtractedWorkerProfile:
    client = get_openai_client()
    settings = get_settings()
    response = await client.responses.parse(
        model=settings.openai_extraction_model,
        input=PROFILE_PROMPT.format(filename=filename, text=text),
        text_format=ExtractedWorkerProfile,
        temperature=0,
    )
    return response.output_parsed
