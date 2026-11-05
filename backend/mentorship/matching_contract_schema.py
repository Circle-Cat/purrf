"""Export the matching contract as JSON Schema.

purrf-matcher keeps a copy of the output. Regenerate and commit after any change
to the models; a test compares the committed files against the models and fails
when they drift.

    python3 -m backend.mentorship.matching_contract_schema
"""

import json
from pathlib import Path

from backend.mentorship.matching_contract import (
    MatchingMeta,
    MatchingRunResult,
    MenteeResult,
    PersonRecord,
)

# One file per addressable Redis value, so every schema can be checked against
# something that is actually stored.
_MODELS = {
    "matching_meta.schema.json": MatchingMeta,
    "person_record.schema.json": PersonRecord,
    "mentee_result.schema.json": MenteeResult,
    "matching_run_result.schema.json": MatchingRunResult,
}


def render_schemas() -> dict[str, str]:
    """Return {filename: file content}.

    The drift test compares against this rather than writing files, because the
    bazel runfiles tree a test runs in is read-only.
    """
    return {
        filename: json.dumps(model.model_json_schema(), indent=2, ensure_ascii=False)
        + "\n"
        for filename, model in _MODELS.items()
    }


def write_schemas(out_dir: Path) -> None:
    """Write every schema into out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for filename, text in render_schemas().items():
        (out_dir / filename).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    write_schemas(Path(__file__).resolve().parent / "contracts")
