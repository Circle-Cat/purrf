import unittest
from datetime import datetime, timezone

from backend.common.mentorship_enums import (
    CommunicationMethod,
    ParticipantRole,
    TrainingCategory,
    TrainingStatus,
)
from backend.common.recruiting_enums import ApplicationStage, JobKind, JobStatus
from backend.dto.training_audience_dto import TrainingAudienceFilterDto
from backend.entity.application_entity import ApplicationEntity
from backend.entity.job_entity import JobEntity
from backend.entity.training_course_entity import TrainingCourseEntity
from backend.entity.training_entity import TrainingEntity
from backend.entity.user_emails_entity import UserEmailsEntity
from backend.entity.users_entity import UsersEntity
from backend.repository.training_audience_repository import (
    TrainingAudienceRepository,
)
from tests.backend_test.repository_test.base_repository_test_lib import (
    BaseRepositoryTestLib,
)


class TestTrainingAudienceRepository(BaseRepositoryTestLib):
    """The audience search behind the bulk assignment card.

    Only active, unblocked people may ever be selectable: a row that reaches
    the page can be ticked and assigned, so the precondition is enforced here
    rather than trusted to the caller.
    """

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.repo = TrainingAudienceRepository()
        self.now = datetime.now(timezone.utc)

        self.internal = self._user("Ada", "Internal", is_internal=True)
        self.external = self._user("Bo", "External", is_internal=False)
        self.deactivated = self._user("Cy", "Gone", is_internal=True, is_active=False)
        self.blocked = self._user("Di", "Barred", is_internal=False, is_blocked=True)
        await self.insert_entities([
            self.internal,
            self.external,
            self.deactivated,
            self.blocked,
        ])

        await self.insert_entities([
            self._email(self.internal, "ada@circlecat.org", is_primary=True),
            self._email(self.internal, "ada.alt@example.com"),
            self._email(self.external, "bo@example.com", is_primary=True),
            self._email(self.deactivated, "cy@circlecat.org", is_primary=True),
            self._email(self.blocked, "di@example.com", is_primary=True),
        ])

    def _user(
        self, first_name, last_name, *, is_internal, is_active=True, is_blocked=False
    ):
        return UsersEntity(
            first_name=first_name,
            last_name=last_name,
            timezone="Asia/Shanghai",
            timezone_updated_at=self.now,
            communication_channel=CommunicationMethod.EMAIL,
            is_active=is_active,
            is_blocked=is_blocked,
            is_internal=is_internal,
            updated_timestamp=self.now,
        )

    def _email(self, user, email, *, is_primary=False):
        return UserEmailsEntity(
            user_id=user.user_id,
            email=email,
            otp_confirmed=True,
            is_primary=is_primary,
            added_at=self.now,
        )

    async def _search(self, filters=None, **kwargs):
        return await self.repo.search_audience(
            self.session,
            filters or TrainingAudienceFilterDto(),
            **kwargs,
        )

    async def test_deactivated_and_blocked_users_never_appear(self):
        rows, total = await self._search()

        self.assertEqual(
            [row.user_id for row in rows],
            [self.internal.user_id, self.external.user_id],
        )
        self.assertEqual(total, 2)

    async def test_user_id_filter_keeps_only_that_person(self):
        rows, total = await self._search(
            TrainingAudienceFilterDto(user_id=self.external.user_id)
        )

        self.assertEqual([row.user_id for row in rows], [self.external.user_id])
        self.assertEqual(total, 1)

    async def test_user_id_filter_cannot_reach_a_blocked_person(self):
        rows, total = await self._search(
            TrainingAudienceFilterDto(user_id=self.blocked.user_id)
        )

        self.assertEqual(rows, [])
        self.assertEqual(total, 0)

    async def test_total_counts_every_match_while_a_page_holds_one(self):
        first_page, total = await self._search(limit=1, offset=0)
        second_page, second_total = await self._search(limit=1, offset=1)

        self.assertEqual([row.user_id for row in first_page], [self.internal.user_id])
        self.assertEqual([row.user_id for row in second_page], [self.external.user_id])
        self.assertEqual(total, 2)
        self.assertEqual(second_total, 2)

    async def test_rows_carry_the_names_and_the_internal_flag(self):
        rows, _ = await self._search(
            TrainingAudienceFilterDto(user_id=self.internal.user_id)
        )

        self.assertEqual(rows[0].first_name, "Ada")
        self.assertEqual(rows[0].last_name, "Internal")
        self.assertTrue(rows[0].is_internal)

    async def _hire(self, user, role):
        """Give ``user`` a hired activity application carrying ``role``."""
        job = JobEntity(
            kind=JobKind.ACTIVITY,
            title=f"Mentorship {role.value}",
            status=JobStatus.PUBLISHED,
            mentorship_role=role,
        )
        await self.insert_entities([job])
        await self.insert_entities([
            ApplicationEntity(
                job_id=job.job_id,
                user_id=user.user_id,
                stage=ApplicationStage.HIRED,
            )
        ])

    async def test_search_matches_a_name_case_insensitively(self):
        rows, total = await self._search(TrainingAudienceFilterDto(search="ADA"))

        self.assertEqual([row.user_id for row in rows], [self.internal.user_id])
        self.assertEqual(total, 1)

    async def test_search_matches_an_alternative_address_not_only_the_primary(self):
        rows, _ = await self._search(TrainingAudienceFilterDto(search="ada.alt"))

        self.assertEqual([row.user_id for row in rows], [self.internal.user_id])

    async def test_search_matches_an_address_substring(self):
        rows, _ = await self._search(TrainingAudienceFilterDto(search="bo@"))

        self.assertEqual([row.user_id for row in rows], [self.external.user_id])

    async def test_search_over_a_shared_domain_reaches_both_kinds_of_address(self):
        rows, _ = await self._search(TrainingAudienceFilterDto(search="@example.com"))

        self.assertEqual(
            [row.user_id for row in rows],
            [self.internal.user_id, self.external.user_id],
        )

    async def test_internal_filter_keeps_only_people_with_a_company_account(self):
        rows, total = await self._search(
            TrainingAudienceFilterDto(user_type="internal")
        )

        self.assertEqual([row.user_id for row in rows], [self.internal.user_id])
        self.assertEqual(total, 1)

    async def test_external_filter_keeps_only_people_without_one(self):
        rows, _ = await self._search(TrainingAudienceFilterDto(user_type="external"))

        self.assertEqual([row.user_id for row in rows], [self.external.user_id])

    async def test_mentorship_filter_reads_a_hired_activity_application(self):
        await self._hire(self.external, ParticipantRole.MENTEE)

        rows, total = await self._search(
            TrainingAudienceFilterDto(mentorship_role=ParticipantRole.MENTEE)
        )

        self.assertEqual([row.user_id for row in rows], [self.external.user_id])
        self.assertEqual(total, 1)

    async def test_mentorship_filter_separates_the_two_roles(self):
        await self._hire(self.external, ParticipantRole.MENTEE)

        rows, _ = await self._search(
            TrainingAudienceFilterDto(mentorship_role=ParticipantRole.MENTOR)
        )

        self.assertEqual(rows, [])

    async def test_an_application_short_of_hired_is_not_a_mentorship_role(self):
        job = JobEntity(
            kind=JobKind.ACTIVITY,
            title="Mentee",
            status=JobStatus.PUBLISHED,
            mentorship_role=ParticipantRole.MENTEE,
        )
        await self.insert_entities([job])
        await self.insert_entities([
            ApplicationEntity(
                job_id=job.job_id,
                user_id=self.external.user_id,
                stage=ApplicationStage.RECRUITER_SCREENING,
            )
        ])

        rows, _ = await self._search(
            TrainingAudienceFilterDto(mentorship_role=ParticipantRole.MENTEE)
        )

        self.assertEqual(rows, [])

    async def test_facets_narrow_each_other(self):
        await self._hire(self.external, ParticipantRole.MENTEE)
        await self._hire(self.internal, ParticipantRole.MENTEE)

        rows, total = await self._search(
            TrainingAudienceFilterDto(
                mentorship_role=ParticipantRole.MENTEE, user_type="internal"
            )
        )

        self.assertEqual([row.user_id for row in rows], [self.internal.user_id])
        self.assertEqual(total, 1)

    async def _course(self, name):
        """A course with no package; assignability is not this query's concern."""
        course = TrainingCourseEntity(name=name, is_active=True)
        await self.insert_entities([course])
        return course

    async def _assign(self, user, course, status=TrainingStatus.TO_DO):
        row = TrainingEntity(
            user_id=user.user_id,
            course_id=course.course_id,
            status=status,
        )
        await self.insert_entities([row])
        return row

    async def test_assigned_filter_keeps_only_people_holding_that_course(self):
        course = await self._course("Culture")
        await self._assign(self.internal, course)

        rows, total = await self._search(
            TrainingAudienceFilterDto(
                course_id=course.course_id, course_status="assigned"
            )
        )

        self.assertEqual([row.user_id for row in rows], [self.internal.user_id])
        self.assertEqual(total, 1)

    async def test_not_assigned_filter_keeps_only_people_missing_that_course(self):
        course = await self._course("Culture")
        await self._assign(self.internal, course)

        rows, total = await self._search(
            TrainingAudienceFilterDto(
                course_id=course.course_id, course_status="not_assigned"
            )
        )

        self.assertEqual([row.user_id for row in rows], [self.external.user_id])
        self.assertEqual(total, 1)

    async def test_holding_another_course_does_not_count_as_holding_this_one(self):
        held = await self._course("Culture")
        wanted = await self._course("Residency")
        await self._assign(self.internal, held)

        rows, _ = await self._search(
            TrainingAudienceFilterDto(
                course_id=wanted.course_id, course_status="assigned"
            )
        )

        self.assertEqual(rows, [])

    async def test_a_category_row_without_a_course_is_not_holding_the_course(self):
        course = await self._course("Culture")
        await self.insert_entities([
            TrainingEntity(
                user_id=self.internal.user_id,
                category=TrainingCategory.CORPORATE_CULTURE_COURSE,
                status=TrainingStatus.TO_DO,
            )
        ])

        rows, _ = await self._search(
            TrainingAudienceFilterDto(
                course_id=course.course_id, course_status="assigned"
            )
        )

        self.assertEqual(rows, [])

    async def test_rows_carry_the_status_on_the_selected_course(self):
        course = await self._course("Culture")
        await self._assign(self.internal, course, status=TrainingStatus.DONE)

        rows, _ = await self._search(
            TrainingAudienceFilterDto(course_id=course.course_id)
        )

        by_user = {row.user_id: row.course_status for row in rows}
        self.assertEqual(by_user[self.internal.user_id], TrainingStatus.DONE)
        self.assertIsNone(by_user[self.external.user_id])

    async def test_rows_count_courses_and_completions_when_no_course_is_selected(self):
        first = await self._course("Culture")
        second = await self._course("Residency")
        await self._assign(self.internal, first, status=TrainingStatus.DONE)
        await self._assign(self.internal, second, status=TrainingStatus.IN_PROGRESS)

        rows, _ = await self._search()

        by_user = {row.user_id: row for row in rows}
        self.assertEqual(by_user[self.internal.user_id].assigned_course_count, 2)
        self.assertEqual(by_user[self.internal.user_id].done_course_count, 1)
        self.assertEqual(by_user[self.external.user_id].assigned_course_count, 0)
        self.assertEqual(by_user[self.external.user_id].done_course_count, 0)

    async def test_ids_list_every_match_in_page_order(self):
        ids = await self.repo.list_audience_ids(
            self.session, TrainingAudienceFilterDto()
        )

        self.assertEqual(ids, [self.internal.user_id, self.external.user_id])

    async def test_ids_honour_the_filters(self):
        ids = await self.repo.list_audience_ids(
            self.session, TrainingAudienceFilterDto(user_type="external")
        )

        self.assertEqual(ids, [self.external.user_id])

    async def test_count_reports_matches_without_fetching_a_page(self):
        total = await self.repo.count_audience(
            self.session, TrainingAudienceFilterDto()
        )

        self.assertEqual(total, 2)

    async def test_restricting_to_a_set_of_ids_intersects_with_the_filters(self):
        rows, total = await self._search(
            restrict_user_ids=[self.internal.user_id, self.blocked.user_id]
        )

        self.assertEqual([row.user_id for row in rows], [self.internal.user_id])
        self.assertEqual(total, 1)

    async def test_an_empty_restriction_matches_nobody(self):
        rows, total = await self._search(restrict_user_ids=[])

        self.assertEqual(rows, [])
        self.assertEqual(total, 0)

    async def test_no_restriction_leaves_the_filters_alone(self):
        rows, _ = await self._search(restrict_user_ids=None)

        self.assertEqual(
            [row.user_id for row in rows],
            [self.internal.user_id, self.external.user_id],
        )

    async def test_ids_respect_the_restriction(self):
        ids = await self.repo.list_audience_ids(
            self.session,
            TrainingAudienceFilterDto(),
            restrict_user_ids=[self.external.user_id],
        )

        self.assertEqual(ids, [self.external.user_id])


if __name__ == "__main__":
    unittest.main()
