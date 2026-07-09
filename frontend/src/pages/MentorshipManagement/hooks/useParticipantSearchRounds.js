import { useEffect, useState } from "react";
import { getAllMentorshipRounds } from "@/api/mentorshipApi";

/** Rounds for the Participant tab's Round filter dropdown. */
export const useParticipantSearchRounds = () => {
  const [rounds, setRounds] = useState([]);

  useEffect(() => {
    getAllMentorshipRounds()
      .then(({ data }) =>
        setRounds([...(data ?? [])].sort((a, b) => b.id - a.id)),
      )
      .catch(() => setRounds([]));
  }, []);

  return rounds;
};
