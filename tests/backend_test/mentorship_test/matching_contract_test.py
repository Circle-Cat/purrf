import json
import unittest
from pathlib import Path

from backend.mentorship.matching_contract import (
    CONTRACT_VERSION,
    SKILL_KEYS,
    MatchingPayload,
    PersonRecord,
)
from backend.mentorship.matching_contract_schema import render_schemas

CONTRACTS_DIR = Path(__file__).resolve().parents[3] / "backend/mentorship/contracts"


def _mentor(**overrides):
    base = dict(
        user_id="1",
        display_name="Ada L",
        timezone="America/New_York",
        skills={k: False for k in SKILL_KEYS},
        specific_industry={"swe": True, "ds": False, "pm": False, "uiux": False},
        education=[],
        work_history=[],
        expected_partner_ids=[],
        unexpected_partner_ids=[],
        goal="",
        max_partners=2,
    )
    base.update(overrides)
    return base


class MatchingContractTest(unittest.TestCase):
    def test_user_id_coerced_to_string(self):
        person = PersonRecord(**_mentor(user_id=7))
        self.assertEqual(person.user_id, "7")

    def test_rejects_unknown_skill_key(self):
        with self.assertRaises(ValueError):
            PersonRecord(**_mentor(skills={"not_a_skill": True}))

    def test_rejects_partial_skill_set(self):
        partial = {k: False for k in SKILL_KEYS[:-1]}
        with self.assertRaises(ValueError):
            PersonRecord(**_mentor(skills=partial))

    def test_rejects_unknown_mentee_stage(self):
        # employed_growing is the backend storage key, not the contract code the
        # export maps it to. Sending the wrong side of that map has to fail loudly.
        with self.assertRaises(ValueError):
            PersonRecord(**_mentor(mentee_stage="employed_growing"))

    def test_rejects_unknown_field(self):
        with self.assertRaises(ValueError):
            PersonRecord(**_mentor(primary_email="ada@example.com"))

    def test_payload_round_trips(self):
        payload = MatchingPayload(
            run_id="r1-20260912T000000Z-abc123",
            round_id=1,
            mentors=[PersonRecord(**_mentor())],
            mentees=[],
        )
        again = MatchingPayload.model_validate(json.loads(payload.model_dump_json()))
        self.assertEqual(again.contract_version, CONTRACT_VERSION)
        self.assertEqual(again.mentors[0].user_id, "1")

    def test_generated_schemas_are_committed_and_current(self):
        # Compare only; never write. The bazel runfiles tree is read-only.
        #
        # Compare parsed documents rather than bytes: the repo formatter reflows
        # JSON (prettier collapses short arrays onto one line, which json.dumps
        # cannot reproduce), so a byte comparison would make the generator and
        # the formatter permanently disagree. Whitespace is not the contract.
        rendered = render_schemas()
        self.assertEqual(
            set(rendered),
            {"matching_payload.schema.json", "matching_result.schema.json"},
        )
        for filename, text in rendered.items():
            committed = (CONTRACTS_DIR / filename).read_text(encoding="utf-8")
            self.assertEqual(
                json.loads(committed),
                json.loads(text),
                f"{filename} is stale; regenerate it with "
                f"python3 -m backend.mentorship.matching_contract_schema, "
                f"run bazel run //:format, and commit",
            )


if __name__ == "__main__":
    unittest.main()
