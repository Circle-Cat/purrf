from backend.dto.rounds_dto import RoundsDto, TimelineDto
from backend.dto.preference_dto import (
    SpecificIndustryDto,
    SkillsetsDto,
    ProfileSurveyDto,
)
from backend.dto.registration_dto import GlobalPreferencesDto, RoundPreferencesDto
from backend.dto.meeting_dto import MeetingDto, MeetingInfoDto, MeetingTimeDto
from backend.dto.admin_meeting_log_dto import AdminMeetingDto

from backend.entity.mentorship_pairs_entity import MentorshipPairsEntity
from backend.entity.mentorship_meeting_entity import MentorshipMeetingEntity
from backend.entity.preference_entity import PreferenceEntity
from backend.entity.mentorship_round_participants_entity import (
    MentorshipRoundParticipantsEntity,
)
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.common.mentorship_enums import (
    MeetingNoteTag,
    MeetingSource,
    ParticipantRole,
)


class MentorshipMapper:
    """
    Mapper for converting mentorship-related database entities to DTOs.
    """

    def map_to_rounds_dto(
        self,
        rounds: list[MentorshipRoundEntity],
        pair_stats: dict[int, dict] | None = None,
    ) -> list[RoundsDto]:
        """Maps a list of MentorshipRoundEntity objects to a list of RoundsDto objects."""
        pair_stats = pair_stats or {}
        return [
            RoundsDto(
                id=r.round_id,
                name=r.name,
                active_pairs=pair_stats.get(r.round_id, {}).get("active_pairs"),
                matched_participants=pair_stats.get(r.round_id, {}).get(
                    "matched_participants"
                ),
                total_completed_meetings=pair_stats.get(r.round_id, {}).get(
                    "total_completed_meetings"
                ),
                mentee_average_score=r.mentee_average_score,
                mentor_average_score=r.mentor_average_score,
                expectations=r.expectations,
                required_meetings=r.required_meetings,
                timeline=self._map_timeline(r.description) if r.description else None,
            )
            for r in rounds
        ]

    def _map_timeline(self, d: dict) -> TimelineDto:
        """
        Maps a dictionary containing timeline data to a TimelineDto.

        Args:
            d (dict): A dictionary containing timeline-related datetime fields.

        Returns:
            TimelineDto: A TimelineDto populated with the corresponding timeline values.
        """
        return TimelineDto(
            promotion_start_at=d.get("promotion_start_at"),
            mentor_application_deadline_at=d.get("mentor_application_deadline_at"),
            mentee_application_deadline_at=d.get("mentee_application_deadline_at"),
            review_start_at=d.get("review_start_at"),
            acceptance_notification_at=d.get("acceptance_notification_at"),
            training_notification_at=d.get("training_notification_at"),
            training_deadline_at=d.get("training_deadline_at"),
            matching_completed_at=d.get("matching_completed_at"),
            match_notification_at=d.get("match_notification_at"),
            first_meeting_deadline_at=d.get("first_meeting_deadline_at"),
            meeting_log_reminder_at=d.get("meeting_log_reminder_at"),
            meetings_completion_deadline_at=d.get("meetings_completion_deadline_at"),
            feedback_start_at=d.get("feedback_start_at"),
            feedback_deadline_at=d.get("feedback_deadline_at"),
        )

    def map_to_global_preferences_dto(
        self, preference_entity: PreferenceEntity
    ) -> GlobalPreferencesDto:
        """Maps a PreferencesEntity to a GlobalPreferencesDto."""
        industry_data = preference_entity.specific_industry or {}

        profile_survey = (
            ProfileSurveyDto.model_validate(preference_entity.profile_survey)
            if preference_entity.profile_survey
            else None
        )

        return GlobalPreferencesDto(
            specific_industry=SpecificIndustryDto(
                swe=industry_data.get("swe", False),
                uiux=industry_data.get("uiux", False),
                ds=industry_data.get("ds", False),
                pm=industry_data.get("pm", False),
            ),
            skillsets=SkillsetsDto(
                resume_guidance=preference_entity.resume_guidance or False,
                career_path_guidance=preference_entity.career_path_guidance or False,
                experience_sharing=preference_entity.experience_sharing or False,
                industry_trends=preference_entity.industry_trends or False,
                technical_skills=preference_entity.technical_skills or False,
                soft_skills=preference_entity.soft_skills or False,
                networking=preference_entity.networking or False,
                project_management=preference_entity.project_management or False,
            ),
            profile_survey=profile_survey,
        )

    def map_to_round_preference_dto(
        self, participants_entity: MentorshipRoundParticipantsEntity
    ) -> RoundPreferencesDto:
        """Maps a MentorshipRoundParticipantsEntity to a RoundPreferencesDto."""
        return RoundPreferencesDto(
            participant_role=participants_entity.participant_role,
            expected_partner_ids=list(
                participants_entity.expected_partner_user_id or []
            ),
            unexpected_partner_ids=list(
                participants_entity.unexpected_partner_user_id or []
            ),
            max_partners=participants_entity.max_partners
            if participants_entity.max_partners is not None
            else 1,
            goal=participants_entity.goal or "",
            current_stage=participants_entity.current_stage,
            time_urgency=participants_entity.time_urgency,
        )

    def map_to_meeting_dto(
        self,
        round_id: int,
        grouped_pairs: list[tuple[MentorshipPairsEntity, int]],
        meetings_by_pair: dict[int, list[MentorshipMeetingEntity]],
        completed_counts: dict[int, int],
    ) -> MeetingDto:
        """Map (MentorshipPairsEntity, partner_id) tuples to MeetingDto.

        Args:
            round_id (int): The mentorship round ID.
            grouped_pairs (list[tuple[MentorshipPairsEntity, int]]): Each pair
                paired with the partner's user id.
            completed_counts (dict[int, int]): pair_id -> completed meeting
                count, from
                ``MentorshipMeetingRepository.count_completed_by_pairs``. Not
                derived from ``meetings_by_pair``: that mapping excludes
                LEGACY rows, which are all a pre-Purrf pairing has, so
                counting it would report 0 for every historical pair. A pair
                absent from this mapping counts as 0.
            meetings_by_pair (dict[int, list[MentorshipMeetingEntity]]):
                Meeting rows keyed by ``pair_id``, e.g. from
                ``MentorshipMeetingRepository.get_meetings_by_pair`` /
                ``get_meetings_by_pairs``. Required rather than defaulted to
                ``None`` -- there are only two call sites, and a caller that
                forgot this argument would otherwise get a silently empty
                meeting list rather than an error. A pair absent from this
                dict is treated as having no meetings. LEGACY rows are
                filtered out here regardless of whether the caller already
                excluded them -- they carry no times and have nothing to show
                in this list. Order is passed through unchanged -- this
                method does not sort; it trusts whatever order the caller's
                meetings came back in.
        """
        return MeetingDto(
            round_id=round_id,
            meeting_info=[
                MeetingInfoDto(
                    partner_id=partner_id,
                    participant_role=ParticipantRole.MENTEE
                    if partner_id == pair.mentor_id
                    else ParticipantRole.MENTOR,
                    meeting_time_list=[
                        MeetingTimeDto(
                            meeting_id=m.meeting_id,
                            start_datetime=m.start_datetime,
                            end_datetime=m.end_datetime,
                            is_completed=m.is_completed,
                            created_datetime=m.created_datetime,
                        )
                        for m in meetings_by_pair.get(pair.pair_id, [])
                        if m.source != MeetingSource.LEGACY
                    ],
                    completed_meetings_count=completed_counts.get(pair.pair_id, 0),
                )
                for pair, partner_id in grouped_pairs
            ],
        )

    def map_to_meeting_v2_dto(
        self,
        round_id: int,
        grouped_pairs: list[tuple[MentorshipPairsEntity, int]],
        meetings_by_pair: dict[int, list[MentorshipMeetingEntity]],
        completed_counts: dict[int, int],
        include_details: bool = False,
    ) -> MeetingDto:
        """Map (MentorshipPairsEntity, partner_id) tuples to MeetingDto, merging
        both meeting generations.

        Compared with `map_to_meeting_dto`, this method:
            - reads from `meetings_by_pair` rows of BOTH `MeetingSource.MANUAL`
              and `MeetingSource.GOOGLE` -- unlike the v1 mapper, this one must
              NOT filter MANUAL-only; merging both generations is the whole
              point of v2.
            - supports Google Meet-specific fields (e.g., absence/late
              information), gated by `include_details`.

        Args:
            round_id (int): The mentorship round ID.
            grouped_pairs (list[tuple[MentorshipPairsEntity, int]]): Each pair
                paired with the partner's user id.
            completed_counts (dict[int, int]): pair_id -> completed meeting
                count, from
                ``MentorshipMeetingRepository.count_completed_by_pairs``. Not
                derived from ``meetings_by_pair``: that mapping excludes
                LEGACY rows, which are all a pre-Purrf pairing has, so
                counting it would report 0 for every historical pair. A pair
                absent from this mapping counts as 0.
            meetings_by_pair (dict[int, list[MentorshipMeetingEntity]]):
                Meeting rows keyed by `pair_id`, e.g. from
                `MentorshipMeetingRepository.get_meetings_by_pairs`. A pair
                absent from this dict is treated as having no meetings.
            include_details (bool): Whether to populate Google-only
                attendance fields.
        """
        return MeetingDto(
            round_id=round_id,
            meeting_info=[
                MeetingInfoDto(
                    partner_id=partner_id,
                    participant_role=ParticipantRole.MENTEE
                    if partner_id == pair.mentor_id
                    else ParticipantRole.MENTOR,
                    meeting_time_list=self._build_meeting_time_list(
                        meetings_by_pair.get(pair.pair_id, []), include_details
                    ),
                    completed_meetings_count=completed_counts.get(pair.pair_id, 0),
                )
                for pair, partner_id in grouped_pairs
            ],
        )

    def _build_meeting_time_list(
        self,
        meetings: list[MentorshipMeetingEntity],
        include_details: bool,
    ) -> list[MeetingTimeDto]:
        """Build the merged MANUAL+GOOGLE meeting-time list for v2.

        Args:
            meetings (list[MentorshipMeetingEntity]): Rows for one pair. Order
                is passed through unchanged -- the repository already returns
                rows interleaved by `start_datetime` across both sources, and
                this method must trust that rather than concatenating one
                generation after the other. LEGACY rows are filtered out here
                regardless of whether the caller already excluded them (same
                defensive stance as `map_to_meeting_dto`): they carry null
                times, which `MeetingTimeDto` cannot represent.
            include_details (bool): Whether to populate the Google-only
                attendance fields (`has_unknown_absent`, `absent_user_id`,
                `has_unknown_late`, `late_user_ids`, `has_insufficient_duration`).
                These are always null on a MANUAL row regardless of this flag.
                `meet_link` is deliberately NOT among them: that flag gates
                admin-only attendance results, while the Meet link belongs to
                the caller's own meeting -- this endpoint returns only the
                caller's own pairs -- and the UI needs it to offer a join
                entry point. It is null on a MANUAL row for the same reason
                the attendance fields are: no Google event ever backed it.

        Returns:
            list[MeetingTimeDto]: One DTO per non-LEGACY input row, in the
                same order given.
        """
        return [
            MeetingTimeDto(
                meeting_id=m.meeting_id,
                start_datetime=m.start_datetime,
                end_datetime=m.end_datetime,
                is_completed=m.is_completed,
                created_datetime=m.created_datetime,
                meet_link=m.meet_link,
                has_unknown_absent=m.has_unknown_absent if include_details else None,
                absent_user_id=m.absent_user_id if include_details else None,
                has_unknown_late=m.has_unknown_late if include_details else None,
                late_user_ids=m.late_user_ids if include_details else None,
                has_insufficient_duration=m.has_insufficient_duration
                if include_details
                else None,
            )
            for m in meetings
            if m.source != MeetingSource.LEGACY
        ]

    def map_to_admin_meeting_dto(
        self,
        meeting: dict,
        *,
        is_completed: bool,
        note_tags: list[MeetingNoteTag],
    ) -> AdminMeetingDto:
        """Maps a meeting record and resolved fields to an AdminMeetingDto."""
        return AdminMeetingDto(
            meeting_id=meeting["meeting_id"],
            start_datetime=meeting["start_datetime"],
            end_datetime=meeting["end_datetime"],
            is_completed=is_completed,
            note=note_tags,
            create_datetime=meeting["created_datetime"],
        )
