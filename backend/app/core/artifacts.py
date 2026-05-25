import json
from pathlib import Path
from typing import Any


ARTIFACT_ROOT = Path("artifacts") / "workflows"


def workflow_artifact_dir(workflow_id: str) -> Path:
    path = ARTIFACT_ROOT / workflow_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_text_artifact(workflow_id: str, filename: str, content: str) -> Path:
    path = workflow_artifact_dir(workflow_id) / filename
    path.write_text(content, encoding="utf-8")
    return path


def write_json_artifact(workflow_id: str, filename: str, content: Any) -> Path:
    path = workflow_artifact_dir(workflow_id) / filename
    path.write_text(json.dumps(content, indent=2, default=str), encoding="utf-8")
    return path
