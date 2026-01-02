import unittest
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from backend.entity.users_entity import UsersEntity
from backend.entity.experience_entity import ExperienceEntity
from backend.entity.training_entity import TrainingEntity
from backend.common.mentorship_enums import (
    UserTimezone,
    Degree,
    TrainingStatus,
    TrainingCategory,
    CommunicationMethod,
)
from backend.dto.profile_dto import ProfileDto
from backend.dto.users_dto import UsersDto
from backend.dto.work_history_dto import WorkHistoryDto
from backend.dto.education_dto import EducationDto
from backend.dto.training_dto import TrainingDto
from backend.profile.profile_mapper import ProfileMapper


class TestProfileMapper(unittest.TestCase):
    def setUp(self):
        """Prepare test data."""
        self.now = datetime.now(timezone.utc)

        # Instantiate the mapper since methods are instance methods
        self.mapper = ProfileMapper()

        self.users_entity = UsersEntity(
            user_id=1,
            first_name="Alice",
            last_name="Admin",
            timezone=UserTimezone.ASIA_SHANGHAI,
            timezone_updated_at=self.now - timedelta(hours=2),
            communication_channel=CommunicationMethod.EMAIL,
            primary_email="alice@example.com",
            updated_timestamp=self.now,
            preferred_name="Alice",
            alternative_emails=["bob@example.com"],
            linkedin_link="http://linkedin.com/alice",
        )

        self.training_entities = [
            TrainingEntity(
                training_id=1,
                user_id=self.users_entity.user_id,
                category=TrainingCategory.CORPORATE_CULTURE_COURSE,
                completed_timestamp=self.now - timedelta(days=5),
                status=TrainingStatus.DONE,
            ),
            TrainingEntity(
                training_id=2,
                user_id=self.users_entity.user_id,
                category=TrainingCategory.RESIDENCY_PROGRAM_ONBOARDING,
                completed_timestamp=self.now - timedelta(days=3),
                status=TrainingStatus.IN_PROGRESS,
                deadline=self.now + timedelta(days=4),
                link="http://example.com/1",
            ),
        ]

        self.experience_entity = ExperienceEntity(
            experience_id=10,
            user_id=self.users_entity.user_id,
            work_history=[
                {
                    "id": str(uuid4()),
                    "title": "Software Engineer",
                    "company_or_organization": "TechCorp",
                    "start_date": "2015-01-01",
                    "end_date": "2019-12-31",
                    "is_currentJ_job": False,
                }
            ],
            education=[
                {
                    "id": str(uuid4()),
                    "degree": Degree.BACHELOR.value,
                    "school": "XYZ University",
                    "field_of_study": "Computer Science",
                    "start_date": "2011-08-01",
                    "end_date": "2015-05-15",
                }
            ],
        )

    def test_map_users_entity_to_dto(self):
        """Test mapping of basic user information using _map_user."""
        dto = self.mapper._map_user(self.users_entity)

        self.assertIsInstance(dto, UsersDto)
        self.assertEqual(dto.id, self.users_entity.user_id)
        self.assertEqual(dto.first_name, self.users_entity.first_name)
        self.assertEqual(
            dto.communication_method, self.users_entity.communication_channel
        )
        self.assertEqual(dto.alternative_emails, ["bob@example.com"])
        self.assertEqual(dto.timezone, UserTimezone.ASIA_SHANGHAI)

    def test_map_experience_to_work_history_dto(self):
        """Test mapping of work history using _map_work_history."""
        dtos = self.mapper._map_work_history(self.experience_entity)

        self.assertEqual(len(dtos), 1)
        dto = dtos[0]
        self.assertIsInstance(dto, WorkHistoryDto)
        self.assertEqual(dto.title, "Software Engineer")
        self.assertEqual(dto.company_or_organization, "TechCorp")
        self.assertEqual(dto.is_current_job, False)

    def test_map_experience_to_education_dto(self):
        """Test mapping of education history using _map_education."""
        dtos = self.mapper._map_education(self.experience_entity)

        self.assertEqual(len(dtos), 1)
        dto = dtos[0]
        self.assertIsInstance(dto, EducationDto)
        self.assertEqual(dto.school, "XYZ University")
        self.assertEqual(dto.degree, Degree.BACHELOR)
        self.assertEqual(dto.field_of_study, "Computer Science")

    def test_map_training_entity_to_dto(self):
        """Test mapping of a single training record using _map_training."""
        training = self.training_entities[0]
        dto = self.mapper._map_training(training)

        self.assertIsInstance(dto, TrainingDto)
        self.assertEqual(dto.id, training.training_id)
        self.assertEqual(dto.category, TrainingCategory.CORPORATE_CULTURE_COURSE)
        self.assertEqual(dto.status, TrainingStatus.DONE)

    def test_map_to_profile_dto_full(self):
        """Test the main mapping method with full data."""
        profile_dto = self.mapper.map_to_profile_dto(
            self.users_entity, self.experience_entity, self.training_entities
        )

        self.assertIsInstance(profile_dto, ProfileDto)
        self.assertEqual(profile_dto.id, self.users_entity.user_id)
        self.assertEqual(profile_dto.user.first_name, "Alice")
        self.assertEqual(len(profile_dto.work_history), 1)
        self.assertEqual(len(profile_dto.education), 1)
        self.assertEqual(len(profile_dto.training), 2)

        self.assertEqual(
            profile_dto.work_history[0].company_or_organization, "TechCorp"
        )
        self.assertEqual(profile_dto.training[1].status, TrainingStatus.IN_PROGRESS)

    def test_map_to_profile_dto_minimal(self):
        """Test the main mapping method with optional related data set to None."""
        profile_dto = self.mapper.map_to_profile_dto(self.users_entity, None, None)

        self.assertEqual(profile_dto.id, self.users_entity.user_id)
        self.assertEqual(profile_dto.work_history, [])
        self.assertEqual(profile_dto.education, [])
        self.assertEqual(profile_dto.training, [])
        self.assertIsNotNone(profile_dto.user)

    def test_map_experience_none_safe(self):
        """Verify defensive handling when experience is None."""
        self.assertEqual(self.mapper._map_work_history(None), [])
        self.assertEqual(self.mapper._map_education(None), [])

    def test_users_entity_alternative_emails_none(self):
        """Verify that alternative_emails is normalized to an empty list when None."""
        self.users_entity.alternative_emails = None
        dto = self.mapper._map_user(self.users_entity)
        self.assertEqual(dto.alternative_emails, [])

    def test_pydantic_serialization_alias(self):
        """Verify Pydantic serialization uses camelCase aliases for API output."""
        profile_dto = self.mapper.map_to_profile_dto(
            self.users_entity, self.experience_entity, []
        )
        json_data = profile_dto.model_dump(by_alias=True)

        self.assertIn("workHistory", json_data)
        self.assertIn("firstName", json_data["user"])
        self.assertIn("companyOrOrganization", json_data["workHistory"][0])

    def test_map_to_profile_dto_partial_include(self):
        """Test conditional inclusion: include education only, exclude work history."""
        profile_dto = self.mapper.map_to_profile_dto(
            self.users_entity,
            self.experience_entity,
            self.training_entities,
            include_work_history=False,
            include_education=True,
        )

        self.assertEqual(profile_dto.education[0].school, "XYZ University")
        self.assertEqual(profile_dto.work_history, [])
        self.assertTrue(len(profile_dto.training) > 0)

    def test_map_to_profile_dto_exclude_both(self):
        """Test conditional inclusion: exclude both work history and education."""
        profile_dto = self.mapper.map_to_profile_dto(
            self.users_entity,
            self.experience_entity,
            [],
            include_work_history=False,
            include_education=False,
        )

        self.assertEqual(profile_dto.work_history, [])
        self.assertEqual(profile_dto.education, [])


if __name__ == "__main__":
    unittest.main()
