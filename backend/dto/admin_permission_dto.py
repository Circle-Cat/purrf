from datetime import datetime

from backend.dto.base_dto import BaseDto


class AdminUserDto(BaseDto):
    user_id: int
    primary_email: str
    first_name: str
    last_name: str
    is_active: bool
    is_super_admin: bool
    preferred_name: str | None = None
    user_type: str


class UserListDto(BaseDto):
    users: list[AdminUserDto]
    total: int


class GrantPersonDto(BaseDto):
    """Who a user id on a grant row refers to.

    The three name fields travel separately and are rendered that way, which is
    the product rule ``backend/common/name_utils`` states for admin and audit
    views: substituting one for another loses the identity such a view exists to
    confirm. No display name is composed here.
    """

    user_id: int
    first_name: str
    last_name: str
    preferred_name: str | None = None


class GrantDto(BaseDto):
    id: int
    user_id: int
    permission_name: str
    granted_source: str
    granted_by: int | None = None
    # Nullable: super admins derived without a promotion marker have no timestamp.
    granted_timestamp: datetime | None = None
    revoked_by: int | None = None
    revoked_timestamp: datetime | None = None
    is_active: bool
    # True when the holder is currently a super admin (so they hold this
    # permission by super-admin derivation, in addition to any real grant).
    is_super_admin: bool = False
    # The three ids above, resolved to people in one batched lookup so no view
    # has to render a bare integer. None when the id has no users row -- a
    # deleted account, or a derived row that has no actor at all.
    user: GrantPersonDto | None = None
    granted_by_user: GrantPersonDto | None = None
    revoked_by_user: GrantPersonDto | None = None


class PermissionCatalogEntryDto(BaseDto):
    name: str
    description: str


class UserPermissionsViewDto(BaseDto):
    user_id: int
    active: list[str]
    history: list[GrantDto]


class AuditListDto(BaseDto):
    entries: list[GrantDto]
    total: int


class PermissionNamesRequestDto(BaseDto):
    permission_names: list[str]
