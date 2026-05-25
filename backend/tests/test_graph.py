from app.models.graph import DecisionRule, Gap, Step, Workflow


def test_workflow_round_trips_through_json_shape() -> None:
    workflow = Workflow(
        name="Citation appeals processing",
        description="Review and resolve student citation appeals.",
        unit="GT P&T",
        source_modality="text",
        source_transcript="Open the appeal, review evidence, decide outcome.",
        steps=[
            Step(
                id="review_appeal",
                order=1,
                title="Review appeal",
                description="Open the appeal and review the appellant's evidence.",
                outputs=["Initial recommendation"],
                decision_rules=[
                    DecisionRule(
                        condition="Appeal exceeds $200",
                        then_step_id="manager_review",
                    )
                ],
            )
        ],
        gaps=[
            Gap(
                id="gap_1",
                step_id="review_appeal",
                field="approver",
                description="Approver for high-value appeals is unclear.",
                severity="important",
            )
        ],
    )

    payload = workflow.model_dump(mode="json")
    restored = Workflow.model_validate(payload)

    assert restored.id == workflow.id
    assert restored.steps[0].decision_rules[0].then_step_id == "manager_review"
    assert restored.gaps[0].severity == "important"

