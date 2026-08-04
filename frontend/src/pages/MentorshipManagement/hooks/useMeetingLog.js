import { useCallback, useEffect, useState } from "react";
import { getMeetingLog, updateMeetingLog } from "@/api/mentorshipApi";
import { useRequestGuard } from "@/hooks/useRequestGuard";

/**
 * Fetches a pair's meeting log only while `open` is true.
 *
 * The request is deferred until the dialog opens to avoid eagerly fetching
 * meeting logs for every visible table row.
 *
 * @param {number|null} pairId
 * @param {boolean} open
 */
export const useMeetingLog = (pairId, open) => {
  const [meetings, setMeetings] = useState([]);
  const [roundVersion, setRoundVersion] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const { begin, isCurrent } = useRequestGuard();

  const applyLogResponse = (data) => {
    setMeetings(data.meetings ?? []);
    setRoundVersion(data.roundVersion ?? null);
  };

  const fetchLog = useCallback(async () => {
    if (pairId == null) return;
    const seq = begin();
    setLoading(true);
    setError(false);
    try {
      const { data } = await getMeetingLog(pairId);
      if (!isCurrent(seq)) return;
      applyLogResponse(data);
    } catch {
      if (isCurrent(seq)) setError(true);
    } finally {
      if (isCurrent(seq)) setLoading(false);
    }
  }, [pairId, begin, isCurrent]);

  useEffect(() => {
    if (!open || pairId == null) return;
    fetchLog();
  }, [open, pairId, fetchLog]);

  /**
   * Sends a batch of meeting log updates and deletes to the server,
   * safely handles out-of-order responses, and updates local state.
   *
   * @param {Object} batch - The batch payload containing updates and deletes.
   * @returns {Promise<void>}
   */
  const saveMeetingBatch = useCallback(
    async (batch) => {
      const seq = begin();
      const { data } = await updateMeetingLog(pairId, batch);
      if (!isCurrent(seq)) return;
      applyLogResponse(data);
    },
    [pairId, begin, isCurrent],
  );

  return { meetings, roundVersion, loading, error, saveMeetingBatch };
};
