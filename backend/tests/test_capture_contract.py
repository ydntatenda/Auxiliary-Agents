"""Unit tests for the capture wire-contract layer.

The full HTTP path lives behind a Postgres dependency, so these tests pin
the bits that don't need a DB: response shape, payload normalisation, and
the JSON-vs-multipart dispatch decisions.
"""
from app.api.capture import (
    SourceResponse,
    UpdateSourcePayload,
    _normalise_chat_messages,
    _to_source_response,
)
from app.models.db import SourceRow


def _row(**overrides):
    base = dict(
        modality="text",
        label="Operator notes",
        contributor_role="operator",
        status="ready",
        error=None,
        meta={"char_count": 42},
        assembled_text="open the appeal, decide, close.",
        order=2,
    )
    base.update(overrides)
    row = SourceRow(**base)
    # SourceRow uses server defaults for id / workflow_id, which the test
    # doesn't go through the DB to assign. Stub them in.
    from uuid import uuid4

    row.id = uuid4()
    row.workflow_id = uuid4()
    return row


def test_source_response_uses_spec_field_names() -> None:
    row = _row()
    response = _to_source_response(row)
    assert isinstance(response, SourceResponse)
    payload = response.model_dump()
    assert "id" in payload and "source_id" not in payload
    assert payload["assembled_text"] == "open the appeal, decide, close."
    assert "has_assembled_text" not in payload
    assert payload["modality"] == "text"
    assert payload["label"] == "Operator notes"
    assert payload["contributor_role"] == "operator"
    assert payload["order"] == 2


def test_source_response_passes_through_failed_sources() -> None:
    row = _row(status="failed", error="whisper 500", assembled_text=None, meta=None)
    payload = _to_source_response(row).model_dump()
    assert payload["status"] == "failed"
    assert payload["error"] == "whisper 500"
    assert payload["assembled_text"] is None


def test_normalise_chat_accepts_question_answer_pairs() -> None:
    raw = [
        {"question": "Walk me through.", "answer": "I open the appeal."},
        {"question": "Common mistakes?", "answer": "Forgetting to send the receipt."},
    ]
    out = _normalise_chat_messages(raw)
    assert out == [
        {"role": "question", "content": "Walk me through."},
        {"role": "answer", "content": "I open the appeal."},
        {"role": "question", "content": "Common mistakes?"},
        {"role": "answer", "content": "Forgetting to send the receipt."},
    ]


def test_normalise_chat_accepts_role_content_turns() -> None:
    raw = [
        {"role": "question", "content": "Who approves?"},
        {"role": "answer", "content": "Director."},
    ]
    assert _normalise_chat_messages(raw) == raw


def test_normalise_chat_skips_blank_sides() -> None:
    raw = [
        {"question": "Walk me through.", "answer": ""},
        {"question": "", "answer": "A standalone note."},
    ]
    assert _normalise_chat_messages(raw) == [
        {"role": "question", "content": "Walk me through."},
        {"role": "answer", "content": "A standalone note."},
    ]


def test_update_source_payload_allows_label_only() -> None:
    payload = UpdateSourcePayload.model_validate({"label": "Policy PDF"})
    assert payload.label == "Policy PDF"
    assert payload.move is None


def test_update_source_payload_allows_move_only() -> None:
    payload = UpdateSourcePayload.model_validate({"move": "up"})
    assert payload.label is None
    assert payload.move == "up"


def test_update_source_payload_rejects_unknown_move() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        UpdateSourcePayload.model_validate({"move": "sideways"})
