from dataclasses import dataclass
from backend.entity.users_entity import UsersEntity


@dataclass
class UserExperienceDto:
    user: UsersEntity
    education: dict | None = None
    work_experience: dict | None = None
