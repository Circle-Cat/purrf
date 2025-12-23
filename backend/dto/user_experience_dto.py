from dataclasses import dataclass
from backend.entity.users_entity import UsersEntity


@dataclass
class UserExperienceDto:
    user: UsersEntity
    education: list[dict] | None = None
    work_history: list[dict] | None = None
