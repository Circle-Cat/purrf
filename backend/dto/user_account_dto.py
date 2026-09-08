"""DTOs for the account console (/admin/accounts).

Deliberately parallel to admin_permission_dto.AdminUserDto rather than
replacing it: the permission page keeps its own DTO, and the two coexisting is
the price of the two pages coexisting.
"""

from datetime import datetime

from backend.dto.base_dto import BaseDto


class UserAccountRowDto(BaseDto):
    """One row of the account console list."""

    user_id: int
    primary_email: str
    first_name: str
    last_name: str
    preferred_name: str | None = None
    user_type: str
    is_super_admin: bool
    is_active: bool
    deactivated_at: datetime | None = None
    deactivated_by: int | None = None
    deactivated_by_name: str | None = None
    deactivated_reason: str | None = None
    is_blocked: bool
    blocked_at: datetime | None = None
    blocked_by: int | None = None
    blocked_by_name: str | None = None
    blocked_reason: str | None = None
    # Scoped to the CALLER: true only when a pending request names the caller
    # as reviewer. A request is visible only to its named reviewer, so this
    # must not be a global "has anyone asked to block them".
    has_pending_block_request: bool


class SignInEmailDto(BaseDto):
    """One address the user can sign in with."""

    email: str
    otp_confirmed: bool
    is_primary: bool
    last_login_at: datetime | None = None


class SignInIdentityDto(BaseDto):
    """One federated identity linked to the account."""

    subject_identifier: str
    email_claim: str | None = None
    linked_at: datetime
    last_login_at: datetime | None = None


class UserSignInMethodsDto(BaseDto):
    """Every way into one account, for the detail page."""

    emails: list[SignInEmailDto]
    identities: list[SignInIdentityDto]
