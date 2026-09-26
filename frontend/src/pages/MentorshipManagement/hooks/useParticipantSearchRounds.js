import { useEffect, useState } from "react";
import { getAllMentorshipRounds } from "@/api/mentorshipApi";

/**
 * Rounds for the Participant tab's Round filter dropdown, in the order the
 * API returns them: latest round first. Re-sorting here by id would undo
 * that, because round ids are not in time order.
 *
 * @returns {Object[]} The rounds, or an empty list if the fetch fails.
 */
export const useParticipantSearchRounds = () => {
  const [rounds, setRounds] = useState([]);

  useEffect(() => {
    getAllMentorshipRounds()
      .then(({ data }) => setRounds(data ?? []))
      .catch(() => setRounds([]));
  }, []);

  return rounds;
};
