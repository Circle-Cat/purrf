import unittest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone, timedelta, date
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4
from backend.profile.profile_command_service import ProfileCommandService
from backend.entity.users_entity import UsersEntity
from backend.dto.profile_create_dto import (
    ProfileCreateDto,
    UsersRequestDto,
    EducationRequestDto,
    WorkHistoryRequestDto,
)
from backend.common.mentorship_enums import CommunicationMethod, UserTimezone
from backend.entity.experience_entity import ExperienceEntity
from backend.common.mentorship_enums import Degree


class TestProfileCommandService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.users_repository = AsyncMock()
        self.experience_repository = AsyncMock()
        self.logger = MagicMock()

        self.service = ProfileCommandService(
            users_repository=self.users_repository,
            logger=self.logger,
            experience_repository=self.experience_repository,
        )

        self.session = AsyncMock(spec=AsyncSession)

    def _create_profile_dto(
        self,
        first_name="Alice",
        timezone=UserTimezone.AMERICA_LOS_ANGELES,
        communication_method=CommunicationMethod.EMAIL,
        education=None,
        work_history=None,
    ) -> ProfileCreateDto:
        user_dto = UsersRequestDto(
            first_name=first_name,
            last_name="Smith",
            timezone=timezone,
            communication_method=communication_method,
            preferred_name="Ali",
            alternative_emails=["ali@example.com"],
            linkedin_link="https://linkedin.com/in/alice",
        )

        return ProfileCreateDto(
            user=user_dto, education=education or [], work_history=work_history or []
        )

    async def test_update_users_success_no_timezone_change(self):
        """Successfully update user information without changing timezone."""
        now = datetime.now(timezone.utc)
        existing_user = UsersEntity(
            user_id=1,
            first_name="Old",
            timezone=UserTimezone.AMERICA_LOS_ANGELES,
            timezone_updated_at=now - timedelta(days=10),
        )

        profile_dto = self._create_profile_dto(
            first_name="NewName", timezone=UserTimezone.AMERICA_LOS_ANGELES
        )

        self.users_repository.upsert_users.side_effect = lambda s, u: u

        result = await self.service.update_users(
            self.session, profile_dto, existing_user
        )

        self.assertEqual(result.first_name, "NewName")
        self.assertEqual(result.timezone, UserTimezone.AMERICA_LOS_ANGELES)
        self.users_repository.upsert_users.assert_awaited_once()

    async def test_update_users_timezone_success_after_30_days(self):
        """Update timezone successfully when more than 30 days have passed since last update."""
        last_update = datetime.now(timezone.utc) - timedelta(days=31)
        existing_user = UsersEntity(
            user_id=1,
            timezone=UserTimezone.AMERICA_LOS_ANGELES,
            timezone_updated_at=last_update,
        )

        profile_dto = self._create_profile_dto(timezone=UserTimezone.ASIA_SHANGHAI)

        self.users_repository.upsert_users.side_effect = lambda s, u: u

        result = await self.service.update_users(
            self.session, profile_dto, existing_user
        )

        self.assertEqual(result.timezone, UserTimezone.ASIA_SHANGHAI)
        self.assertGreater(result.timezone_updated_at, last_update)

    async def test_update_users_timezone_restriction_error(self):
        """Updating timezone too frequently (less than 30 days) should raise ValueError."""
        last_update = datetime.now(timezone.utc) - timedelta(days=5)
        existing_user = UsersEntity(
            user_id=1,
            timezone=UserTimezone.AMERICA_LOS_ANGELES,
            timezone_updated_at=last_update,
        )

        profile_dto = self._create_profile_dto(timezone=UserTimezone.AMERICA_NEW_YORK)

        with self.assertRaises(ValueError):
            await self.service.update_users(self.session, profile_dto, existing_user)

        self.users_repository.upsert_users.assert_not_awaited()

    async def test_update_users_database_error(self):
        """Database error occurs during save; error should be logged and re-raised."""
        existing_user = UsersEntity(
            user_id=1,
            timezone=UserTimezone.AMERICA_LOS_ANGELES,
            timezone_updated_at=datetime.now(timezone.utc),
        )

        profile_dto = self._create_profile_dto(
            timezone=UserTimezone.AMERICA_LOS_ANGELES
        )

        self.users_repository.upsert_users.side_effect = Exception("Connection Timeout")

        with self.assertRaises(Exception):
            await self.service.update_users(self.session, profile_dto, existing_user)

    async def test_update_education_no_change_skips_upsert(self):
        """The data from the frontend is the same as in the database
        (order may differ), no database operation is performed."""
        user_id = 1
        edu_id1 = str(uuid4())
        edu_id2 = str(uuid4())
        start_date_str = "2025-01-01"
        end_date_str = "2026-01-01"

        # Construct existing database data
        existing_entity = ExperienceEntity(user_id=user_id)
        existing_entity.education = [
            {
                "id": edu_id1,
                "school": "Stanford",
                "degree": Degree.BACHELOR.value,
                "field_of_study": "Computer Science",
                "start_date": start_date_str,
                "end_date": end_date_str,
            },
            {
                "id": edu_id2,
                "school": "Stanford",
                "degree": Degree.MASTER.value,
                "field_of_study": "Computer Science",
                "start_date": start_date_str,
                "end_date": end_date_str,
            },
        ]
        self.experience_repository.get_experience_by_user_id.return_value = (
            existing_entity
        )

        # Provide input data with the same content
        profile_dto = self._create_profile_dto(
            education=[
                EducationRequestDto(
                    id=edu_id2,
                    school="Stanford",
                    degree=Degree.MASTER,
                    field_of_study="Computer Science",
                    start_date=date.fromisoformat(start_date_str),
                    end_date=date.fromisoformat(end_date_str),
                ),
                EducationRequestDto(
                    id=edu_id1,
                    school="Stanford",
                    degree=Degree.BACHELOR,
                    field_of_study="Computer Science",
                    start_date=date.fromisoformat(start_date_str),
                    end_date=date.fromisoformat(end_date_str),
                ),
            ]
        )

        result = await self.service.update_education(self.session, profile_dto, user_id)

        self.experience_repository.upsert_experience.assert_not_awaited()
        self.assertEqual(result, existing_entity)

    async def test_update_work_history_content_changed_success(self):
        """Content changed (same ID), update occurs and timestamp is set."""
        user_id = 1
        work_id = str(uuid4())
        today = date.today()

        existing_entity = ExperienceEntity(user_id=user_id)
        existing_entity.work_history = [
            {
                "id": work_id,
                "company_or_organization": "Google",
                "title": "Junior",
                "is_current_job": False,
                "start_date": today.isoformat(),
                "end_date": today.isoformat(),
            }
        ]
        self.experience_repository.get_experience_by_user_id.return_value = (
            existing_entity
        )

        # Modify title to Senior
        profile_dto = self._create_profile_dto(
            work_history=[
                WorkHistoryRequestDto(
                    id=work_id,
                    company_or_organization="Google",
                    title="Senior",
                    is_current_job=True,
                    start_date=today,
                    end_date=today,
                )
            ]
        )

        result = await self.service.update_work_history(
            self.session, profile_dto, user_id
        )

        self.experience_repository.upsert_experience.assert_awaited_once()
        self.assertEqual(result.work_history[0]["title"], "Senior")
        self.assertIsNotNone(result.updated_timestamp)

    async def test_update_education_new_item_generates_id(self):
        """Adding a new education item (ID is None), generates UUID automatically."""
        user_id = 1
        self.experience_repository.get_experience_by_user_id.return_value = None

        new_edu_dto = EducationRequestDto(
            id=None,
            school="MIT",
            degree=Degree.PROFESSIONAL,
            field_of_study="Engineering",
            start_date=date.today(),
            end_date=date.today(),
        )
        profile_dto = self._create_profile_dto(education=[new_edu_dto])

        result = await self.service.update_education(self.session, profile_dto, user_id)

        self.assertIsNotNone(new_edu_dto.id)
        self.experience_repository.upsert_experience.assert_awaited_once()
        self.assertEqual(result.education[0]["id"], new_edu_dto.id)

    async def test_update_work_history_delete_item_success(self):
        """All work history items are deleted, database update is executed."""
        user_id = 1
        work_id = str(uuid4())
        today = date.today()

        existing_entity = ExperienceEntity(user_id=user_id)
        existing_entity.work_history = [
            {
                "id": work_id,
                "company_or_organization": "Google",
                "title": "Junior",
                "is_current_job": False,
                "start_date": today.isoformat(),
                "end_date": today.isoformat(),
            }
        ]
        self.experience_repository.get_experience_by_user_id.return_value = (
            existing_entity
        )

        profile_dto = self._create_profile_dto(work_history=[])

        result = await self.service.update_work_history(
            self.session, profile_dto, user_id
        )

        self.experience_repository.upsert_experience.assert_awaited_once()
        self.assertEqual(len(result.work_history), 0)
        self.assertIsNotNone(result.updated_timestamp)


if __name__ == "__main__":
    unittest.main()
