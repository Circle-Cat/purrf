from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.entity.mentorship_round_participants_entity import (
    MentorshipRoundParticipantsEntity,
)
from backend.entity.mentorship_meeting_entity import MentorshipMeetingEntity
from backend.entity.mentorship_pairs_entity import MentorshipPairsEntity
from backend.entity.users_entity import UsersEntity
from backend.entity.experience_entity import ExperienceEntity
from backend.entity.preference_entity import PreferenceEntity
from backend.entity.user_emails_entity import UserEmailsEntity
from backend.entity.application_entity import ApplicationEntity
from backend.entity.job_entity import JobEntity
from backend.entity.training_entity import TrainingEntity
from backend.common.mentorship_enums import (
    MENTORSHIP_ONBOARDING_CATEGORIES,
    ParticipantRole,
    TrainingCategory,
    TrainingStatus,
)
from backend.common.recruiting_enums import ApplicationStage, JobKind
from backend.dto.participant_search_row_dto import (
    ParticipantSearchPairRow,
    ParticipantSearchRow,
    PersonSearchRow,
)
from backend.dto.participant_search_filter_dto import (
    ParticipantSearchFilterDto,
    UnregisteredFilterDto,
)
from sqlalchemy import (
    Float,
    and_,
    cast,
    exists,
    false,
    func,
    not_,
    or_,
    select,
    tuple_,
)
from sqlalchemy.ext.asyncio import AsyncSession

_INT32_MAX = 2**31 - 1


class MentorshipRoundParticipantsRepository:
    """
    Repository for handling database operations related to MentorshipRoundParticipantsEntity.
    """

    async def get_by_user_id_and_round_id(
        self, session: AsyncSession, user_id: int, round_id: int
    ) -> MentorshipRoundParticipantsEntity | None:
        """
        Retrieve a mentorship round participant by user_id and round_id.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): User id.
            round_id (int): Mentorship round id.

        Returns:
            MentorshipRoundParticipantsEntity | None: The matching participant or None.
        """
        result = await session.execute(
            select(MentorshipRoundParticipantsEntity).where(
                and_(
                    MentorshipRoundParticipantsEntity.user_id == user_id,
                    MentorshipRoundParticipantsEntity.round_id == round_id,
                )
            )
        )

        return result.scalars().one_or_none()

    async def get_recent_participant_by_user_id(
        self, session: AsyncSession, user_id: int
    ) -> MentorshipRoundParticipantsEntity | None:
        """
        Retrieve the most recent mentorship round participant for a user,
        ordered by the round's meetings_completion_deadline_at descending.

        Rounds without meetings_completion_deadline_at are skipped because
        their timeline is not finalized.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): User id.

        Returns:
            MentorshipRoundParticipantsEntity | None: The matching participant or None.
        """
        result = await session.execute(
            select(MentorshipRoundParticipantsEntity)
            .join(
                MentorshipRoundEntity,
                MentorshipRoundEntity.round_id
                == MentorshipRoundParticipantsEntity.round_id,
            )
            .where(
                MentorshipRoundParticipantsEntity.user_id == user_id,
                MentorshipRoundEntity.meetings_completion_deadline_at.isnot(None),
            )
            .order_by(MentorshipRoundEntity.meetings_completion_deadline_at.desc())
            .limit(1)
        )

        return result.scalars().one_or_none()

    async def get_recent_participant_by_user_id_and_role(
        self,
        session: AsyncSession,
        user_id: int,
        participant_role: ParticipantRole,
    ) -> MentorshipRoundParticipantsEntity | None:
        """
        Retrieve the user's most recent mentorship round participant record
        for a specific role, ordered by the round's
        meetings_completion_deadline_at descending.

        Used to pre-fill a new round's registration form with the user's
        carried-over preferences from a prior round in the SAME role, so a
        mentee's form is never seeded from a round they attended as a mentor
        (or vice versa). Rounds without meetings_completion_deadline_at are
        skipped because their timeline is not finalized.

        Args:
            session (AsyncSession): The active async database session.
            user_id (int): User id.
            participant_role (ParticipantRole): The role to match.

        Returns:
            MentorshipRoundParticipantsEntity | None: The matching participant or None.
        """
        result = await session.execute(
            select(MentorshipRoundParticipantsEntity)
            .join(
                MentorshipRoundEntity,
                MentorshipRoundEntity.round_id
                == MentorshipRoundParticipantsEntity.round_id,
            )
            .where(
                MentorshipRoundParticipantsEntity.user_id == user_id,
                MentorshipRoundParticipantsEntity.participant_role == participant_role,
                MentorshipRoundEntity.meetings_completion_deadline_at.isnot(None),
            )
            .order_by(MentorshipRoundEntity.meetings_completion_deadline_at.desc())
            .limit(1)
        )

        return result.scalars().one_or_none()

    async def list_distinct_user_roles(
        self, session: AsyncSession
    ) -> list[tuple[int, ParticipantRole]]:
        """Return every distinct (user_id, participant_role) pair that has
        ever registered for a round.

        Used by the one-time activity-application backfill to find legacy
        participants who registered before the application/round-
        registration gate existed.
        """
        result = await session.execute(
            select(
                MentorshipRoundParticipantsEntity.user_id,
                MentorshipRoundParticipantsEntity.participant_role,
            ).distinct()
        )
        return [tuple(row) for row in result.all()]

    async def count_registered_rounds(
        self, session: AsyncSession, user_ids: list[int], exclude_round_id: int
    ) -> dict[int, int]:
        """Count past rounds each person put their name down for.

        Registration rather than pairing, so a round nobody could be found for
        still counts: the person went through the process, and reading their
        pairs instead would report that round as if they had never shown up.

        Every ``approval_status`` counts, ``rejected`` included. That value
        carries two meanings at once -- not accepted, and left partway -- and
        the second of those is participation.

        Args:
            session (AsyncSession): The active async database session.
            user_ids (list[int]): People to count for.
            exclude_round_id (int): Round to leave out, being the one now
                matched, which everyone in the payload is registered for.

        Returns:
            dict[int, int]: user_id -> rounds registered. People with no past
                registration are absent.
        """
        if not user_ids:
            return {}

        # One row per person per round, by the table's own unique constraint.
        result = await session.execute(
            select(
                MentorshipRoundParticipantsEntity.user_id,
                func.count(MentorshipRoundParticipantsEntity.round_id),
            )
            .where(
                MentorshipRoundParticipantsEntity.user_id.in_(user_ids),
                MentorshipRoundParticipantsEntity.round_id != exclude_round_id,
            )
            .group_by(MentorshipRoundParticipantsEntity.user_id)
        )
        return {user_id: rounds for user_id, rounds in result.all()}

    async def get_average_program_rating_by_round_and_role(
        self,
        session: AsyncSession,
        round_id: int,
        role: ParticipantRole,
    ) -> float:
        """
        Compute the average program_rating for all participants in a round with a specific role.

        Args:
            session (AsyncSession): The active async database session.
            round_id (int): Mentorship round id.
            role (ParticipantRole): The participant role to filter by.

        Returns:
            float: The average program_rating.
        """
        result = await session.execute(
            select(
                func.avg(
                    cast(
                        MentorshipRoundParticipantsEntity.program_feedback[
                            "program_rating"
                        ].astext,
                        Float,
                    )
                )
            ).where(
                and_(
                    MentorshipRoundParticipantsEntity.round_id == round_id,
                    MentorshipRoundParticipantsEntity.participant_role == role,
                    MentorshipRoundParticipantsEntity.program_feedback[
                        "program_rating"
                    ].astext.isnot(None),
                )
            )
        )
        return result.scalar_one_or_none()

    def _feedback_owed_condition(self):
        """
        Who a round's feedback is asked of: anyone paired in that round, the
        pair still going or ended.

        Leaving part way or being blocked does not take someone off the list:
        submitting is gated only on the feedback window, so what they sent
        before leaving is still theirs to have sent.
        """
        return exists().where(
            MentorshipPairsEntity.round_id
            == MentorshipRoundParticipantsEntity.round_id,
            or_(
                MentorshipPairsEntity.mentor_id
                == MentorshipRoundParticipantsEntity.user_id,
                MentorshipPairsEntity.mentee_id
                == MentorshipRoundParticipantsEntity.user_id,
            ),
        )

    def _feedback_sent_condition(self):
        """
        Feedback counts as sent when ``program_feedback`` holds an object,
        the same test the participant's own read uses for ``has_submitted``.
        """
        return (
            func.jsonb_typeof(MentorshipRoundParticipantsEntity.program_feedback)
            == "object"
        )

    async def get_feedback_counts_by_round(
        self, session: AsyncSession
    ) -> dict[int, dict]:
        """
        Count, per round, the people feedback is asked of and how many of them
        have sent it.

        Args:
            session (AsyncSession): The active async database session.

        Returns:
            dict[int, dict]: Mapping of round_id to {"owed": int, "sent": int}.
                Rounds nobody owes feedback for are absent.
        """
        result = await session.execute(
            select(
                MentorshipRoundParticipantsEntity.round_id,
                func.count().label("owed"),
                func.count().filter(self._feedback_sent_condition()).label("sent"),
            )
            .where(self._feedback_owed_condition())
            .group_by(MentorshipRoundParticipantsEntity.round_id)
        )
        return {
            row.round_id: {"owed": row.owed, "sent": row.sent} for row in result.all()
        }

    async def get_feedback_owed_in_round(
        self, session: AsyncSession, round_id: int
    ) -> list[tuple[MentorshipRoundParticipantsEntity, UsersEntity]]:
        """
        The participants a round's feedback is asked of, with their users.

        Args:
            session (AsyncSession): The active async database session.
            round_id (int): Mentorship round id.

        Returns:
            list[tuple[MentorshipRoundParticipantsEntity, UsersEntity]]: One
                pair per participant, ordered by user id.
        """
        result = await session.execute(
            select(MentorshipRoundParticipantsEntity, UsersEntity)
            .join(
                UsersEntity,
                UsersEntity.user_id == MentorshipRoundParticipantsEntity.user_id,
            )
            .where(
                MentorshipRoundParticipantsEntity.round_id == round_id,
                self._feedback_owed_condition(),
            )
            .order_by(MentorshipRoundParticipantsEntity.user_id)
        )
        return [(row[0], row[1]) for row in result.all()]

    def _build_mentorship_eligibility_gate(self):
        """
        Builds the base filter for the admin participant search.

        A user is considered a mentorship user if they meet at least one condition:
        1. Has a hired application for a mentor/mentee activity in the recruiting system.
        2. Has a mentor/mentee onboarding training record, not other categories like
           residency onboarding or corporate culture course.

        Returns:
            ColumnElement[bool]: A correlated EXISTS-OR-EXISTS expression.
        """
        has_hired_activity_application = (
            select(ApplicationEntity.application_id)
            .join(JobEntity, ApplicationEntity.job_id == JobEntity.job_id)
            .where(
                ApplicationEntity.user_id == UsersEntity.user_id,
                ApplicationEntity.stage == ApplicationStage.HIRED,
                JobEntity.kind == JobKind.ACTIVITY,
                JobEntity.mentorship_role.in_([
                    ParticipantRole.MENTOR,
                    ParticipantRole.MENTEE,
                ]),
            )
            .exists()
        )
        has_mentorship_onboarding_training = (
            select(TrainingEntity.training_id)
            .where(
                TrainingEntity.user_id == UsersEntity.user_id,
                TrainingEntity.category.in_(MENTORSHIP_ONBOARDING_CATEGORIES),
            )
            .exists()
        )
        return or_(has_hired_activity_application, has_mentorship_onboarding_training)

    def _build_onboarding_completed_condition(self, is_completed: bool):
        """
        Correlated condition for whether the row's own participant_role has
        completed mentor/mentee onboarding training.

        - MENTOR: mentor onboarding training status is DONE.
        - MENTEE: mentee onboarding training status is DONE.
        - No role (non-participant): either category's status is DONE.

        is_completed=False negates this same condition rather than using a
        separate one.

        Returns:
            ColumnElement[bool]: A correlated EXISTS-based expression.
        """
        mentor_done = (
            select(TrainingEntity.training_id)
            .where(
                TrainingEntity.user_id == UsersEntity.user_id,
                TrainingEntity.category
                == TrainingCategory.MENTORSHIP_MENTOR_ONBOARDING,
                TrainingEntity.status == TrainingStatus.DONE,
            )
            .exists()
        )
        mentee_done = (
            select(TrainingEntity.training_id)
            .where(
                TrainingEntity.user_id == UsersEntity.user_id,
                TrainingEntity.category
                == TrainingCategory.MENTORSHIP_MENTEE_ONBOARDING,
                TrainingEntity.status == TrainingStatus.DONE,
            )
            .exists()
        )

        completed = or_(
            and_(
                MentorshipRoundParticipantsEntity.participant_role
                == ParticipantRole.MENTOR,
                mentor_done,
            ),
            and_(
                MentorshipRoundParticipantsEntity.participant_role
                == ParticipantRole.MENTEE,
                mentee_done,
            ),
            and_(
                MentorshipRoundParticipantsEntity.participant_role.is_(None),
                or_(mentor_done, mentee_done),
            ),
        )

        return completed if is_completed else not_(completed)

    def _apply_person_filters(self, stmt, filters):
        """
        Narrow a statement over UsersEntity by who the person is: exact user
        ID, name or email, account state, and internal or external. Shared by
        the participant search and the not-registered list.

        Args:
            stmt (Select): A statement selecting from UsersEntity.
            filters: Any DTO carrying ``user_id``, ``q``, ``account_status``
                and ``internal``.

        Returns:
            Select: The statement with those conditions applied.
        """
        if filters.user_id is not None:
            # Postgres rejects an int4 literal outside its range, so an ID no
            # row can hold matches nothing instead of failing the query.
            if not 1 <= filters.user_id <= _INT32_MAX:
                stmt = stmt.where(false())
            else:
                stmt = stmt.where(UsersEntity.user_id == filters.user_id)

        if filters.q:
            pattern = f"%{filters.q}%"
            stmt = stmt.where(
                or_(
                    UsersEntity.first_name.ilike(pattern),
                    UsersEntity.last_name.ilike(pattern),
                    UsersEntity.preferred_name.ilike(pattern),
                    select(UserEmailsEntity.email_id)
                    .where(
                        UserEmailsEntity.user_id == UsersEntity.user_id,
                        UserEmailsEntity.email.ilike(pattern),
                    )
                    .exists(),
                )
            )

        if filters.account_status == "active":
            stmt = stmt.where(
                UsersEntity.is_active.is_(True), UsersEntity.is_blocked.is_(False)
            )
        elif filters.account_status == "blocked":
            stmt = stmt.where(UsersEntity.is_blocked.is_(True))
        elif filters.account_status == "deactivated":
            stmt = stmt.where(UsersEntity.is_active.is_(False))

        if filters.internal == "internal":
            stmt = stmt.where(UsersEntity.is_internal.is_(True))
        elif filters.internal == "external":
            stmt = stmt.where(UsersEntity.is_internal.is_(False))

        return stmt

    def _build_admin_search_stmt(self, filters):
        """
        Build the base SELECT statement for the admin participant search.

        Applies all filter conditions from the provided filter DTO.
        ORDER BY, LIMIT, and OFFSET are intentionally excluded so the
        same statement can be reused for both result queries and
        COUNT(*) subqueries.

        Args:
            filters (ParticipantSearchFilterDto): Filter parameters to apply.

        Returns:
            Select: A SQLAlchemy SELECT statement with all filter conditions applied.
        """
        columns = [
            UsersEntity.user_id.label("user_id"),
            MentorshipRoundParticipantsEntity.round_id.label("round_id"),
            MentorshipRoundParticipantsEntity.participant_role.label(
                "participant_role"
            ),
            MentorshipRoundParticipantsEntity.approval_status.label("approval_status"),
            UsersEntity.is_blocked.label("is_blocked"),
            UsersEntity.is_active.label("is_active"),
            UsersEntity.is_internal.label("is_internal"),
        ]

        stmt = (
            select(*columns)
            .select_from(UsersEntity)
            .join(
                MentorshipRoundParticipantsEntity,
                MentorshipRoundParticipantsEntity.user_id == UsersEntity.user_id,
            )
            .where(self._build_mentorship_eligibility_gate())
        )

        stmt = self._apply_person_filters(stmt, filters)

        if filters.round_id is not None:
            stmt = stmt.where(
                MentorshipRoundParticipantsEntity.round_id == filters.round_id
            )

        if filters.participant_role is not None:
            stmt = stmt.where(
                MentorshipRoundParticipantsEntity.participant_role
                == filters.participant_role
            )

        if filters.approval_status is not None:
            stmt = stmt.where(
                MentorshipRoundParticipantsEntity.approval_status
                == filters.approval_status
            )

        if filters.onboarding_status is not None:
            stmt = stmt.where(
                self._build_onboarding_completed_condition(
                    is_completed=filters.onboarding_status == "completed"
                )
            )

        return stmt

    _SORT_WHITELIST: dict[str, object] = {
        "user_id": UsersEntity.user_id,
    }

    def _build_default_order(self) -> list:
        """
        Return the shared deterministic default ordering for the admin
        participant search: last_name, first_name, round_id, user_id — all
        ascending, nulls last.
        """
        return [
            func.lower(UsersEntity.last_name).asc().nulls_last(),
            func.lower(UsersEntity.first_name).asc().nulls_last(),
            MentorshipRoundParticipantsEntity.round_id.asc().nulls_last(),
            UsersEntity.user_id.asc(),
        ]

    async def search_participants_for_admin(
        self,
        session: AsyncSession,
        filters: ParticipantSearchFilterDto,
        limit: int,
        offset: int,
        sort_by: str | None = None,
        order: str = "asc",
    ) -> tuple[list[ParticipantSearchRow], int]:
        """
        Run the admin participant search and return paginated results.

        Rows are one per participant, keyed by (user_id, round_id); a user
        with no participant row is not listed. Each row
        carries every pair the user is in for that round, ordered by pair_id.
        The same base query is reused for both the COUNT(*) query and the
        paginated data query to ensure consistent filtering.

        Args:
            session (AsyncSession): Active database session.
            filters (ParticipantSearchFilterDto): Filter parameters.
            limit (int): Maximum number of rows to return.
            offset (int): Number of rows to skip.
            sort_by (str | None): Column to sort by (whitelisted via
                `_SORT_WHITELIST`). Unknown or None values fall back to the
                deterministic last_name/first_name/round_id/user_id order.
            order (str): "asc" (default) or "desc". Only applied when
                `sort_by` resolves to a whitelisted column.

        Returns:
            tuple[list[ParticipantSearchRow], int]:
                Matching participant rows and the total number of matches
                before pagination.
        """
        base_stmt = self._build_admin_search_stmt(filters)

        total = (
            await session.scalar(select(func.count()).select_from(base_stmt.subquery()))
            or 0
        )

        sort_col = self._SORT_WHITELIST.get(sort_by) if sort_by else None
        if sort_col is not None:
            primary_order = sort_col.desc() if order == "desc" else sort_col.asc()
            # Rows are keyed by (user_id, round_id), so round_id breaks ties
            # for deterministic pagination.
            order_clauses = [
                primary_order,
                MentorshipRoundParticipantsEntity.round_id.asc().nulls_last(),
            ]
        else:
            order_clauses = self._build_default_order()

        data_stmt = base_stmt.order_by(*order_clauses).limit(limit).offset(offset)
        result = await session.execute(data_stmt)
        rows = [
            ParticipantSearchRow(
                user_id=row.user_id,
                round_id=row.round_id,
                participant_role=row.participant_role,
                approval_status=row.approval_status,
                is_blocked=row.is_blocked,
                is_deactivated=not row.is_active,
                is_internal=row.is_internal,
            )
            for row in result.all()
        ]
        await self._attach_round_pairs(session, rows)
        return rows, int(total)

    def _admitted_as(self, roles: list[ParticipantRole]):
        """
        Correlated EXISTS for a person hired into an activity posting for
        any of ``roles``.

        Args:
            roles (list[ParticipantRole]): The mentorship roles to look for.

        Returns:
            ColumnElement[bool]: A correlated EXISTS on UsersEntity.
        """
        return (
            select(ApplicationEntity.application_id)
            .join(JobEntity, ApplicationEntity.job_id == JobEntity.job_id)
            .where(
                ApplicationEntity.user_id == UsersEntity.user_id,
                ApplicationEntity.stage == ApplicationStage.HIRED,
                JobEntity.kind == JobKind.ACTIVITY,
                JobEntity.mentorship_role.in_(roles),
            )
            .exists()
        )

    async def search_unregistered_for_admin(
        self,
        session: AsyncSession,
        round_id: int,
        filters: UnregisteredFilterDto,
        limit: int,
        offset: int,
        order: str = "asc",
    ) -> tuple[list[PersonSearchRow], int]:
        """
        People admitted as a mentor or mentee who have not registered for a
        round, one row each, by user ID.

        Admission is a HIRED application to an activity posting carrying a
        mentorship role. Training and past rounds play no part: the
        historical members are backfilled with admissions. Blocked and
        deactivated people are listed; the account filter narrows them.

        Args:
            session (AsyncSession): Active database session.
            round_id (int): The round they have not registered for.
            filters (UnregisteredFilterDto): Person filters, plus
                ``admitted_role`` to keep only those admitted as that role.
            limit (int): Maximum number of rows to return.
            offset (int): Number of rows to skip.
            order (str): "asc" (default) or "desc" by user ID.

        Returns:
            tuple[list[PersonSearchRow], int]: The page of rows and the
                total before pagination.
        """
        roles = (
            [filters.admitted_role]
            if filters.admitted_role is not None
            else [ParticipantRole.MENTOR, ParticipantRole.MENTEE]
        )
        registered = (
            select(MentorshipRoundParticipantsEntity.participant_id)
            .where(
                MentorshipRoundParticipantsEntity.user_id == UsersEntity.user_id,
                MentorshipRoundParticipantsEntity.round_id == round_id,
            )
            .exists()
        )
        stmt = select(
            UsersEntity.user_id,
            UsersEntity.is_blocked,
            UsersEntity.is_active,
            UsersEntity.is_internal,
        ).where(self._admitted_as(roles), not_(registered))
        stmt = self._apply_person_filters(stmt, filters)

        total = (
            await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        )
        by_id = (
            UsersEntity.user_id.desc() if order == "desc" else UsersEntity.user_id.asc()
        )
        result = await session.execute(stmt.order_by(by_id).limit(limit).offset(offset))
        rows = [
            PersonSearchRow(
                user_id=row.user_id,
                is_blocked=row.is_blocked,
                is_deactivated=not row.is_active,
                is_internal=row.is_internal,
            )
            for row in result.all()
        ]
        return rows, int(total)

    async def list_registered_rounds_by_user_ids(
        self, session: AsyncSession, user_ids: list[int]
    ) -> dict[int, list[MentorshipRoundEntity]]:
        """
        Every round each person has a participant row in, whatever its
        approval status, latest first.

        Latest is by ``meetings_completion_deadline_at`` -- round IDs do not
        run in time order -- with rounds lacking one last and round_id
        breaking ties.

        Args:
            session (AsyncSession): Active database session.
            user_ids (list[int]): People to look up.

        Returns:
            dict[int, list[MentorshipRoundEntity]]: user_id -> rounds. People
                with no registration are absent. Empty for empty input,
                without touching the database.
        """
        if not user_ids:
            return {}
        result = await session.execute(
            select(MentorshipRoundParticipantsEntity.user_id, MentorshipRoundEntity)
            .join(
                MentorshipRoundEntity,
                MentorshipRoundEntity.round_id
                == MentorshipRoundParticipantsEntity.round_id,
            )
            .where(MentorshipRoundParticipantsEntity.user_id.in_(user_ids))
            .order_by(
                MentorshipRoundEntity.meetings_completion_deadline_at.desc().nulls_last(),
                MentorshipRoundEntity.round_id.desc(),
            )
        )
        grouped: dict[int, list[MentorshipRoundEntity]] = {}
        for user_id, round_entity in result.all():
            grouped.setdefault(user_id, []).append(round_entity)
        return grouped

    async def _attach_round_pairs(
        self, session: AsyncSession, rows: list[ParticipantSearchRow]
    ) -> None:
        """
        Load, in one query, every pair each row's user is in for the row's
        round, and set it on the row's `pairs`, ordered by pair_id.

        Args:
            session (AsyncSession): Active database session.
            rows (list[ParticipantSearchRow]): One page of search rows. Rows
                without a round get no pairs.
        """
        keys = {(row.user_id, row.round_id) for row in rows if row.round_id}
        if not keys:
            return

        key_list = list(keys)
        # Counted from the meeting rows rather than read off
        # mentorship_pairs.completed_count, which is on its way out
        # (PUR-608). LEGACY rows are included on purpose: historical rounds
        # have nothing else, so filtering them would report 0 for every
        # pre-Purrf pairing. A pair with no meetings counts 0; someone never
        # paired has no pair entry at all, which is how "never paired" stays
        # distinct from "paired, met nobody".
        completed_count = (
            select(func.count())
            .select_from(MentorshipMeetingEntity)
            .where(
                MentorshipMeetingEntity.pair_id == MentorshipPairsEntity.pair_id,
                MentorshipMeetingEntity.is_completed.is_(True),
            )
            .scalar_subquery()
        )
        result = await session.execute(
            select(
                MentorshipPairsEntity.pair_id,
                MentorshipPairsEntity.round_id,
                MentorshipPairsEntity.mentor_id,
                MentorshipPairsEntity.mentee_id,
                MentorshipPairsEntity.status,
                completed_count.label("completed_count"),
            )
            .where(
                or_(
                    tuple_(
                        MentorshipPairsEntity.mentor_id,
                        MentorshipPairsEntity.round_id,
                    ).in_(key_list),
                    tuple_(
                        MentorshipPairsEntity.mentee_id,
                        MentorshipPairsEntity.round_id,
                    ).in_(key_list),
                )
            )
            .order_by(MentorshipPairsEntity.pair_id)
        )

        pairs_by_key: dict[tuple[int, int], list[ParticipantSearchPairRow]] = {}
        for pair in result.all():
            pair_row = ParticipantSearchPairRow(
                pair_id=pair.pair_id,
                mentor_id=pair.mentor_id,
                mentee_id=pair.mentee_id,
                pair_status=pair.status,
                completed_count=pair.completed_count,
            )
            for user_id in (pair.mentor_id, pair.mentee_id):
                key = (user_id, pair.round_id)
                if key in keys:
                    pairs_by_key.setdefault(key, []).append(pair_row)

        for row in rows:
            row.pairs = pairs_by_key.get((row.user_id, row.round_id), [])

    async def upsert_participant(
        self, session: AsyncSession, entity: MentorshipRoundParticipantsEntity
    ) -> MentorshipRoundParticipantsEntity:
        """
        Inserts or updates a MentorshipRoundParticipantsEntity in the database.

        Args:
            session (AsyncSession): Active async database session.
            entity (MentorshipRoundParticipantsEntity): The entity containing
                mentorship round participation data.

        Returns:
            MentorshipRoundParticipantsEntity: The merged entity instance synchronized with the session.
        """
        merged_entity = await session.merge(entity)
        await session.flush()

        return merged_entity

    async def list_for_matching(
        self, session: AsyncSession, round_id: int, user_ids: list[int]
    ) -> list[tuple]:
        """Retrieve the rows a matching payload is built from, for chosen participants.

        No eligibility or account-state filtering: the caller names exactly who
        takes part, and deciding who is allowed to belongs to whoever assembles
        that list.

        Args:
            session (AsyncSession): The active async database session.
            round_id (int): Mentorship round id.
            user_ids (list[int]): Users to include.

        Returns:
            list[tuple]: (user, participant, experience, preference) per row;
                experience and preference may be None.
        """
        if not user_ids:
            return []

        result = await session.execute(
            select(
                UsersEntity,
                MentorshipRoundParticipantsEntity,
                ExperienceEntity,
                PreferenceEntity,
            )
            .join(
                MentorshipRoundParticipantsEntity,
                and_(
                    UsersEntity.user_id == MentorshipRoundParticipantsEntity.user_id,
                    MentorshipRoundParticipantsEntity.round_id == round_id,
                ),
            )
            .outerjoin(
                ExperienceEntity, UsersEntity.user_id == ExperienceEntity.user_id
            )
            .outerjoin(
                PreferenceEntity, UsersEntity.user_id == PreferenceEntity.user_id
            )
            .where(UsersEntity.user_id.in_(user_ids))
        )
        return list(result.all())
