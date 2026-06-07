"""Extraction eval harness.

A fixture-driven scorer that exercises the workflow extraction skill end
to end and reports per-axis pass / fail. The harness is domain-agnostic;
the citation appeals fixture is one instance of a general capability.

Public surface lives in submodules:
    fixtures: schema, loader, multi-source transcript builder.
    scorers : the five pure scoring functions.
    report  : ScorerResult, EvalReport, terminal renderer.
    runner  : CLI entry point and the orchestrator that calls extraction.
"""
