from app.core.assembly import _format_header


def test_header_includes_label_modality_and_role() -> None:
    header = _format_header("voice", "Jane's walkthrough", "operator")
    assert header == "=== Source: Jane's walkthrough (voice, operator) ==="


def test_header_falls_back_to_placeholder_label() -> None:
    header = _format_header("document", None, None)
    assert header == "=== Source: (no label) (document) ==="


def test_header_role_is_optional() -> None:
    header = _format_header("text", "Policy PDF", None)
    assert header == "=== Source: Policy PDF (text) ==="
