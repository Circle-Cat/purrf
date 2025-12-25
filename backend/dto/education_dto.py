from dataclasses import dataclass
from datetime import date
from backend.common.mentorship_enums import Degree


@dataclass
class EducationDto:
    id: str
    degree: Degree
    school: str
    fieldOfStudy: str
    startDate: date
    endDate: date
