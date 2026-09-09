# organisational_assessment

Produces a governed future-state assessment from the workflow graph and
worker profiles. It scores automation potential, identifies unresolved gaps,
designs a human-agent workflow, proposes worker-reviewed role transitions and
lists the knowledge and deployment work that must follow.

## Public surface

`assess_organisation(workflow: Workflow, workers: list[dict]) -> OrganisationalAssessment`

## Safety boundary

The output is advisory. It cannot deploy an agent or make an employment
decision. Worker transitions require human review, and recommendations may use
only evidence supplied in the workflow and profiles.
