import json
import unittest
from pathlib import Path
from typing import Literal, get_args, get_origin

from backend.common.mentorship_survey_codes import VOCABULARIES
from backend.mentorship.matching_contract import (
    INDUSTRY_KEYS,
    META_VERSION,
    SKILL_KEYS,
    Candidate,
    MatchingMeta,
    MenteeResult,
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

    def test_meta_and_person_round_trip_separately(self):
        # They land in different Redis keys and are read back one at a time, so
        # each has to survive a round trip on its own.
        meta = MatchingMeta(run_id="r1-20260912T000000Z-abc123", round_id=1)
        again = MatchingMeta.model_validate(json.loads(meta.model_dump_json()))
        self.assertEqual(again.contract_version, META_VERSION)

        person = PersonRecord(**_mentor())
        person_again = PersonRecord.model_validate(json.loads(person.model_dump_json()))
        self.assertEqual(person_again.user_id, "1")

    def test_unmatched_mentee_carries_no_score_and_no_match_type(self):
        result = MenteeResult(candidates=[Candidate(mentor_id="7", score=64)])
        self.assertIsNone(result.mentor_id)
        self.assertIsNone(result.score)
        self.assertIsNone(result.match_type)

    def test_rejects_a_score_on_a_mentee_nobody_was_assigned(self):
        with self.assertRaises(ValueError):
            MenteeResult(score=64)

    def test_mutual_choice_is_not_scored(self):
        # +1000 is the matcher's sentinel for "both asked for each other". It
        # would be read as a score beside the candidates, which carry real ones.
        result = MenteeResult(mentor_id="7", match_type="mutual_yes")
        self.assertIsNone(result.score)
        with self.assertRaises(ValueError):
            MenteeResult(mentor_id="7", match_type="mutual_yes", score=1000)

    def test_rejects_an_assignment_without_a_score_or_a_match_type(self):
        with self.assertRaises(ValueError):
            MenteeResult(mentor_id="7", match_type="hungarian")
        with self.assertRaises(ValueError):
            MenteeResult(mentor_id="7", score=64)

    def test_rejects_the_assigned_mentor_among_his_own_alternatives(self):
        with self.assertRaises(ValueError):
            MenteeResult(
                mentor_id="7",
                match_type="hungarian",
                score=64,
                candidates=[Candidate(mentor_id="7", score=64)],
            )

    def test_rejects_a_fourth_alternative(self):
        with self.assertRaises(ValueError):
            MenteeResult(
                candidates=[Candidate(mentor_id=str(i), score=60) for i in range(4)]
            )

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
            {
                "matching_meta.schema.json",
                "person_record.schema.json",
                "mentee_result.schema.json",
                "matching_run_result.schema.json",
            },
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
