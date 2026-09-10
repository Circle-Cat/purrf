"""Reads the population the bulk training assignment card assigns to."""

from sqlalchemy import Row, Select, false, func, null, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.identity_type import IdentityType
from backend.common.mentorship_enums import TrainingStatus
from backend.common.recruiting_enums import ApplicationStage, JobKind
from backend.dto.training_audience_dto import TrainingAudienceFilterDto
from backend.entity.application_entity import ApplicationEntity
from backend.entity.job_entity import JobEntity
from backend.entity.training_entity import TrainingEntity
from backend.entity.user_emails_entity import UserEmailsEntity
from backend.entity.users_entity import UsersEntity


class TrainingAudienceRepository:
    """The people a course may be assigned to, filtered and paginated."""

    @staticmethod
    def _any_email_matches(pattern: str):
        """EXISTS filter over every address the person claims.

        Primary alone forks one person into two identities, so the substring
        runs across all of their user_emails rows. Addresses are stored
        lowercased, so the column needs no lower().

        Args:
            pattern (str): A lowercased LIKE pattern.

        Returns:
            ColumnElement[bool]: A correlated EXISTS.
        """
        return (
            select(UserEmailsEntity.email_id)
            .where(
                UserEmailsEntity.user_id == UsersEntity.user_id,
                UserEmailsEntity.email.like(pattern),
            )
            .exists()
        )

    @staticmethod
    def _holds_mentorship_role(role) -> object:
        """EXISTS filter for an admitted mentor or mentee.

        The role is carried by the job the person was hired into, not by a job
        kind of its own: there is no MENTORSHIP kind, activity jobs hold a
        mentorship_role. Anything short of HIRED is an applicant, not a
        participant.

        Args:
            role (ParticipantRole): The role to look for.

        Returns:
            ColumnElement[bool]: A correlated EXISTS.
        """
        return (
            select(ApplicationEntity.application_id)
            .join(JobEntity, ApplicationEntity.job_id == JobEntity.job_id)
            .where(
                ApplicationEntity.user_id == UsersEntity.user_id,
                ApplicationEntity.stage == ApplicationStage.HIRED,
                JobEntity.kind == JobKind.ACTIVITY,
                JobEntity.mentorship_role == role,
            )
            .exists()
        )

    @staticmethod
    def _holds_course(course_id: int):
        """EXISTS filter for a training row on this exact course.

        Keyed on (user_id, course_id), the pair the partial unique index
        covers. A legacy row carrying only a category is not this course: it
        would let a top-up skip somebody who holds nothing on the course.

        Args:
            course_id (int): The course to look for.

        Returns:
            ColumnElement[bool]: A correlated EXISTS.
        """
        return (
            select(TrainingEntity.training_id)
            .where(
                TrainingEntity.user_id == UsersEntity.user_id,
                TrainingEntity.course_id == course_id,
            )
            .exists()
        )

    @classmethod
    def _conditions(
        cls,
        filters: TrainingAudienceFilterDto,
        restrict_user_ids: list[int] | None = None,
    ) -> list:
        """The WHERE terms for one filter set, precondition included.

        Args:
            filters (TrainingAudienceFilterDto): The requested filters.
            restrict_user_ids (list[int] | None): When not None, the only
                user_ids that may match, as resolved from a store the query
                cannot join. An empty list matches nobody, which is what an
                LDAP group holding no purrf account means -- reading it as "no
                restriction" would silently widen the search to everyone.

        Returns:
            list: Conditions to AND together.
        """
        conditions = [
            UsersEntity.is_active.is_(True),
            UsersEntity.is_blocked.is_(False),
        ]
        if filters.search:
            pattern = f"%{filters.search.lower()}%"
            conditions.append(
                or_(
                    func.lower(UsersEntity.first_name).like(pattern),
                    func.lower(UsersEntity.last_name).like(pattern),
                    func.lower(UsersEntity.preferred_name).like(pattern),
                    cls._any_email_matches(pattern),
                )
            )
        if filters.user_id is not None:
            conditions.append(UsersEntity.user_id == filters.user_id)
        if filters.user_type == IdentityType.INTERNAL:
            conditions.append(UsersEntity.is_internal.is_(True))
        elif filters.user_type == IdentityType.EXTERNAL:
            conditions.append(UsersEntity.is_internal.is_(False))
        if filters.mentorship_role is not None:
            conditions.append(cls._holds_mentorship_role(filters.mentorship_role))
        if restrict_user_ids is not None:
            conditions.append(
                UsersEntity.user_id.in_(restrict_user_ids)
                if restrict_user_ids
                else false()
            )
        if filters.course_id is not None and filters.course_status:
            holds = cls._holds_course(filters.course_id)
            conditions.append(holds if filters.course_status == "assigned" else ~holds)
        return conditions

    @staticmethod
    def _course_columns(course_id: int | None) -> list:
        """The three columns that depend on which course is in scope.

        With a course selected the page shows that course's status; with none
        selected it shows how much the person holds overall. Only the columns
        the page can display are computed, so the other side costs nothing.

        Args:
            course_id (int | None): The course in scope, or None for all.

        Returns:
            list: Labelled columns for the page query.
        """
        if course_id is not None:
            course_status = (
                select(TrainingEntity.status)
                .where(
                    TrainingEntity.user_id == UsersEntity.user_id,
                    TrainingEntity.course_id == course_id,
                )
                .limit(1)
                .scalar_subquery()
            )
            return [
                course_status.label("course_status"),
                null().label("assigned_course_count"),
                null().label("done_course_count"),
            ]

        assigned_count = (
            select(func.count())
            .select_from(TrainingEntity)
            .where(TrainingEntity.user_id == UsersEntity.user_id)
            .scalar_subquery()
        )
        done_count = (
            select(func.count())
            .select_from(TrainingEntity)
            .where(
                TrainingEntity.user_id == UsersEntity.user_id,
                TrainingEntity.status == TrainingStatus.DONE,
            )
            .scalar_subquery()
        )
        return [
            null().label("course_status"),
            assigned_count.label("assigned_course_count"),
            done_count.label("done_course_count"),
        ]

    @classmethod
    def _page_stmt(cls, conditions: list, course_id: int | None) -> Select:
        """The page query for a set of conditions.

        Args:
            conditions (list): Conditions to AND together.
            course_id (int | None): The course in scope, or None for all.

        Returns:
            Select: The unpaginated row query, ordered by user_id.
        """
        return (
            select(
                UsersEntity.user_id.label("user_id"),
                UsersEntity.first_name.label("first_name"),
                UsersEntity.last_name.label("last_name"),
                UsersEntity.preferred_name.label("preferred_name"),
                UsersEntity.is_internal.label("is_internal"),
                *cls._course_columns(course_id),
            )
            .where(*conditions)
            .order_by(UsersEntity.user_id)
        )

    async def count_audience(
        self,
        session: AsyncSession,
        filters: TrainingAudienceFilterDto,
        *,
        restrict_user_ids: list[int] | None = None,
    ) -> int:
        """How many people match, without reading a page.

        Args:
            session (AsyncSession): The active async database session.
            filters (TrainingAudienceFilterDto): The requested filters.

        Returns:
            int: The number of matching people.
        """
        total = await session.scalar(
            select(func.count())
            .select_from(UsersEntity)
            .where(*self._conditions(filters, restrict_user_ids))
        )
        return int(total or 0)

    async def list_audience_ids(
        self,
        session: AsyncSession,
        filters: TrainingAudienceFilterDto,
        *,
        restrict_user_ids: list[int] | None = None,
    ) -> list[int]:
        """Every matching user_id, in the order the pages walk them.

        Unpaginated on purpose: this backs selecting a whole result set, which
        submits ids rather than filters so the number on screen is the number
        assigned. The caller owns the size limit.

        Args:
            session (AsyncSession): The active async database session.
            filters (TrainingAudienceFilterDto): The requested filters.

        Returns:
            list[int]: Matching user_ids.
        """
        result = await session.execute(
            select(UsersEntity.user_id)
            .where(*self._conditions(filters, restrict_user_ids))
            .order_by(UsersEntity.user_id)
        )
        return list(result.scalars().all())

    async def search_audience(
        self,
        session: AsyncSession,
        filters: TrainingAudienceFilterDto,
        *,
        restrict_user_ids: list[int] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Row], int]:
        """One page of matching people, and how many match in total.

        Args:
            session (AsyncSession): The active async database session.
            filters (TrainingAudienceFilterDto): The requested filters.
            restrict_user_ids (list[int] | None): Cross-store restriction; an
                empty list matches nobody.
            limit (int): Max rows to return.
            offset (int): Rows to skip.

        Returns:
            tuple[list[Row], int]: (page rows, total matches across pages).
        """
        conditions = self._conditions(filters, restrict_user_ids)
        total = await session.scalar(
            select(func.count()).select_from(UsersEntity).where(*conditions)
        )
        result = await session.execute(
            self._page_stmt(conditions, filters.course_id).limit(limit).offset(offset)
        )
        return list(result.all()), int(total or 0)
