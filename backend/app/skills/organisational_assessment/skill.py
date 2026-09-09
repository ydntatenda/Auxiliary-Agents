import json

from app.config import get_settings
from app.models.graph import Workflow
from app.models.workforce import OrganisationalAssessment
from app.services.openai_client import get_openai_client


ASSESSMENT_PROMPT = """
You are designing a safer future operating model from an evidence-backed
workflow graph and worker profiles.

For each workflow step, choose human, assist, automate_with_approval, or
automate. Score technical automation potential from 0 to 100, but do not treat
technical possibility as permission to automate. Preserve human judgement for
high-consequence, ambiguous, interpersonal or policy-authority decisions.
Every recommendation must cite workflow step IDs, gap IDs or worker-profile
evidence excerpts supplied below. Never infer protected or sensitive worker
characteristics. A CV claim is not verified truth. Propose role transitions
only where profile evidence supports them, set requires_human_review to true,
and frame them as options for worker and manager review, never employment
decisions.

Identify controls, data dependencies, approval gates, rollback needs,
knowledge updates and measurable success criteria. Describe the future
workflow as an ordered human-agent operating model. Do not claim an agent is
deployed. Put missing access, integrations, evaluation data, policy approval
and security work in deployment_prerequisites.

Workflow:
{workflow}

Confirmed and draft worker profiles:
{workers}
"""


async def assess_organisation(
    workflow: Workflow,
    workers: list[dict],
) -> OrganisationalAssessment:
    client = get_openai_client()
    settings = get_settings()
    response = await client.responses.parse(
        model=settings.openai_extraction_model,
        input=ASSESSMENT_PROMPT.format(
            workflow=workflow.model_dump_json(indent=2),
            workers=json.dumps(workers, indent=2, default=str),
        ),
        text_format=OrganisationalAssessment,
        temperature=0,
    )
    report = response.output_parsed
    return report.model_copy(update={"workflow_id": str(workflow.id)})
