import { useCallback, useEffect, useState } from "react";
import { getParticipantDetail } from "@/api/mentorshipApi";
import { useRequestGuard } from "@/hooks/useRequestGuard";

/**
 * Loads one person's detail in one round. Nothing is asked until both ids
 * are known. `refetch` reloads quietly, without going back to the loading
 * state, so the page does not flash after a note or a request is sent.
 *
 * @param {number|string|null} roundId
 * @param {number|string|null} userId
 * @returns {{detail: Object|null, loading: boolean, error: boolean,
 *            refetch: () => Promise<void>}}
 */
export const useParticipantDetail = (roundId, userId) => {
  const ready = roundId != null && userId != null;
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(ready);
  const [error, setError] = useState(false);
  const { begin, isCurrent } = useRequestGuard();

  const fetchDetail = useCallback(
    async ({ quiet = false } = {}) => {
      if (roundId == null || userId == null) return;
      const seq = begin();
      if (!quiet) setLoading(true);
      setError(false);
      try {
        const { data } = await getParticipantDetail(roundId, userId);
        if (!isCurrent(seq)) return;
        setDetail(data ?? null);
      } catch {
        if (isCurrent(seq)) setError(true);
      } finally {
        if (isCurrent(seq)) setLoading(false);
      }
    },
    [roundId, userId, begin, isCurrent],
  );

  useEffect(() => {
    fetchDetail();
  }, [fetchDetail]);

  const refetch = useCallback(
    () => fetchDetail({ quiet: true }),
    [fetchDetail],
  );

  return { detail, loading, error, refetch };
};
