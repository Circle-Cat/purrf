from datetime import date
from backend.dto.base_dto import BaseDto
from backend.common.mentorship_enums import Degree


class EducationDto(BaseDto):
    id: str
    degree: Degree
    school: str
    field_of_study: str
    start_date: date
    end_date: date
