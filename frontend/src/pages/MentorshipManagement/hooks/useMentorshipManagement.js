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
    // The basic round list is open to any authenticated user; per-round detail
    // stats (need_details=true) require MENTORSHIP_ADMIN_READ on the backend,
    // so we mirror canReadRounds into the request instead of skipping it.
    setIsLoading(true);
    try {
      const { data: rounds } = await getAllMentorshipRounds(canReadRounds);
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
    openCreate,
    openEdit,
    closeModal,
    saveRound,
  };
};
