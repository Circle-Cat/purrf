from dataclasses import dataclass, field
from backend.common.identity_type import IdentityType
from backend.common.permissions import Permission


@dataclass
class UserContextDto:
    sub: str
    primary_email: str
    identity_type: IdentityType = IdentityType.EXTERNAL
    is_service_account: bool = False
    is_super_admin: bool = False
    first_name: str | None = None
    last_name: str | None = None
    last_login_at: int | None = None
    user_id: int | None = None
    email_verified: bool = False
    # True when the login's email collides with an existing account: no local
    # user is created and the session is held at the verify wall, where a
    # successful OTP links this sub into the owning account (PUR-480).
    needs_link: bool = False
    permissions: frozenset[Permission] = field(default_factory=frozenset)

    def has_permission(self, permission: Permission) -> bool:
        return permission in self.permissions
