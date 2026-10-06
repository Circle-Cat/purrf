import { useEffect, useState } from "react";
import { getMentorshipRoundSlots } from "@/api/mentorshipApi";

/**
 * The round taking registrations right now, as the server decides it for the
 * Personal Dashboard: the slots' registration round, when its window is open.
 *
 * @returns {string|null|undefined} Its id as a string; null when no round is
 *   taking registrations or the slots could not be read; undefined until the
 *   slots have loaded.
 */
export const useRegistrationRound = () => {
  const [roundId, setRoundId] = useState(undefined);

  useEffect(() => {
    getMentorshipRoundSlots()
      .then(({ data }) =>
        setRoundId(
          data?.isRegistrationOpen && data.registrationRoundId != null
            ? String(data.registrationRoundId)
            : null,
        ),
      )
      .catch(() => setRoundId(null));
  }, []);

  return roundId;
};
