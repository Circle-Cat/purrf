import { useCallback, useEffect, useState } from "react";
import {
  getAllMentorshipRounds,
  upsertMentorshipRound,
} from "@/api/mentorshipApi";
import { calculateRoundStatus } from "@/pages/PersonalDashboard/utils/mentorshipRounds";

/**
 * Hook for the Mentorship Admin Dashboard.
 *
 * Fetches all rounds with per-round pair stats (active pairs, matched
 * participants, total completed meetings), derives sorted rounds and status
 * labels, computes footer totals (completed rounds, total matched participants,
 * total completed meetings), and manages the create/edit round modal state.
 */
export const useMentorshipManagement = (canReadRounds = true) => {
  const [rounds, setRounds] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  // Modal state: { open: bool, round: Object|null }
  // round === null → create mode; round !== null → edit mode
  const [roundModalState, setRoundModalState] = useState({
    open: false,
    round: null,
  });

  const refreshRounds = useCallback(async () => {
    // The detailed round view requires MENTORSHIP_ROUND_READ; skip the request
    // when the user lacks it (the backend would return 403) and show nothing.
    if (!canReadRounds) {
      setRounds([]);
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    try {
      const { data: rounds } = await getAllMentorshipRounds(true);
      setRounds(rounds ?? []);
    } catch (err) {
      console.error("Failed to fetch mentorship rounds", err);
    } finally {
      setIsLoading(false);
    }
  }, [canReadRounds]);

  useEffect(() => {
    refreshRounds();
  }, [refreshRounds]);

  const { sortedRounds } = calculateRoundStatus(rounds);

  const totals = {
    totalCompletedRounds: sortedRounds.filter((r) => r.status === "completed")
      .length,
    totalParticipants: rounds.reduce(
      (sum, r) => sum + (r.matchedParticipants ?? 0),
      0,
    ),
    totalMeetings: rounds.reduce(
      (sum, r) => sum + (r.totalCompletedMeetings ?? 0),
      0,
    ),
  };

  const openCreate = () => setRoundModalState({ open: true, round: null });
  const openEdit = (round) => setRoundModalState({ open: true, round });
  const closeModal = () => setRoundModalState({ open: false, round: null });

  const saveRound = async (payload) => {
    await upsertMentorshipRound(payload);
    await refreshRounds();
    closeModal();
  };

  return {
    sortedRounds,
    totals,
    isLoading,
    roundModalState,
    refreshRounds,
    openCreate,
    openEdit,
    closeModal,
    saveRound,
  };
};
