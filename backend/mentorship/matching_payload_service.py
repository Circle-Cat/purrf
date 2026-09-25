"""Assemble the matching payload for a round from a chosen list of participants.

Translation only. Nothing is written, and nobody is filtered out: the caller
names exactly who takes part, and deciding who is allowed to is a separate
question that belongs with whoever assembles that list.
"""

import secrets
from collections import Counter
from datetime import datetime, timezone
from typing import NamedTuple

from backend.common.mentorship_enums import ParticipantRole
from backend.common.mentorship_survey_codes import (
    CAREER_TRANSITION_MAP,
    DEVELOPMENT_REGION_MAP,
    EXTERNAL_MENTORING_EXP_MAP,
    JOB_MARKET_REGION_MAP,
    MENTEE_STAGE_MAP,
    TRANSITION_TYPE_MAP,
    URGENCY_MAP,
    VOCABULARIES,
    mapped_code_or_none,
    other_text_or_none,
)
from backend.mentorship.matching_contract import (
    INDUSTRY_KEYS,
    SKILL_KEYS,
    EducationRecord,
    MatchingMeta,
    PersonRecord,
    WorkHistoryRecord,
)

# Dates arrive as strings in a JSONB column, where 1970-01-01 stands in for
# "unknown". The contract says absent instead.
_PLACEHOLDER_DATE_PREFIX = "1970-"


class MatchingInput(NamedTuple):
    """The three things one run needs written, in the order they are written.

    Not a contract type: the envelope and the two groups land in three separate
    Redis keys and never travel together as one document. Named rather than a
    plain tuple because the two lists have the same type, and swapping them
    would produce a run that matches mentors against mentors.
    """

    meta: MatchingMeta
    mentors: list[PersonRecord]
    mentees: list[PersonRecord]


def new_run_id(round_id: int) -> str:
    """Build a run id that a person can recognise in a storage browser."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"r{round_id}-{stamp}-{secrets.token_hex(3)}"


def _date_or_none(value) -> str | None:
    if not isinstance(value, str) or value.startswith(_PLACEHOLDER_DATE_PREFIX):
        return None
    return value[:10] or None


def _display_name(user) -> str:
    """Preferred name when there is one, otherwise the legal name."""
    preferred = (user.preferred_name or "").strip()
    if preferred:
        return preferred
    return f"{(user.first_name or '').strip()} {(user.last_name or '').strip()}".strip()


def _education(records) -> list[EducationRecord]:
    return [
        EducationRecord(
            degree=record.get("degree") or "",
            school=record.get("school") or "",
            field_of_study=record.get("field_of_study") or "",
            start_date=_date_or_none(record.get("start_date")),
            end_date=_date_or_none(record.get("end_date")),
        )
        for record in records or []
    ]


def _work_history(records) -> list[WorkHistoryRecord]:
    return [
        WorkHistoryRecord(
            title=record.get("title") or "",
            # Stored under the longer name the profile form uses.
            company=record.get("company_or_organization") or "",
            start_date=_date_or_none(record.get("start_date")),
            end_date=_date_or_none(record.get("end_date")),
            is_current_job=bool(record.get("is_current_job", False)),
        )
        for record in records or []
    ]


class MatchingPayloadService:
    """Builds the payload a matching run reads."""

    def __init__(
        self,
        mentorship_round_participants_repository,
        mentorship_pairs_repository,
        logger,
    ):
        """
        Args:
            mentorship_round_participants_repository: Participant row access.
            mentorship_pairs_repository: Past-pair counts for mentors.
            logger: Injected logger.
        """
        self.mentorship_round_participants_repository = (
            mentorship_round_participants_repository
        )
        self.mentorship_pairs_repository = mentorship_pairs_repository
        self.logger = logger

    async def build_matching_payload(
        self,
        session,
        round_id: int,
        participant_ids: list[int],
        *,
        run_id: str | None = None,
        triggered_by_user_id: str | None = None,
    ) -> MatchingInput:
        """Translate chosen participants of a round into a matching payload.

        Args:
            session (AsyncSession): The active async database session.
            round_id (int): Round being matched.
            participant_ids (list[int]): Users to include. Every one of them has
                to be registered for this round.
            run_id (str | None): Run identifier; generated when absent.
            triggered_by_user_id (str | None): Who asked for this run. Carried
                so the completion notice has somewhere to go; nothing else
                outlives the run.

        Returns:
            MatchingInput: Validated envelope and both groups, ready to write.

        Raises:
            ValueError: A requested user is not a participant of this round,
                a requested mentor already holds as many active pairs in it as
                they take, a requested mentee already has an active pair in it,
                or the selection has no mentor or no mentee.
        """
        requested = list(dict.fromkeys(participant_ids))
        rows = await self.mentorship_round_participants_repository.list_for_matching(
            session, round_id, requested
        )

        found = {user.user_id for user, _, _, _ in rows}
        missing = [user_id for user_id in requested if user_id not in found]
        if missing:
            raise ValueError(
                f"Users {missing} are not registered for round {round_id}."
            )

        user_ids = [user.user_id for user, _, _, _ in rows]
        registered = (
            await self.mentorship_round_participants_repository.count_registered_rounds(
                session, user_ids, round_id
            )
        )
        completed = await self.mentorship_pairs_repository.count_completed_rounds(
            session, user_ids, round_id
        )
        round_counts = {
            user_id: self._round_counts(
                user_id, registered.get(user_id, 0), completed.get(user_id, 0)
            )
            for user_id in user_ids
        }

        active_pairs = await self.mentorship_pairs_repository.get_active_pairs_by_round(
            session, round_id
        )
        held = Counter(pair.mentor_id for pair in active_pairs)
        paired_mentees = {pair.mentee_id for pair in active_pairs}

        mentors: list[PersonRecord] = []
        mentees: list[PersonRecord] = []
        full: list[int] = []
        already_paired: list[int] = []
        for user, participant, experience, preference in rows:
            is_mentor = participant.participant_role == ParticipantRole.MENTOR
            open_slots = None
            if not is_mentor and user.user_id in paired_mentees:
                # A mentee takes one mentor, and the matcher has no idea she
                # already has one: sending her would give her a second.
                already_paired.append(user.user_id)
                continue
            if is_mentor:
                cap = (
                    participant.max_partners
                    if participant.max_partners is not None
                    else 1
                )
                open_slots = cap - held[user.user_id]
                if open_slots < 1:
                    full.append(user.user_id)
                    continue
            record = self._person(
                user,
                participant,
                experience,
                preference,
                is_mentor=is_mentor,
                round_counts=round_counts[user.user_id],
                open_slots=open_slots,
            )
            (mentors if is_mentor else mentees).append(record)

        if full:
            # Sending them with no room would not keep them out: the matcher
            # reads 0 as 1 and would give each one more mentee.
            raise ValueError(
                f"Mentors {full} already have as many mentees as they take in "
                f"round {round_id}."
            )
        if already_paired:
            raise ValueError(
                f"Mentees {already_paired} already have a mentor in round {round_id}."
            )

        if not mentors or not mentees:
            raise ValueError(
                f"Round {round_id} selection needs both mentors and mentees; "
                f"got {len(mentors)} and {len(mentees)}."
            )

        self.logger.info(
            "[MatchingPayloadService] round=%s mentors=%d mentees=%d",
            round_id,
            len(mentors),
            len(mentees),
        )
        return MatchingInput(
            meta=MatchingMeta(
                run_id=run_id or new_run_id(round_id),
                round_id=round_id,
                generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                triggered_by_user_id=triggered_by_user_id,
                vocabularies=VOCABULARIES,
            ),
            mentors=mentors,
            mentees=mentees,
        )

    def _round_counts(
        self, user_id: int, registered: int, completed: int
    ) -> tuple[int, int]:
        """Reconcile the two round counts so their difference stays meaningful.

        The matcher reads ``participated - completed`` as rounds that were
        paired and then went nowhere, so a negative difference would report a
        gap in our own records as somebody standing people up. It can only
        arise where a historical round left a pair behind without a
        registration row, which is a data gap worth saying out loud.
        """
        if registered < completed:
            self.logger.warning(
                "[MatchingPayloadService] user=%s has %d completed round(s) but "
                "only %d registration(s); reporting %d participated.",
                user_id,
                completed,
                registered,
                completed,
            )
            return completed, completed
        return registered, completed

    def _person(
        self,
        user,
        participant,
        experience,
        preference,
        *,
        is_mentor: bool,
        round_counts: tuple[int, int],
        open_slots: int | None,
    ) -> PersonRecord:
        """Turn one set of rows into a contract record.

        ``open_slots`` is what a mentor can still take in this round, and is
        what travels as ``max_partners``; None for a mentee.
        """
        survey = (preference.profile_survey or {}) if preference else {}
        common = {
            "role": "mentor" if is_mentor else "mentee",
            "user_id": user.user_id,
            "display_name": _display_name(user),
            "timezone": user.timezone or "",
            "goal": participant.goal or "",
            "skills": {
                key: bool(getattr(preference, key, False) if preference else False)
                for key in SKILL_KEYS
            },
            "education": _education(experience.education if experience else None),
            "work_history": _work_history(
                experience.work_history if experience else None
            ),
            "expected_partner_ids": [
                str(i) for i in (participant.expected_partner_user_id or [])
            ],
            "unexpected_partner_ids": [
                str(i) for i in (participant.unexpected_partner_user_id or [])
            ],
            # Both sides carry these. The matcher reads them to avoid pairing two
            # people who have never been through a round, which is a question
            # about the pair, not about either role.
            "mentorship_rounds_participated": round_counts[0],
            "mentorship_rounds_completed": round_counts[1],
        }

        if is_mentor:
            return PersonRecord(
                **common,
                max_partners=open_slots,
                career_transition=mapped_code_or_none(
                    survey.get("career_transition"), CAREER_TRANSITION_MAP
                ),
                career_transition_other=other_text_or_none(
                    survey.get("career_transition"),
                    survey.get("career_transition_other"),
                ),
                development_region=mapped_code_or_none(
                    survey.get("region"), DEVELOPMENT_REGION_MAP
                ),
                development_region_other=other_text_or_none(
                    survey.get("region"), survey.get("region_other")
                ),
                external_mentoring_exp=mapped_code_or_none(
                    survey.get("external_mentoring_exp"), EXTERNAL_MENTORING_EXP_MAP
                ),
            )

        industry = (preference.specific_industry if preference else None) or {}
        return PersonRecord(
            **common,
            specific_industry={
                key: bool(industry.get(key, False)) for key in INDUSTRY_KEYS
            },
            transition_type=mapped_code_or_none(
                survey.get("current_background"), TRANSITION_TYPE_MAP
            ),
            transition_type_other=other_text_or_none(
                survey.get("current_background"), survey.get("current_background_other")
            ),
            mentee_stage=mapped_code_or_none(
                participant.current_stage, MENTEE_STAGE_MAP
            ),
            urgency=mapped_code_or_none(participant.time_urgency, URGENCY_MAP),
            job_market_region=mapped_code_or_none(
                survey.get("target_region"), JOB_MARKET_REGION_MAP
            ),
            job_market_region_other=other_text_or_none(
                survey.get("target_region"), survey.get("target_region_other")
            ),
        )
