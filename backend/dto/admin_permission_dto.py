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


class GrantDto(BaseDto):
    id: int
    user_id: int
    permission_name: str
    granted_source: str
    granted_by: int | None = None
    granted_timestamp: datetime
    revoked_by: int | None = None
    revoked_timestamp: datetime | None = None
    is_active: bool


class UserPermissionsViewDto(BaseDto):
    user_id: int
    active: list[str]
    history: list[GrantDto]


class AuditListDto(BaseDto):
    entries: list[GrantDto]
    total: int


class PermissionNamesRequestDto(BaseDto):
    permission_names: list[str]
