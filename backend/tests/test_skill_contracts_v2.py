"""Extra contract assertions added for capture v2."""
import inspect

from app.skills import delta_extraction, embedding


def test_embedding_skill_exposes_one_public_async_function() -> None:
    assert embedding.__all__ == ["embed_text"]
    assert inspect.iscoroutinefunction(embedding.embed_text)


def test_delta_extraction_exports() -> None:
    assert set(delta_extraction.__all__) == {
        "extract_delta",
        "apply_delta",
        "DeltaResult",
        "DeltaScope",
    }
    assert inspect.iscoroutinefunction(delta_extraction.extract_delta)
    # apply_delta is sync by design; it mutates a Pydantic model in-memory.
    assert callable(delta_extraction.apply_delta)
