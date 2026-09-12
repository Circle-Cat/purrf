"""The payload and the legacy CSV export have to describe the same people.

Both read the same rows and share the survey code tables, but they query
separately and encode differently. This pins them together on every field they
have in common, so a change to one that the other does not follow shows up here
rather than as a quiet difference in a matching run.

Temporary by design. The export is being retired; delete this file along with
it rather than repairing it, because at that point there is nothing left to
agree with.
"""

import json
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from backend.backfill.export_mentorship_records import fetch_participants_data
from backend.common.mentorship_enums import CommunicationMethod, ParticipantRole
from backend.entity.experience_entity import ExperienceEntity
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.entity.mentorship_round_participants_entity import (
    MentorshipRoundParticipantsEntity,
)
from backend.entity.preference_entity import PreferenceEntity
from backend.entity.users_entity import UsersEntity
from backend.mentorship.matching_payload_service import MatchingPayloadService
from backend.repository.mentorship_pairs_repository import MentorshipPairsRepository
from backend.repository.mentorship_round_participants_repository import (
    MentorshipRoundParticipantsRepository,
)
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)

# The export writes the bucket as a midpoint integer; the payload keeps the
# bucket. Same answer, two encodings.
_BUCKET_FOR_MIDPOINT = {0: "none", 2: "1_to_3", 4: "3_plus"}


class MatchingPayloadEquivalenceTest(BaseRepositoryTestLib):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.service = MatchingPayloadService(
            mentorship_round_participants_repository=MentorshipRoundParticipantsRepository(),
            mentorship_pairs_repository=MentorshipPairsRepository(),
            logger=MagicMock(),
        )
        self.round = MentorshipRoundEntity(
            name="2026 Autumn", required_meetings=5, description={}
        )
        await self.insert_entities([self.round])

    async def _person(self, *, role, preferred=None, survey=None, **participant_fields):
        user = UsersEntity(
            first_name="Grace",
            last_name="Hopper",
            preferred_name=preferred,
            timezone="America/New_York",
            timezone_updated_at=datetime.now(timezone.utc),
            communication_channel=CommunicationMethod.EMAIL,
            is_active=True,
            updated_timestamp=datetime.now(timezone.utc),
        )
        await self.insert_entities([user])
        await self.insert_entities([
            ExperienceEntity(
                user_id=user.user_id,
                education=[
                    {
                        "degree": "Master",
                        "school": "UCLA",
                        "field_of_study": "Computer Science",
                        "start_date": "2020-09-01",
                        # The placeholder both sides drop.
                        "end_date": "1970-01-01",
                    }
                ],
                work_history=[
                    {
                        "title": "Software Engineer",
                        "company_or_organization": "Circle Cat",
                        "start_date": "2022-01-01",
                        "end_date": None,
                        "is_current_job": True,
                    }
                ],
            ),
            PreferenceEntity(
                user_id=user.user_id,
                resume_guidance=True,
                technical_skills=True,
                specific_industry={"swe": True},
                profile_survey=survey or {},
            ),
            MentorshipRoundParticipantsEntity(
                user_id=user.user_id,
                round_id=self.round.round_id,
                participant_role=role,
                goal="Break into backend work",
                **participant_fields,
            ),
        ])
        return user

    async def _both_views(self, user_ids):
        payload = await self.service.build_matching_payload(
            self.session, self.round.round_id, user_ids
        )
        mentors_df, mentees_df = await fetch_participants_data(
            self.session, self.round.round_id
        )
        return payload, mentors_df, mentees_df

    def _assert_shared_fields_agree(self, record, row):
        self.assertEqual(record.user_id, str(row["user_id"]))
        self.assertEqual(
            record.display_name,
            (
                row["preferred_name"] or f"{row['first_name']} {row['last_name']}"
            ).strip(),
        )
        self.assertEqual(record.timezone, row["timezone"])
        self.assertEqual(record.goal, row["goal"])

        for key, value in record.skills.items():
            self.assertEqual(value, row[key] == "t", f"skill {key}")

        expected_ids = [
            i for i in str(row["expected_partner_user_id"]).split(",") if i.strip()
        ]
        self.assertEqual(record.expected_partner_ids, [i.strip() for i in expected_ids])

        education = json.loads(row["education"])
        self.assertEqual(len(record.education), len(education))
        self.assertEqual(record.education[0].school, education[0]["school"])
        # Both sides drop the 1970 placeholder rather than pass it on.
        self.assertIsNone(record.education[0].end_date)
        self.assertIsNone(education[0]["end_date"])

        work = json.loads(row["work_history"])
        self.assertEqual(record.work_history[0].title, work[0]["title"])
        self.assertEqual(
            record.work_history[0].company, work[0]["company_or_organization"]
        )

    async def test_mentor_rows_agree(self):
        mentor = await self._person(
            role=ParticipantRole.MENTOR,
            preferred="Amazing G",
            max_partners=2,
            expected_partner_user_id=[26, 31],
            survey={
                "career_transition": "path_b",
                "region": "us",
                "external_mentoring_exp": "1_to_3",
            },
        )
        mentee = await self._person(role=ParticipantRole.MENTEE)

        payload, mentors_df, _ = await self._both_views([
            mentor.user_id,
            mentee.user_id,
        ])
        record = payload.mentors[0]
        row = mentors_df.iloc[0]

        self._assert_shared_fields_agree(record, row)
        self.assertEqual(record.max_partners, row["max_partners"])
        self.assertEqual(record.career_transition, row["career_transition"])
        self.assertEqual(record.development_region, row["development_region"])
        self.assertEqual(
            record.external_mentoring_exp,
            _BUCKET_FOR_MIDPOINT[row["prev_mentoring_exp"]],
        )
        # The export carries an industry for mentors that nobody ever asked for.
        self.assertIsNone(record.specific_industry)

    async def test_mentee_rows_agree(self):
        mentor = await self._person(role=ParticipantRole.MENTOR, max_partners=1)
        mentee = await self._person(
            role=ParticipantRole.MENTEE,
            current_stage="job_searching",
            time_urgency="within_6_months",
            survey={
                "current_background": "non_tech_to_tech",
                "target_region": "canada",
            },
        )

        payload, _, mentees_df = await self._both_views([
            mentor.user_id,
            mentee.user_id,
        ])
        record = payload.mentees[0]
        row = mentees_df.iloc[0]

        self._assert_shared_fields_agree(record, row)
        self.assertEqual(record.transition_type, row["transition_type"])
        self.assertEqual(record.mentee_stage, row["mentee_stage"])
        self.assertEqual(record.urgency, row["urgency"])
        self.assertEqual(record.job_market_region, row["job_market_region"])
        self.assertEqual(record.specific_industry, json.loads(row["specific_industry"]))

    async def test_free_text_answer_is_split_rather_than_inlined(self):
        mentor = await self._person(
            role=ParticipantRole.MENTOR,
            max_partners=1,
            survey={
                "career_transition": "other",
                "career_transition_other": "Came over from bioinformatics",
            },
        )
        mentee = await self._person(role=ParticipantRole.MENTEE)

        payload, mentors_df, _ = await self._both_views([
            mentor.user_id,
            mentee.user_id,
        ])
        record = payload.mentors[0]

        # The export packs the text into the code field; the payload does not,
        # which is the one place the two deliberately disagree.
        self.assertEqual(
            mentors_df.iloc[0]["career_transition"],
            "other:Came over from bioinformatics",
        )
        self.assertIsNone(record.career_transition)
        self.assertEqual(
            record.career_transition_other, "Came over from bioinformatics"
        )


if __name__ == "__main__":
    unittest.main()
