import {
  getAllMentorshipRounds,
  getMyMentorshipPartners,
  getMyMentorshipRegistration,
  postMyMentorshipRegistration,
  getMyMentorshipMatchResult,
  getMyMentorshipMeetingLog,
} from "@/api/mentorshipApi";
import { getMyMentorshipMeetingsV2 } from "@/api/meetingApi";

import {
  calculateMentorshipSlots,
  calculateRoundStatus,
} from "@/pages/PersonalDashboard/utils/mentorshipRounds";
import { MentorshipParticipantRoles } from "@/constants/MentorshipParticipantRoles";
import { useCallback, useEffect, useRef, useState } from "react";
import { useFeatureFlags } from "@/hooks/useFeatureFlags";
import { useRequestGuard } from "@/hooks/useRequestGuard";
import { FEATURE_FLAGS } from "@/constants/FeatureFlags";

/**
 * React hook for loading and managing mentorship-related data
 * for the Personal Dashboard.
 *
 * Responsibilities:
 * - Fetch all mentorship rounds and determine current registration
 *   and feedback slots.
 * - Load the current user's registration data for the active round.
 * - Lazily load past mentorship partners.
 * - Provide helpers for saving registration data.
 *
 * This hook encapsulates business rules around:
 * - which round is currently actionable
 * - whether registration or feedback actions are enabled
 *
 * @param {{enabled?: boolean, hiredMentorshipRole?: "mentor"|"mentee"|null}} params -
 *   `hiredMentorshipRole` comes from the user's HIRED activity application
 *   and decides which of the round's two deadlines applies to them.
 * @returns {{
 *   regRoundId: string | null,
 *   regRoundName: string,
 *   feedbackRoundId: string | null,
 *   isRegistrationOpen: boolean,
 *   registrationDeadlineAt: string | null,
 *   isFeedbackEnabled: boolean,
 *   registration: Object | null,
 *   saveRegistration: (data: Object) => Promise<any> | undefined,
 *   isLoading: boolean,
 *   isPartnersLoading: boolean,
 *   loadPastPartners: () => Promise<void>,
 *   userTimezone: string | null
 * }}
 */
export const useMentorshipData = ({
  enabled = true,
  hiredMentorshipRole = null,
} = {}) => {
  const flags = useFeatureFlags();
  const useV2Meetings = !!flags[FEATURE_FLAGS.CREATE_GOOGLE_MEETING];

  const [roundStatus, setRoundStatus] = useState({
    regRoundId: null,
    feedbackRoundId: null,
    isFeedbackEnabled: false,
    matchResultRoundName: "",
    canViewMatch: false,
  });
  const [isRegistrationOpen, setIsRegistrationOpen] = useState(false);
  // The deadline that produced `isRegistrationOpen`, kept so callers can
  // name the date instead of only knowing whether it has passed.
  const [registrationDeadlineAt, setRegistrationDeadlineAt] = useState(null);
  const [regRoundName, setRegRoundName] = useState("");
  const [matchResult, setMatchResult] = useState(null);
  // Current user's registration data for the active round
  const [registration, setRegistration] = useState(null);

  // Loading state for initial mentorship data, derived during render
  // rather than set from the effect. Which fetch the data in state
  // belongs to is what actually decides it, so being enabled -- or
  // handed a different role -- reports loading on the very render that
  // does it. Raising the flag from the effect instead is one commit too
  // late: sibling hooks in the same commit have already read the stale
  // `false` and taken the empty initial state, no open round and no
  // deadline, for a finished answer.
  const requestKey = enabled ? `role:${hiredMentorshipRole}` : null;
  const [fetchState, setFetchState] = useState({
    key: requestKey,
    isSettled: false,
  });
  if (fetchState.key !== requestKey) {
    setFetchState({ key: requestKey, isSettled: false });
  }
  const isLoading = enabled && !fetchState.isSettled;

  // Cached list of past mentorship partners
  const [pastPartners, setPastPartners] = useState([]);

  // Loading state for user profile timezone
  const [userTimezone, setUserTimezone] = useState(null);

  // Loading state for partners data
  const [isPartnersLoading, setIsPartnersLoading] = useState(false);

  // Round Selector
  const [roundSelectionData, setRoundSelectionData] = useState({
    sortedRounds: [],
    activeRoundId: null,
  });
  const [participantDetails, setParticipantDetails] = useState({
    roundInfo: null,
    partnerMeetingOverview: [],
    participantRole: null,
  });
  const [selectedRoundId, setSelectedRoundId] = useState(null);
  // Loading state for meeting log
  const [isMeetingsLoading, setIsMeetingsLoading] = useState(false);
  // Cache for partners data per round, reset on page mount
  const partnersCacheRef = useRef({});
  // Guards refreshMeetings against stale-round responses and unmount updates.
  const { begin, isCurrent } = useRequestGuard();

  /**
   * refreshRegistration
   *
   * Refreshes the current user's registration data if the registration round ID (`regRoundId`) is available.
   * It fetches the registration data associated with the current round and updates the `registration` state.
   * If the `regRoundId` is not set, no API call is made.
   *
   * @returns {Promise<void>} - A promise that resolves when the registration data has been refreshed or an error occurs.
   */
  const refreshRegistration = async () => {
    if (!roundStatus.regRoundId) return;
    try {
      const { data: regData } = await getMyMentorshipRegistration(
        roundStatus.regRoundId,
      );
      setRegistration(regData);
    } catch (err) {
      console.error("Failed to refresh registration", err);
    }
  };

  /**
   * useEffect to initialize and load mentorship data.
   *
   * This effect is run once when the component is mounted. It fetches the available mentorship rounds, calculates
   * the mentorship slot status, and then fetches the user's registration data for the active round (if any).
   * It marks the request settled once the data has been fetched (or an error has occurred), which is what
   * resolves `isLoading` to `false`.
   *
   * @returns {void}
   */
  useEffect(() => {
    if (!enabled) return;

    const fetchData = async () => {
      try {
        const now = new Date().toISOString();
        const { data: rounds } = await getAllMentorshipRounds();

        const status = calculateMentorshipSlots(rounds);
        setRoundStatus(status);

        // If there is an actionable round, fetch the user's registration data
        // Note: registration data is fetched based on the registration slot first
        if (status.regRoundId) {
          const { data: regData } = await getMyMentorshipRegistration(
            status.regRoundId,
          );
          setRegistration(regData);

          // Which deadline applies comes from the admission, not from an
          // existing registration: a first-time registrant has no
          // `roundPreferences` at all, so reading the role from there put
          // every mentor on the mentee deadline.
          const deadlineKey =
            hiredMentorshipRole === MentorshipParticipantRoles.MENTOR
              ? "mentorApplicationDeadlineAt"
              : "menteeApplicationDeadlineAt";
          const regRound = rounds.find(
            (r) => r.id?.toString() === status.regRoundId?.toString(),
          );
          const deadline = regRound?.timeline?.[deadlineKey] ?? null;
          setRegRoundName(regRound?.name ?? "");
          setRegistrationDeadlineAt(deadline);
          setIsRegistrationOpen(Boolean(deadline) && now < deadline);

          if (regData && regData.isRegistered) {
            try {
              const { data: matchData } = await getMyMentorshipMatchResult(
                status.regRoundId,
              );
              setMatchResult(matchData);
            } catch (matchErr) {
              console.error("Failed to fetch match result", matchErr);
            }
          } else {
            setMatchResult(null);
          }
        }

        const selectionData = calculateRoundStatus(rounds);
        setRoundSelectionData(selectionData);

        if (selectionData.activeRoundId) {
          setSelectedRoundId(selectionData.activeRoundId);
          setIsMeetingsLoading(true);
        }
      } catch (err) {
        console.error("Failed to fetch mentorship data", err);
      } finally {
        // Tagged with the request it answers: a response that arrives
        // after the role changed settles nothing, and the next render
        // notices the mismatch and goes back to loading.
        setFetchState({ key: requestKey, isSettled: true });
      }
    };

    fetchData();
  }, [enabled, hiredMentorshipRole, requestKey]);

  /**
   * Lazily load the user's past mentorship partners.
   *
   * @returns {Promise<void>}
   */
  const loadPastPartners = async () => {
    setIsPartnersLoading(true);
    try {
      const { data: allPastPartners } = await getMyMentorshipPartners();
      setPastPartners(allPastPartners || []);
    } catch (err) {
      console.error("Failed to fetch partners data", err);
    } finally {
      setIsPartnersLoading(false);
    }
  };

  /**
   * Save or update the user's mentorship registration.
   *
   * This operation is only allowed when:
   * - a valid registration round exists
   * - registration for that round is currently open
   *
   * @param {Object} data - Registration payload submitted by the user.
   * @returns {Promise<any> | undefined} API response when saved, or undefined if not allowed.
   */
  const saveRegistration = async (data) => {
    // Only allow saving when registration is open and a valid round exists
    if (!roundStatus.regRoundId || !isRegistrationOpen) return;
    return postMyMentorshipRegistration(roundStatus.regRoundId, data);
  };

  const handleRoundChange = useCallback(
    (id) => {
      if (id !== selectedRoundId) {
        setParticipantDetails({
          roundInfo: null,
          partnerMeetingOverview: [],
          participantRole: null,
        });
        setIsMeetingsLoading(true);
      }
      setSelectedRoundId(id);
    },
    [selectedRoundId],
  );

  const refreshMeetings = useCallback(async () => {
    if (!selectedRoundId) return;
    const seq = begin();
    setIsMeetingsLoading(true);

    try {
      const [{ data: meetingLog }, { data: partnersInfo }] = await Promise.all([
        useV2Meetings
          ? getMyMentorshipMeetingsV2({
              roundId: selectedRoundId,
              includeDetails: false,
            })
          : getMyMentorshipMeetingLog(selectedRoundId),
        partnersCacheRef.current[selectedRoundId]
          ? Promise.resolve({ data: partnersCacheRef.current[selectedRoundId] })
          : getMyMentorshipPartners(selectedRoundId),
      ]);

      // A newer round was selected while this request was in flight — drop the
      // stale response so it can't overwrite the current round's data.
      if (!isCurrent(seq)) return;

      partnersCacheRef.current[selectedRoundId] ??= partnersInfo;
      setUserTimezone((prev) => prev ?? meetingLog?.userTimezone ?? null);

      const currentRound = roundSelectionData.sortedRounds.find(
        (r) => r.id.toString() === selectedRoundId.toString(),
      );

      if (!partnersInfo || partnersInfo.length === 0) {
        const isRegisteredForRound =
          selectedRoundId?.toString() === roundStatus.regRoundId?.toString() &&
          registration?.isRegistered === true;
        setParticipantDetails({
          roundInfo: currentRound,
          partnerMeetingOverview: [],
          participantRole: null,
          isRegistered: isRegisteredForRound,
        });
        return;
      }

      const requiredMeetings = currentRound?.requiredMeetings ?? 0;
      const partnerMeeting = (partnersInfo || []).map((partner) => {
        const info = meetingLog?.meetingInfo?.find(
          (i) => i.partnerId.toString() === partner.id.toString(),
        );
        const completedCount = info?.completedMeetingsCount ?? 0;
        const completedRate =
          requiredMeetings > 0
            ? Math.round((completedCount / requiredMeetings) * 100)
            : 0;

        return {
          partnerId: partner.id,
          preferredName: partner.preferredName,
          firstName: partner.firstName,
          lastName: partner.lastName,
          partnerEmail: partner.primaryEmail,
          requiredMeetings,
          completedCount,
          completedRate,
          meetingTimeList: info?.meetingTimeList || [],
          participantRole: info?.participantRole,
        };
      });

      const globalParticipantRole =
        partnerMeeting?.[0]?.participantRole ?? null;

      setParticipantDetails({
        roundInfo: currentRound,
        partnerMeetingOverview: partnerMeeting,
        participantRole: globalParticipantRole,
      });
    } catch (MeetingErr) {
      console.error("Failed to fetch meeting log", MeetingErr);
    } finally {
      // Only the latest in-flight request controls the loading flag.
      if (isCurrent(seq)) {
        setIsMeetingsLoading(false);
      }
    }
  }, [
    selectedRoundId,
    roundSelectionData.sortedRounds,
    roundStatus.regRoundId,
    registration?.isRegistered,
  ]);

  useEffect(() => {
    if (!selectedRoundId) {
      setParticipantDetails({
        roundInfo: null,
        partnerMeetingOverview: [],
        participantRole: null,
      });
      return;
    }
    refreshMeetings();
  }, [selectedRoundId, refreshMeetings]);

  return {
    ...roundStatus,
    isRegistrationOpen,
    registrationDeadlineAt,
    regRoundName,
    // registration
    registration,
    saveRegistration,
    refreshRegistration,
    // loading states
    isLoading,
    isParticipantCardLoading: isLoading || isMeetingsLoading,
    isPartnersLoading,
    // partner history
    loadPastPartners,
    pastPartners,
    // match result
    matchResult,
    // round selector for participant card
    selectedRoundId,
    roundSelectionData,
    handleRoundChange,
    // meeting
    refreshMeetings,
    participantDetails,
    // user profile timezone
    userTimezone,
  };
};
