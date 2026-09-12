import json
import unittest
from pathlib import Path
from typing import Literal, get_args, get_origin

from backend.common.mentorship_survey_codes import VOCABULARIES
from backend.mentorship.matching_contract import (
    CONTRACT_VERSION,
    INDUSTRY_KEYS,
    SKILL_KEYS,
    MatchingPayload,
    PersonRecord,
)
from backend.mentorship.matching_contract_schema import render_schemas

CONTRACTS_DIR = Path(__file__).resolve().parents[3] / "backend/mentorship/contracts"


def _mentor(**overrides):
    base = dict(
        role="mentor",
        user_id="1",
        display_name="Ada L",
        timezone="America/New_York",
        skills={k: False for k in SKILL_KEYS},
        education=[],
        work_history=[],
        expected_partner_ids=[],
        unexpected_partner_ids=[],
        goal="",
        max_partners=2,
    )
    base.update(overrides)
    return base


def _mentee(**overrides):
    base = dict(
        role="mentee",
        user_id="2",
        display_name="Grace H",
        timezone="America/New_York",
        skills={k: False for k in SKILL_KEYS},
        specific_industry={"swe": True, "ds": False, "pm": False, "uiux": False},
        education=[],
        work_history=[],
        expected_partner_ids=[],
        unexpected_partner_ids=[],
        goal="",
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

    def test_mentor_carries_no_industry(self):
        # The registration form only asks mentees, so a mentor has no answer to
        # send. It is absent rather than four falses, which would read as a
        # deliberate "none of these".
        self.assertIsNone(PersonRecord(**_mentor()).specific_industry)

    def test_mentee_must_declare_an_industry(self):
        with self.assertRaises(ValueError):
            PersonRecord(**_mentee(specific_industry=None))

    def test_mentor_must_not_carry_a_leftover_industry(self):
        industry = {"swe": True, "ds": False, "pm": False, "uiux": False}
        with self.assertRaises(ValueError):
            PersonRecord(**_mentor(specific_industry=industry))

    def test_mentee_industry_needs_every_key(self):
        with self.assertRaises(ValueError):
            PersonRecord(**_mentee(specific_industry={"swe": True}))

    def test_rejects_unknown_role(self):
        with self.assertRaises(ValueError):
            PersonRecord(**_mentor(role="admin"))

    def test_rejects_unknown_mentee_stage(self):
        # employed_growing is the backend storage key, not the contract code the
        # export maps it to. Sending the wrong side of that map has to fail loudly.
        with self.assertRaises(ValueError):
            PersonRecord(**_mentee(mentee_stage="employed_growing"))

    def test_rejects_unknown_field(self):
        with self.assertRaises(ValueError):
            PersonRecord(**_mentor(primary_email="ada@example.com"))

    def test_external_experience_keeps_the_bucket_the_mentor_picked(self):
        person = PersonRecord(**_mentor(external_mentoring_exp="1_to_3"))
        self.assertEqual(person.external_mentoring_exp, "1_to_3")

    def test_rejects_the_midpoint_encoding_of_external_experience(self):
        # The export used to send 2 for "1_to_3" and 4 for "3_plus", and the
        # rationale printed the midpoint as a count. The bucket is the answer.
        with self.assertRaises(ValueError):
            PersonRecord(**_mentor(external_mentoring_exp=2))

    def test_internal_round_counts_are_separate_from_the_self_report(self):
        person = PersonRecord(
            **_mentor(
                external_mentoring_exp="3_plus",
                mentorship_rounds_participated=2,
                mentorship_rounds_completed=1,
            )
        )
        self.assertEqual(person.external_mentoring_exp, "3_plus")
        self.assertEqual(person.mentorship_rounds_participated, 2)
        self.assertEqual(person.mentorship_rounds_completed, 1)

    def test_free_text_answer_travels_beside_the_enum_not_inside_it(self):
        person = PersonRecord(
            **_mentor(
                career_transition=None,
                career_transition_other="Switched over from bioinformatics",
            )
        )
        self.assertIsNone(person.career_transition)
        self.assertEqual(
            person.career_transition_other, "Switched over from bioinformatics"
        )

    def test_rejects_the_inline_other_encoding(self):
        # The CSV export packed free text into the same field as "other:<text>".
        with self.assertRaises(ValueError):
            PersonRecord(
                **_mentor(career_transition="other:Switched over from bioinformatics")
            )

    def test_payload_round_trips(self):
        payload = MatchingPayload(
            run_id="r1-20260912T000000Z-abc123",
            round_id=1,
            mentors=[PersonRecord(**_mentor())],
            mentees=[PersonRecord(**_mentee())],
        )
        again = MatchingPayload.model_validate(json.loads(payload.model_dump_json()))
        self.assertEqual(again.contract_version, CONTRACT_VERSION)
        self.assertEqual(again.mentors[0].user_id, "1")

    def test_every_code_the_contract_allows_has_wording(self):
        """A renamed or added code without a sentence behind it fails here.

        The wording is what a consumer renders instead of keeping its own
        translation, so a code that has none puts a raw value in front of
        somebody.
        """
        for field_name, labels in VOCABULARIES.items():
            if field_name == "skills":
                self.assertEqual(set(labels), set(SKILL_KEYS))
                continue
            if field_name == "specific_industry":
                self.assertEqual(set(labels), set(INDUSTRY_KEYS))
                continue

            annotation = PersonRecord.model_fields[field_name].annotation
            options: set[str] = set()
            for arg in get_args(annotation):
                if get_origin(arg) is Literal:
                    options.update(get_args(arg))
            self.assertTrue(options, f"{field_name} is not a Literal any more")
            self.assertEqual(
                options,
                set(labels),
                f"{field_name}: codes and wording have drifted apart",
            )

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
