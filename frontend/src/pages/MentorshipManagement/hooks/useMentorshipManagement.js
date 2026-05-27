import { useCallback, useEffect, useState } from "react";
import { getAllMentorshipRounds } from "@/api/mentorshipApi";
import { calculateRoundStatus } from "@/pages/PersonalDashboard/utils/mentorshipRounds";

/**
 * Hook for the Mentorship Admin Dashboard.
 *
 * Fetches all rounds with per-round pair stats (active pairs, matched
 * participants, total completed meetings), derives sorted rounds and status
 * labels, computes footer totals (completed rounds, total matched participants,
 * total completed meetings), and manages the create/edit round modal state.
 */
export const useMentorshipManagement = () => {
  const [rounds, setRounds] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  // Modal state: { open: bool, round: Object|null }
  // round === null → create mode; round !== null → edit mode
  const [roundModalState, setRoundModalState] = useState({
    open: false,
    round: null,
  });

  const refreshRounds = useCallback(async () => {
    setIsLoading(true);
    try {
      const { data: rounds } = await getAllMentorshipRounds(true);
      setRounds(rounds ?? []);
    } catch (err) {
      console.error("Failed to fetch mentorship rounds", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshRounds();
  }, [refreshRounds]);

  // Derive sorted rounds and status labels via existing utility
  const { sortedRounds } = calculateRoundStatus(rounds);

  // Compute footer totals
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

  // Modal actions
  const openCreate = () => setRoundModalState({ open: true, round: null });
  const openEdit = (round) => setRoundModalState({ open: true, round });
  const closeModal = () => setRoundModalState({ open: false, round: null });

  return {
    sortedRounds,
    totals,
    isLoading,
    roundModalState,
    refreshRounds,
    openCreate,
    openEdit,
    closeModal,
  };
};
