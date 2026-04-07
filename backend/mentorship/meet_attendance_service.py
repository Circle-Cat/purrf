import asyncio
from datetime import datetime, timezone, timedelta
from dateutil.parser import isoparse
from intervaltree import Interval, IntervalTree
from itertools import combinations
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from backend.dto.google_meeting_detail_dto import GoogleMeetingDetailDto
from backend.entity.users_entity import UsersEntity
from backend.entity.mentorship_pairs_entity import MentorshipPairsEntity

# Configuration Constants
LATE_THRESHOLD = timedelta(minutes=5)
# Ignore "noise" records shorter than 60 seconds
MIN_VALID_SESSION_STRICT = 60
# Specific meeting room hardware ID CN-CAN-BAOLI-5-519-Lihua (5) [GVC]
EXCLUDED_GOOGLE_USER_IDS = {"100580340666352382634"}
# Required overlapping duration ratio for a "successful" meeting
MIN_INTERACTION_RATIO = 0.8
ATTENDANCE_WINDOW_DELTA = timedelta(hours=3)
# Top N anonymous participants ranked by total time spent
TOP_ANONYMOUS_USERS = 3


class MeetAttendanceService:
    """
    Service for synchronizing and analyzing Google Meet attendance for mentorship pairs.

    Logic:
        - Prioritizes identified users (by email or Google UID) and falls back to anonymous
          participant data when identity cannot be resolved.
        - Lateness is measured against a fixed anchor at the scheduled start time.
        - Meeting success is defined by the overlapping presence of mentor and mentee
          exceeding the required interaction ratio.
        - Both mentor and mentee can independently be marked as late.
    """

    def __init__(
        self,
        logger,
        google_service,
        mentorship_pairs_repository,
        mentorship_round_repository,
        users_repository,
    ):
        """
        Args:
            logger: Logging instance for error and info tracking.
            google_service: Interface for Google Workspace Meet API.
            mentorship_pairs_repository: Repository for mentorship pair data.
            mentorship_round_repository: Repository for mentorship round data.
            users_repository: Repository for user profile data.
        """
        self.logger = logger
        self.google_service = google_service
        self.mentorship_pairs_repository = mentorship_pairs_repository
        self.mentorship_round_repository = mentorship_round_repository
        self.users_repository = users_repository

    async def sync_attendance(self, session: AsyncSession, lookback_hours: int) -> dict:
        """
        Fetches ended Google Meet conferences within a lookback window and reconciles
        them against scheduled mentorship meetings. Applies a 3-hour proximity filter
        to match actual conferences with their corresponding scheduled slots.

        Args:
            session: SQLAlchemy database session for transactional operations.
            lookback_hours: Number of hours back from now to search for ended conferences.

        Returns:
            A summary dict with the following keys:
                - round_id (int): ID of the processed round.
                - pairs_updated (int): Number of pair records written to the database.
                - meetings_completed (int): Number of meetings marked as successfully completed.
                - meetings_absent (int): Number of meetings where an absence was recorded.
                - meetings_skipped (int): Number of conference records that could not be matched.
            Returns an empty dict if not currently in the meeting window or no conferences were found.
        """
        round_id = await self.mentorship_round_repository.get_running_round_id(session)
        if not round_id:
            self.logger.info(
                "[MeetAttendanceService] sync_attendance: not in meeting window, skipping"
            )
            return {}
        self.logger.debug(
            "[MeetAttendanceService] sync_attendance: round_id=%s, lookback_hours=%s",
            round_id,
            lookback_hours,
        )

        now = datetime.now(timezone.utc)
        # Fetch conferences ending within the lookback window
        conferences = await self.google_service.list_ended_conferences(
            end_time_after=(now - timedelta(hours=lookback_hours)).isoformat(),
            end_time_before=now.isoformat(),
        )
        if not conferences:
            return {}
        self.logger.debug(
            "[MeetAttendanceService] Fetched %d conferences", len(conferences)
        )

        summary = {
            "round_id": round_id,
            "pairs_updated": 0,
            "meetings_completed": 0,
            "meetings_absent": 0,
            "meetings_skipped": 0,
        }
        changed_pairs = {}

        # Load active pairs and build a lookup map based on meeting_code
        pairs = await self.mentorship_pairs_repository.get_active_pairs_by_round(
            session, round_id
        )
        pair_lookup = self._build_pair_lookup(pairs)
        self.logger.debug(
            "[MeetAttendanceService] Pair lookup built: %d entries", len(pair_lookup)
        )
        if not pair_lookup:
            return summary

        # Pre-load user entities to reduce database queries
        active_uids = {
            uid
            for pair, _ in pair_lookup.values()
            for uid in (pair.mentor_id, pair.mentee_id)
        }
        users = await self.users_repository.get_all_by_ids(session, list(active_uids))
        user_by_id = {u.user_id: u for u in users}
        self.logger.debug(
            "[MeetAttendanceService] Loaded %d users for %d active UIDs",
            len(users),
            len(active_uids),
        )

        # Group conference records by space
        space_to_confs = {}
        for c in conferences:
            space_to_confs.setdefault(c.get("space"), []).append(c)
        self.logger.debug(
            "[MeetAttendanceService] Processing %d spaces", len(space_to_confs)
        )

        for space, conf_list in space_to_confs.items():
            try:
                meeting_code = await self.google_service.get_meeting_code_for_space(
                    space
                )
                if meeting_code not in pair_lookup:
                    self.logger.debug(
                        "[MeetAttendanceService] Space %s: meeting_code=%s not in pair_lookup, skipping",
                        space,
                        meeting_code,
                    )
                    summary["meetings_skipped"] += 1
                    continue

                pair, gm_index = pair_lookup[meeting_code]
                self.logger.debug(
                    "[MeetAttendanceService] Space %s: matched pair_id=%s, mentor_id=%s, mentee_id=%s, gm_index=%s",
                    space,
                    pair.pair_id,
                    pair.mentor_id,
                    pair.mentee_id,
                    gm_index,
                )
                mentor = user_by_id.get(pair.mentor_id)
                mentee = user_by_id.get(pair.mentee_id)

                google_meetings = list(pair.meeting_log["google_meetings"])
                gm = google_meetings[gm_index]

                if gm.get("is_completed"):
                    self.logger.debug(
                        "[MeetAttendanceService] Space %s: gm already completed, skipping",
                        space,
                    )
                    continue

                scheduled_start = isoparse(gm["start_datetime"])
                scheduled_end = isoparse(gm["end_datetime"])

                # Define the valid attendance window: 3h before scheduled start to 3h after scheduled end
                window_start = scheduled_start - ATTENDANCE_WINDOW_DELTA
                window_end = scheduled_end + ATTENDANCE_WINDOW_DELTA

                filtered_conf_list = []
                for c in conf_list:
                    c_start = isoparse(c["start_time"])
                    # Only include conference instances that started within the window
                    # (excludes test calls or unrelated early/late instances)
                    if window_start <= c_start <= window_end:
                        filtered_conf_list.append(c)
                    else:
                        self.logger.debug(
                            "[MeetAttendanceService] Space %s: Ignoring instance started at %s (outside 3h window)",
                            space,
                            c_start,
                        )

                if not filtered_conf_list:
                    self.logger.debug(
                        "[MeetAttendanceService] Space %s: No instances found within the 3h affinity window",
                        space,
                    )
                    continue

                # Fetch and resolve identities for the filtered conferences
                raw_by_conf = {}
                for c in filtered_conf_list:
                    raw_by_conf[
                        c["name"]
                    ] = await self.google_service.fetch_participants_for_record(
                        c["name"]
                    )

                identity_map = await self._resolve_identities(
                    raw_by_conf, [mentor, mentee]
                )

                target_secs = max((scheduled_end - scheduled_start).total_seconds(), 60)
                self.logger.debug(
                    "[MeetAttendanceService] Space %s: scheduled=%s to %s, target_secs=%.0f",
                    space,
                    scheduled_start,
                    scheduled_end,
                    target_secs,
                )

                # Map participant logs into Time Interval Trees for overlap calculation
                role_trees, anon_trees = self._build_attendee_interval_trees(
                    filtered_conf_list, raw_by_conf, identity_map, mentor, mentee
                )
                self.logger.debug(
                    "[MeetAttendanceService] Space %s: mentor_intervals=%d, mentee_intervals=%d, anon_keys=%s",
                    space,
                    len(role_trees["mentor"]),
                    len(role_trees["mentee"]),
                    list(anon_trees.keys()),
                )

                # Core attendance logic
                meet_detail = GoogleMeetingDetailDto(**gm)
                result = self._analyze_attendance(
                    role_trees,
                    anon_trees,
                    target_secs,
                    pair.mentor_id,
                    pair.mentee_id,
                    meet_detail,
                )
                self.logger.debug(
                    "[MeetAttendanceService] Space %s: result=%s",
                    space,
                    result.model_dump(),
                )

                # Update the meeting log metadata
                gm.update({
                    "is_completed": result.is_completed,
                    "absent_user_id": result.absent_user_id,
                    "late_user_id": result.late_user_id,
                    "has_unknown_absent": result.has_unknown_absent,
                    "has_unknown_late": result.has_unknown_late,
                    "has_insufficient_duration": result.has_insufficient_duration,
                    "last_sync_at": now.isoformat(),
                })

                if result.is_completed:
                    pair.completed_count = (pair.completed_count or 0) + 1
                    summary["meetings_completed"] += 1
                if result.absent_user_id or result.has_unknown_absent:
                    summary["meetings_absent"] += 1

                google_meetings[gm_index] = gm
                pair.meeting_log = {
                    **pair.meeting_log,
                    "google_meetings": google_meetings,
                }
                flag_modified(pair, "meeting_log")
                changed_pairs[pair.pair_id] = pair
            except Exception as e:
                self.logger.error(
                    "[MeetAttendanceService] Failed to process space %s: %s", space, e
                )
                summary["meetings_skipped"] += 1

        if changed_pairs:
            await self.mentorship_pairs_repository.upsert_pairs_batch(
                session, list(changed_pairs.values())
            )
            self.logger.debug(
                "[MeetAttendanceService] changed_pairs.values(): %s",
                changed_pairs.values(),
            )
            await session.commit()
            summary["pairs_updated"] = len(changed_pairs)

        self.logger.debug("[MeetAttendanceService] Sync complete: %s", summary)
        return summary

    async def _resolve_identities(
        self, raw_by_conf: dict[str, list[dict]], user_entities: list[UsersEntity]
    ) -> dict[str, str | None]:
        """
        Resolves Google user IDs found in participant logs to their primary email addresses.

        Checks the mentor/mentee user objects first (local cache) before falling back
        to bulk Google API lookups for any unresolved UIDs.

        Args:
            raw_by_conf: Mapping of conference resource names to their participant log lists.
            user_entities: List of mentor and mentee user objects used as a local identity cache.

        Returns:
            A dict mapping Google UID strings to lowercase email addresses. If a UID
            cannot be resolved via the API, its value is None.
        """
        all_uids = {
            p.get("signedin_user_id")
            for parts in raw_by_conf.values()
            for p in parts
            if p.get("signedin_user_id")
            and p.get("signedin_user_id") not in EXCLUDED_GOOGLE_USER_IDS
        }
        self.logger.debug(
            "[MeetAttendanceService] _resolve_identities: %d unique signed-in UIDs found",
            len(all_uids),
        )
        if not all_uids:
            return {}

        identity_map = {}
        uids_to_query = []

        # Build local lookup from known Mentor/Mentee entities
        local_uid_map = {
            u.subject_identifier.split("|")[-1]: u.primary_email.lower()
            for u in user_entities
            if u and u.subject_identifier
        }

        for uid in all_uids:
            if uid in local_uid_map:
                identity_map[uid] = local_uid_map[uid]
            else:
                uids_to_query.append(uid)
        self.logger.debug(
            "[MeetAttendanceService] Identity cache: %d resolved locally, %d to query via API",
            len(identity_map),
            len(uids_to_query),
        )

        # Bulk query Google API for unknown IDs
        if uids_to_query:
            api_results = await asyncio.gather(*[
                asyncio.to_thread(self.google_service.get_email_by_google_user_id, uid)
                for uid in uids_to_query
            ])
            for uid, email in zip(uids_to_query, api_results):
                identity_map[uid] = email.lower() if email else None
                self.logger.debug(
                    "[MeetAttendanceService] UID %s -> email=%s", uid, email
                )

        return identity_map

    def _build_attendee_interval_trees(
        self,
        conf_list: list[dict],
        raw_by_conf: dict[str, list[dict]],
        identity_map: dict[str, str | None],
        mentor: UsersEntity | None,
        mentee: UsersEntity | None,
    ) -> tuple[dict[str, IntervalTree], dict[str, IntervalTree]]:
        """
        Converts raw participant session records into merged IntervalTrees grouped by role.

        Applies a three-tier identity matching strategy:
            Tier 1 - Email match against known mentor/mentee addresses (strongest signal).
            Tier 2 - Display-name fuzzy match against name fingerprints (fallback for
                     unsigned-in participants).
            Tier 3 - Unresolved participants stored as anonymous entries keyed by display name.

        Sessions shorter than MIN_VALID_SESSION_STRICT are discarded as noise before
        matching. Overlapping intervals for the same participant are merged into
        continuous blocks.

        Args:
            conf_list: List of conference instance dicts for a single Meet space.
            raw_by_conf: Mapping of conference resource names to raw participant log lists.
            identity_map: Dict mapping Google UIDs to resolved lowercase email addresses.
            mentor: Mentor user ORM object, or None if unavailable.
            mentee: Mentee user ORM object, or None if unavailable.

        Returns:
            A tuple (role_trees, anon_trees):
                - role_trees (dict): Keys "mentor" and "mentee", each mapping to a merged
                  IntervalTree of that participant's presence intervals.
                - anon_trees (dict): Keys are lowercase display names, values are merged
                  IntervalTrees for unidentified participants.
        """
        role_trees = {"mentor": IntervalTree(), "mentee": IntervalTree()}
        anon_trees = {}

        mentor_names = self._get_user_name_fingerprints(mentor)
        mentee_names = self._get_user_name_fingerprints(mentee)
        mentor_emails = self._get_user_emails(mentor)
        mentee_emails = self._get_user_emails(mentee)

        for conf in conf_list:
            conf_end = isoparse(conf["end_time"])
            for p in raw_by_conf.get(conf["name"], []):
                uid = p.get("signedin_user_id")
                if uid in EXCLUDED_GOOGLE_USER_IDS:
                    continue

                start_str = p.get("start_time")
                if not start_str:
                    continue

                start = isoparse(start_str)
                end = isoparse(p["end_time"]) if p.get("end_time") else conf_end

                duration = (end - start).total_seconds()
                # Filter out transient connections/noise
                if duration < MIN_VALID_SESSION_STRICT:
                    clean_name = (
                        (p.get("display_name") or "unknown guest").strip().lower()
                    )
                    self.logger.debug(
                        "[MeetAttendanceService] Skipping short session for %r: %.0fs < %ds",
                        clean_name,
                        duration,
                        MIN_VALID_SESSION_STRICT,
                    )
                    continue

                email = identity_map.get(uid) if uid else None
                clean_name = (p.get("display_name") or "unknown guest").strip().lower()

                # Tier 1: Strong match via Email or Google UID
                if email and email in mentor_emails:
                    self.logger.debug(
                        "[MeetAttendanceService] Tier1 email match: %r -> mentor", email
                    )
                    role_trees["mentor"].add(Interval(start, end))
                elif email and email in mentee_emails:
                    self.logger.debug(
                        "[MeetAttendanceService] Tier1 email match: %r -> mentee", email
                    )
                    role_trees["mentee"].add(Interval(start, end))

                # Tier 2: Fuzzy match via Display Name (Fallback for non-signed-in users)
                elif clean_name in mentor_names:
                    self.logger.info(
                        "[MeetAttendanceService] Matched mentor by name fingerprint: %s",
                        clean_name,
                    )
                    self.logger.debug(
                        "[MeetAttendanceService] Tier2 name match: %r -> mentor, interval=%s to %s",
                        clean_name,
                        start,
                        end,
                    )
                    role_trees["mentor"].add(Interval(start, end))
                elif clean_name in mentee_names:
                    self.logger.info(
                        "[MeetAttendanceService] Matched mentee by name fingerprint: %s",
                        clean_name,
                    )
                    self.logger.debug(
                        "[MeetAttendanceService] Tier2 name match: %r -> mentee, interval=%s to %s",
                        clean_name,
                        start,
                        end,
                    )
                    role_trees["mentee"].add(Interval(start, end))

                # Tier 3: Unidentified participant
                else:
                    self.logger.debug(
                        "[MeetAttendanceService] Tier3 anon: %r, interval=%s to %s",
                        clean_name,
                        start,
                        end,
                    )
                    anon_trees.setdefault(clean_name, IntervalTree()).add(
                        Interval(start, end)
                    )

        # Merge overlapping sessions into continuous blocks for each participant
        for t in role_trees.values():
            t.merge_overlaps()
        for t in anon_trees.values():
            t.merge_overlaps()
        self.logger.debug(
            "[MeetAttendanceService] Interval trees merged: mentor=%d, mentee=%d, anon_count=%d",
            len(role_trees["mentor"]),
            len(role_trees["mentee"]),
            len(anon_trees),
        )
        return role_trees, anon_trees

    def _analyze_attendance(
        self,
        role_trees: dict[str, IntervalTree],
        anon_trees: dict[str, IntervalTree],
        target_secs: float,
        mentor_id: int,
        mentee_id: int,
        meet_details: GoogleMeetingDetailDto,
    ) -> GoogleMeetingDetailDto:
        """
        Analyzes interval trees to determine meeting completion, absence, and lateness.

        Logic:
            1. Interaction - Computes overlap between mentor and mentee trees. If the overlap
               ratio meets MIN_INTERACTION_RATIO, the meeting is marked complete. When direct
               overlap is insufficient, the top anonymous participants are included as
               candidates and the best-overlapping pair is selected.
            2. Absence - If the meeting is incomplete and fewer than 2 distinct participants
               are present, the missing party is identified (or flagged as unknown if identity
               is ambiguous). If 2+ participants are present but overlap is insufficient,
               has_insufficient_duration is set.
            3. Lateness - For any interaction pair (identified or inferred), each participant's
               earliest join time is compared to the legal wait deadline (scheduled start +
               LATE_THRESHOLD). Identified users are attributed by ID; fully anonymous pairs
               are flagged via has_unknown_late.

        Args:
            role_trees: Dict with keys "mentor" and "mentee", each an IntervalTree of
                confirmed presence intervals for that role.
            anon_trees: Dict mapping display names to IntervalTrees for unidentified
                participants.
            target_secs: Minimum required interaction duration in seconds.
            mentor_id: Database ID of the mentor user.
            mentee_id: Database ID of the mentee user.
            meet_details: GoogleMeetingDetailDto instance carrying scheduled start/end
                times. Attendance results are written back onto this object.

        Returns:
            The same GoogleMeetingDetailDto passed in, with the following fields updated:
            is_completed, absent_user_id, late_user_id, has_unknown_absent,
            has_unknown_late, has_insufficient_duration.
        """
        m_tree, s_tree = role_trees["mentor"], role_trees["mentee"]
        legal_wait_end = isoparse(meet_details.start_datetime) + LATE_THRESHOLD
        self.logger.debug(
            "[MeetAttendanceService] _analyze_attendance: target_secs=%.0f, mentor_id=%s, mentee_id=%s, scheduled=%s to %s",
            target_secs,
            mentor_id,
            mentee_id,
            meet_details.start_datetime,
            meet_details.end_datetime,
        )

        # 1. Interaction Analysis
        # Calculate intersection for identified Mentor/Mentee
        real_interaction = self._get_tree_intersection_secs(m_tree, s_tree)
        self.logger.debug(
            "[MeetAttendanceService] Real interaction (mentor∩mentee): %.1fs (threshold=%.1fs)",
            real_interaction,
            target_secs * MIN_INTERACTION_RATIO,
        )

        # Find the best interaction candidate (including anonymous participants)
        if real_interaction >= (target_secs * MIN_INTERACTION_RATIO):
            self.logger.debug(
                "[MeetAttendanceService] Direct match sufficient, is_completed=True"
            )
            is_completed = True
            max_interaction = real_interaction
            best_m_tree, best_s_tree = m_tree, s_tree
            best_m_role, best_s_role = "mentor", "mentee"
        else:
            # Optimization: Only consider the top N anonymous users with longest stay
            sorted_anons = sorted(
                [(f"anon_{i}", tree) for i, (_, tree) in enumerate(anon_trees.items())],
                key=lambda x: sum((iv.end - iv.begin).total_seconds() for iv in x[1]),
                reverse=True,
            )[:TOP_ANONYMOUS_USERS]
            self.logger.debug(
                "[MeetAttendanceService] Direct match insufficient (%.1fs), searching with %d anon candidates",
                real_interaction,
                len(sorted_anons),
            )

            all_candidates = [("mentor", m_tree), ("mentee", s_tree)] + sorted_anons
            best_match = max(
                (
                    (
                        self._get_tree_intersection_secs(a[1], b[1]),
                        a[0],
                        b[0],
                        a[1],
                        b[1],
                    )
                    for a, b in combinations(all_candidates, 2)
                    if not a[1].is_empty() and not b[1].is_empty()
                ),
                key=lambda x: x[0],
                default=(0.0, None, None, None, None),
            )
            max_interaction, best_m_role, best_s_role, best_m_tree, best_s_tree = (
                best_match
            )
            is_completed = max_interaction >= (target_secs * MIN_INTERACTION_RATIO)
            self.logger.debug(
                "[MeetAttendanceService] Best interaction pair: (%s, %s) = %.1fs, is_completed=%s",
                best_m_role,
                best_s_role,
                max_interaction,
                is_completed,
            )

        # Initialize status flags
        absent_user_id = None
        late_user_ids = []
        has_unknown_absent = None
        has_unknown_late = False
        has_insufficient_duration = None

        m_exists = not m_tree.is_empty()
        s_exists = not s_tree.is_empty()
        anon_count = len(anon_trees)
        total_present_count = (
            (1 if m_exists else 0) + (1 if s_exists else 0) + anon_count
        )
        self.logger.debug(
            "[MeetAttendanceService] Presence: m_exists=%s, s_exists=%s, anon_count=%d, total=%d",
            m_exists,
            s_exists,
            anon_count,
            total_present_count,
        )

        # 2. Absence Logic
        if not is_completed:
            # If total headcount < 2, someone is definitely missing
            if total_present_count < 2:
                if m_exists and anon_count == 0:
                    absent_user_id = mentee_id  # Only Mentor present
                    self.logger.debug(
                        "[MeetAttendanceService] Absence: only mentor present -> absent_user_id=%s",
                        mentee_id,
                    )
                elif s_exists and anon_count == 0:
                    absent_user_id = mentor_id  # Only Mentee present
                    self.logger.debug(
                        "[MeetAttendanceService] Absence: only mentee present -> absent_user_id=%s",
                        mentor_id,
                    )
                else:
                    has_unknown_absent = True  # Ambiguous single participant
                    self.logger.debug(
                        "[MeetAttendanceService] Absence: ambiguous single participant -> has_unknown_absent=True"
                    )
            else:
                # 2+ people joined but overlap was too short
                has_insufficient_duration = True
                self.logger.debug(
                    "[MeetAttendanceService] Absence: 2+ joined but overlap too short -> has_insufficient_duration=True"
                )

        # 3. Lateness Logic (Triggered if at least 2 people were present)
        if max_interaction > 0:
            # Case A: Successful interaction found
            both_anon = (
                "mentor" not in (best_m_role or "")
                and "mentee" not in (best_m_role or "")
                and "mentor" not in (best_s_role or "")
                and "mentee" not in (best_s_role or "")
            )
            if both_anon:
                # Can detect late start, but cannot attribute to specific user_id
                if (
                    min(best_m_tree).begin > legal_wait_end
                    or min(best_s_tree).begin > legal_wait_end
                ):
                    has_unknown_late = True
                self.logger.debug(
                    "[MeetAttendanceService] Lateness case A-anon: has_unknown_late=%s",
                    has_unknown_late,
                )
                check_targets = []
            else:
                check_targets = [(best_m_role, best_m_tree), (best_s_role, best_s_tree)]
                self.logger.debug(
                    "[MeetAttendanceService] Lateness case A: check_targets=%s",
                    [r for r, _ in check_targets],
                )

        elif total_present_count >= 2:
            # Case B: Headcount >= 2 but zero overlap. Inference for 1v1 scenarios
            check_targets = []

            # If Mentor is identified and Mentee is absent but an anonymous guest is present,
            # infer the anonymous guest is the Mentee.
            if m_exists and not s_exists and anon_count > 0:
                top_anon_tree = sorted(
                    anon_trees.values(),
                    key=lambda t: sum((iv.end - iv.begin).total_seconds() for iv in t),
                    reverse=True,
                )[0]
                check_targets = [("mentor", m_tree), ("anon_mentee", top_anon_tree)]

            elif s_exists and not m_exists and anon_count > 0:
                top_anon_tree = sorted(
                    anon_trees.values(),
                    key=lambda t: sum((iv.end - iv.begin).total_seconds() for iv in t),
                    reverse=True,
                )[0]
                check_targets = [("anon_mentor", top_anon_tree), ("mentee", s_tree)]

            elif m_exists and s_exists:
                check_targets = [("mentor", m_tree), ("mentee", s_tree)]

            else:
                has_unknown_late = True
                self.logger.debug(
                    "[MeetAttendanceService] Lateness case B: both anon, has_unknown_late=True"
                )

            if check_targets:
                self.logger.debug(
                    "[MeetAttendanceService] Lateness case B: inferred check_targets=%s",
                    [r for r, _ in check_targets],
                )
        else:
            check_targets = []

        # Final Lateness Verification
        for role, tree in check_targets:
            if not tree or tree.is_empty():
                continue
            earliest_join = min(tree).begin
            is_late = earliest_join > legal_wait_end
            self.logger.debug(
                "[MeetAttendanceService] Lateness check: role=%s, earliest_join=%s, legal_wait_end=%s, late=%s",
                role,
                earliest_join,
                legal_wait_end,
                is_late,
            )
            if is_late:
                if "mentor" in role:
                    late_user_ids.append(mentor_id)
                elif "mentee" in role:
                    late_user_ids.append(mentee_id)

        self.logger.debug(
            "[MeetAttendanceService] Attendance result: is_completed=%s, absent_user_id=%s, late_user_id=%s, has_unknown_absent=%s, has_unknown_late=%s, has_insufficient_duration=%s",
            is_completed,
            absent_user_id,
            late_user_ids,
            has_unknown_absent,
            has_unknown_late,
            has_insufficient_duration,
        )

        meet_details.is_completed = is_completed
        meet_details.absent_user_id = absent_user_id
        meet_details.late_user_id = late_user_ids
        meet_details.has_unknown_absent = has_unknown_absent
        meet_details.has_unknown_late = has_unknown_late
        meet_details.has_insufficient_duration = has_insufficient_duration

        return meet_details

    def _get_tree_intersection_secs(
        self, tree_a: IntervalTree, tree_b: IntervalTree
    ) -> float:
        """
        Calculates the total overlapping duration in seconds between two IntervalTrees.

        Args:
            tree_a: First IntervalTree of datetime intervals.
            tree_b: Second IntervalTree of datetime intervals.

        Returns:
            Total overlapping seconds as a float.
        """
        total = 0.0
        for iv_a in tree_a:
            for iv_b in tree_b.overlap(iv_a.begin, iv_a.end):
                total += (
                    min(iv_a.end, iv_b.end) - max(iv_a.begin, iv_b.begin)
                ).total_seconds()
        return total

    def _build_pair_lookup(
        self, pairs: list[MentorshipPairsEntity]
    ) -> dict[str, tuple]:
        """
        Builds a lookup map from conference ID to (pair entity, meeting index).

        Only includes meetings that have a conference_id and are not yet completed.

        Args:
            pairs: List of mentorship pair ORM objects with a meeting_log attribute.

        Returns:
            A dict mapping conference_id strings to (pair, gm_index) tuples.
        """
        return {
            gm["conference_id"]: (p, i)
            for p in pairs
            for i, gm in enumerate((p.meeting_log or {}).get("google_meetings", []))
            if gm.get("conference_id") and not gm.get("is_completed")
        }

    def _get_user_emails(self, user: UsersEntity | None) -> set[str]:
        """
        Returns the set of all known email addresses for a user.

        Args:
            user: User ORM object, or None.

        Returns:
            A set of lowercase email strings (primary + alternatives), or an empty set
            if user is None.
        """
        if not user:
            return set()
        return {user.primary_email.lower()} | {
            e.lower() for e in (user.alternative_emails or [])
        }

    def _get_user_name_fingerprints(self, user: UsersEntity | None) -> set[str]:
        """
        Builds a set of normalized name variants for fuzzy display-name matching.

        Includes first name, last name, preferred name, and the full "first last" combination.

        Args:
            user: User ORM object, or None.

        Returns:
            A set of stripped, lowercased name strings, or an empty set if user is None.
        """
        if not user:
            return set()
        names = {
            user.first_name,
            user.last_name,
            user.preferred_name,
            f"{user.first_name} {user.last_name}",
        }
        return {n.strip().lower() for n in names if n}
