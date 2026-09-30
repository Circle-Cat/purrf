import { useEffect, useState } from "react";
import { getRoundFeedback } from "@/api/mentorshipApi";

/**
 * Loads one round's feedback for the admin console.
 *
 * @param {number|string} roundId - The mentorship round's id.
 * @returns {{feedback: Object|null, isLoading: boolean, error: boolean}}
 */
export const useRoundFeedback = (roundId) => {
  const [feedback, setFeedback] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(false);
    getRoundFeedback(roundId)
      .then(({ data }) => {
        if (!cancelled) setFeedback(data ?? null);
      })
      .catch((err) => {
        console.error("Failed to fetch round feedback", err);
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [roundId]);

  return { feedback, isLoading, error };
};
