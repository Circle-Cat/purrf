import { useCallback, useEffect, useState } from "react";
import { getMyMentorshipApprovals } from "@/api/mentorshipApi";

/**
 * Loads the mentorship approval requests waiting on the signed-in reviewer.
 * With `enabled` off nothing is fetched and the list stays empty.
 *
 * @param {boolean} enabled - The viewer can review mentorship requests.
 * @returns {{requests: Object[], isLoading: boolean, reload: () => Promise<void>}}
 */
export const useMyMentorshipApprovals = (enabled) => {
  const [requests, setRequests] = useState([]);
  const [isLoading, setIsLoading] = useState(false);

  const load = useCallback(() => {
    if (!enabled) {
      setRequests([]);
      return Promise.resolve();
    }
    setIsLoading(true);
    return getMyMentorshipApprovals()
      .then(({ data }) => setRequests(data ?? []))
      .catch((err) => {
        console.error("Failed to fetch your pending approvals", err);
      })
      .finally(() => setIsLoading(false));
  }, [enabled]);

  useEffect(() => {
    load();
  }, [load]);

  return { requests, isLoading, reload: load };
};
