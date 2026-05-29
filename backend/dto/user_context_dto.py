from dataclasses import dataclass, field
from backend.common.user_role import IdentityType, UserRole


@dataclass
class UserContextDto:
    sub: str
    primary_email: str
    identity_type: IdentityType = IdentityType.EXTERNAL
    first_name: str | None = None
    last_name: str | None = None
    last_login_at: int | None = None
    user_id: int | None = None
    email_verified: bool = False
    roles: list[UserRole] = field(default_factory=list)

    def has_role(self, role: UserRole) -> bool:
        return role in self.roles
