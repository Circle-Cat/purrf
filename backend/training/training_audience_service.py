"""The audience search behind bulk training assignment."""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.constants import (
    INTERNAL_GOOGLE_ACCOUNT_DOMAIN,
    MicrosoftAccountStatus,
    MicrosoftGroups,
)
from backend.common.exceptions import ConflictError
from backend.common.identity_type import IdentityType
from backend.dto.training_audience_dto import (
    TrainingAudienceFilterDto,
    TrainingAudienceIdsDto,
    TrainingAudienceRowDto,
    TrainingAudienceSearchDto,
)


class TrainingAudienceService:
    """Resolves who a course may be assigned to.

    Everything the SQL can express lives in the repository. This layer owns
    the two things it cannot: the LDAP group, which is a Redis snapshot rather
    than a table, and the size limit on selecting a whole result set.
    """

    # Selecting everyone submits an id list, so the cap bounds one request
    # body and one transaction. Refusing above it is deliberate: truncating
    # would assign a subset silently, and there is no undo.
    ID_SELECTION_CAP = 1000

    def __init__(
        self,
        logger,
        training_audience_repository,
        user_emails_repository,
        ldap_service,
    ):
        """
        Args:
            logger: Structured logger.
            training_audience_repository (TrainingAudienceRepository): The
                paginated audience read.
            user_emails_repository (UserEmailsRepository): Address lookups,
                both for resolving ldaps and for the contact column.
            ldap_service (LdapService): The Azure group snapshot in Redis.
        """
        self.logger = logger
        self.training_audience_repository = training_audience_repository
        self.user_emails_repository = user_emails_repository
        self.ldap_service = ldap_service

    async def _restrict_to_group(
        self,
        session: AsyncSession,
        filters: TrainingAudienceFilterDto,
        group: MicrosoftGroups | None,
    ) -> list[int] | None:
        """The user_ids an LDAP group narrows the search to.

        Read at ``active`` only. Azure's terminated is a different fact from
        purrf's is_active -- the purrf side of offboarding is done by hand --
        and offering both meanings of "left" in one search bar guarantees a
        misreading.

        A read that fails is allowed to fail the request. An empty set would
        read as "nobody in that group is missing the course", which is the
        opposite of the truth.

        Args:
            session (AsyncSession): The active async database session.
            filters (TrainingAudienceFilterDto): The rest of the search, whose
                type facet decides whether a group means anything.
            group (MicrosoftGroups | None): The group to narrow to.

        Returns:
            list[int] | None: None when no group was asked for, otherwise the
            matching user_ids -- empty when the group holds no purrf account.

        Raises:
            ValueError: A group was asked for outside the internal type.
        """
        if group is None:
            return None
        if filters.user_type != IdentityType.INTERNAL:
            raise ValueError(
                "An LDAP group only exists for an internal account. "
                "Set the type to internal to filter by group."
            )

        ldaps_by_group = self.ldap_service.get_ldaps_by_status_and_group(
            MicrosoftAccountStatus.ACTIVE, [group]
        )
        ldaps = ldaps_by_group.get(group.value, {}).get(
            MicrosoftAccountStatus.ACTIVE.value, {}
        )
        if not ldaps:
            self.logger.warning(
                "LDAP group %s holds no active member; the search matches nobody.",
                group.value,
            )
            return []

        # The ldap is the local part of the corporate address, derived the same
        # way the sync job writes it. Only the Google domain can be signed in
        # with, so one address per person is the whole of it.
        emails = sorted(f"{ldap}{INTERNAL_GOOGLE_ACCOUNT_DOMAIN}" for ldap in ldaps)
        rows = await self.user_emails_repository.list_by_emails(session, emails)
        return sorted({row.user_id for row in rows})

    async def search_audience(
        self,
        session: AsyncSession,
        filters: TrainingAudienceFilterDto,
        group: MicrosoftGroups | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> TrainingAudienceSearchDto:
        """One page of the people a search matches.

        Args:
            session (AsyncSession): The active async database session.
            filters (TrainingAudienceFilterDto): The requested filters.
            group (MicrosoftGroups | None): LDAP group to narrow to.
            limit (int): Max rows to return.
            offset (int): Rows to skip.

        Returns:
            TrainingAudienceSearchDto: The page and the total.
        """
        restrict_user_ids = await self._restrict_to_group(session, filters, group)
        rows, total = await self.training_audience_repository.search_audience(
            session,
            filters,
            restrict_user_ids=restrict_user_ids,
            limit=limit,
            offset=offset,
        )
        contact_by_user_id = (
            await self.user_emails_repository.get_contact_emails_by_user_ids(
                session, [row.user_id for row in rows]
            )
        )
        return TrainingAudienceSearchDto(
            rows=[
                TrainingAudienceRowDto(
                    user_id=row.user_id,
                    first_name=row.first_name,
                    last_name=row.last_name,
                    preferred_name=row.preferred_name,
                    contact_email=contact_by_user_id.get(row.user_id),
                    is_internal=row.is_internal,
                    course_status=row.course_status,
                    assigned_course_count=row.assigned_course_count,
                    done_course_count=row.done_course_count,
                )
                for row in rows
            ],
            total=total,
        )

    async def list_audience_ids(
        self,
        session: AsyncSession,
        filters: TrainingAudienceFilterDto,
        group: MicrosoftGroups | None = None,
    ) -> TrainingAudienceIdsDto:
        """Every id a search matches, for selecting a whole result set.

        Counted before it is read: over the cap the call is refused, never
        trimmed, so the number the operator sees is the number that will be
        assigned.

        Args:
            session (AsyncSession): The active async database session.
            filters (TrainingAudienceFilterDto): The requested filters.
            group (MicrosoftGroups | None): LDAP group to narrow to.

        Returns:
            TrainingAudienceIdsDto: The ids and their count.

        Raises:
            ConflictError: More matches than one selection may hold.
        """
        restrict_user_ids = await self._restrict_to_group(session, filters, group)
        total = await self.training_audience_repository.count_audience(
            session, filters, restrict_user_ids=restrict_user_ids
        )
        if total > self.ID_SELECTION_CAP:
            raise ConflictError(
                f"This search matches {total} people, more than the "
                f"{self.ID_SELECTION_CAP} one selection can hold. "
                "Narrow the search and select again."
            )
        user_ids = await self.training_audience_repository.list_audience_ids(
            session, filters, restrict_user_ids=restrict_user_ids
        )
        return TrainingAudienceIdsDto(user_ids=user_ids, total=total)
