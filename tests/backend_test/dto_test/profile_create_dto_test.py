import unittest
from datetime import date

from pydantic import ValidationError

from backend.dto.profile_create_dto import (
    EducationRequestDto,
    ProfileCreateDto,
    WorkHistoryRequestDto,
)


def _first_of_month(months_ahead: int) -> date:
    today = date.today()
    index = today.year * 12 + today.month - 1 + months_ahead
    return date(index // 12, index % 12 + 1, 1)


class TestEducationRequestDto(unittest.TestCase):
    def _valid_kwargs(self):
        return dict(
            degree="Bachelor",
            school="State University",
            field_of_study="Physics",
            start_date=date(2016, 9, 1),
            end_date=date(2020, 6, 1),
        )

    def test_valid_entry(self):
        dto = EducationRequestDto(**self._valid_kwargs())
        self.assertEqual(dto.school, "State University")

    def test_end_before_start_rejected(self):
        kwargs = self._valid_kwargs()
        kwargs["start_date"] = date(2020, 3, 1)
        kwargs["end_date"] = date(2019, 1, 1)
        with self.assertRaises(ValidationError):
            EducationRequestDto(**kwargs)

    def test_end_in_start_month_accepted(self):
        kwargs = self._valid_kwargs()
        kwargs["start_date"] = date(2020, 3, 1)
        kwargs["end_date"] = date(2020, 3, 1)
        EducationRequestDto(**kwargs)

    def test_start_next_month_rejected(self):
        kwargs = self._valid_kwargs()
        kwargs["start_date"] = _first_of_month(1)
        kwargs["end_date"] = _first_of_month(2)
        with self.assertRaises(ValidationError):
            EducationRequestDto(**kwargs)

    def test_start_this_month_accepted(self):
        # The form sends the first of the picked month, so the current month
        # must pass whatever day it is.
        kwargs = self._valid_kwargs()
        kwargs["start_date"] = _first_of_month(0)
        kwargs["end_date"] = _first_of_month(0)
        EducationRequestDto(**kwargs)

    def test_blank_school_rejected(self):
        kwargs = self._valid_kwargs()
        kwargs["school"] = "   "
        with self.assertRaises(ValidationError):
            EducationRequestDto(**kwargs)

    def test_blank_field_of_study_rejected(self):
        kwargs = self._valid_kwargs()
        kwargs["field_of_study"] = ""
        with self.assertRaises(ValidationError):
            EducationRequestDto(**kwargs)


class TestWorkHistoryRequestDto(unittest.TestCase):
    def _valid_kwargs(self):
        return dict(
            title="Engineer",
            company_or_organization="Acme",
            start_date=date(2020, 1, 1),
            is_current_job=False,
            end_date=date(2022, 5, 1),
        )

    def test_valid_entry(self):
        dto = WorkHistoryRequestDto(**self._valid_kwargs())
        self.assertEqual(dto.title, "Engineer")

    def test_current_job_without_end_accepted(self):
        kwargs = self._valid_kwargs()
        kwargs["is_current_job"] = True
        kwargs["end_date"] = None
        WorkHistoryRequestDto(**kwargs)

    def test_past_job_without_end_rejected(self):
        kwargs = self._valid_kwargs()
        kwargs["end_date"] = None
        with self.assertRaises(ValidationError):
            WorkHistoryRequestDto(**kwargs)

    def test_past_job_end_before_start_rejected(self):
        kwargs = self._valid_kwargs()
        kwargs["start_date"] = date(2021, 6, 1)
        kwargs["end_date"] = date(2021, 5, 1)
        with self.assertRaises(ValidationError):
            WorkHistoryRequestDto(**kwargs)

    def test_past_job_end_in_start_month_accepted(self):
        kwargs = self._valid_kwargs()
        kwargs["start_date"] = date(2021, 6, 1)
        kwargs["end_date"] = date(2021, 6, 1)
        WorkHistoryRequestDto(**kwargs)

    def test_start_next_month_rejected(self):
        kwargs = self._valid_kwargs()
        kwargs["is_current_job"] = True
        kwargs["start_date"] = _first_of_month(1)
        kwargs["end_date"] = None
        with self.assertRaises(ValidationError):
            WorkHistoryRequestDto(**kwargs)

    def test_start_this_month_accepted(self):
        kwargs = self._valid_kwargs()
        kwargs["is_current_job"] = True
        kwargs["start_date"] = _first_of_month(0)
        kwargs["end_date"] = None
        WorkHistoryRequestDto(**kwargs)

    def test_blank_title_rejected(self):
        kwargs = self._valid_kwargs()
        kwargs["title"] = "  "
        with self.assertRaises(ValidationError):
            WorkHistoryRequestDto(**kwargs)

    def test_blank_company_rejected(self):
        kwargs = self._valid_kwargs()
        kwargs["company_or_organization"] = " "
        with self.assertRaises(ValidationError):
            WorkHistoryRequestDto(**kwargs)


class TestProfileCreateDto(unittest.TestCase):
    def test_camel_case_payload_with_bad_education_rejected(self):
        with self.assertRaises(ValidationError):
            ProfileCreateDto.model_validate({
                "education": [
                    {
                        "school": "X",
                        "degree": "Bachelor",
                        "fieldOfStudy": "Y",
                        "startDate": "2020-03-01",
                        "endDate": "2019-01-01",
                    }
                ]
            })


if __name__ == "__main__":
    unittest.main()
