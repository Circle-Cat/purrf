import { useEffect, useState } from "react";
import { getMentorshipApprovers } from "@/api/mentorshipApi";

/**
 * Loads who a mentorship approval request can be sent to, whenever
 * `enabled` turns on (a dialog opening), so the list is fresh each time.
 * The caller is never in it: the backend leaves them out.
 *
 * @param {boolean} enabled - Load now.
 * @returns {{approvers: {userId: number, name: string}[], isLoading: boolean,
 *            error: boolean}}
 */
export const useMentorshipApprovers = (enabled) => {
  const [approvers, setApprovers] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!enabled) return undefined;
    let cancelled = false;
    setIsLoading(true);
    setError(false);
    getMentorshipApprovers()
      .then(({ data }) => {
        if (!cancelled) setApprovers(data ?? []);
      })
      .catch((err) => {
        console.error("Failed to fetch the approvers", err);
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [enabled]);

  return { approvers, isLoading, error };
};
