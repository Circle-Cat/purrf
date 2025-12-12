from dataclasses import dataclass, field
from backend.common.user_role import UserRole


@dataclass
class UserContextDto:
    sub: str
    primary_email: str
    roles: list[UserRole] = field(default_factory=list)

    def has_role(self, role: UserRole) -> bool:
        return role in self.roles
