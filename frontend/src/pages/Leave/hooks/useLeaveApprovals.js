import { useCallback, useEffect, useState } from "react";

import { decideLeaveRequest, getLeaveApprovals } from "@/api/leaveApi";
import { LEAVE_REQUEST_STATUS } from "@/constants/LeaveRequest";

/**
 * Everything filed against the current user, split into what still needs
 * deciding and what has been settled.
 *
 * `isApprover` is what the entry point is hung off, and it is derived from the
 * response rather than from any flag on the user: approving is not a
 * permission, and a manager who is outside the leave population has no
 * employment profile to read a manager relationship off. Somebody approves for
 * others exactly when somebody has filed against them.
 *
 * It fails closed -- false while loading and false after a load error -- so a
 * slow or broken fetch never puts up a button that leads nowhere. The cost is
 * that a brand new manager whose reports have never filed anything sees no
 * entry point; they also have nothing to decide, and the entry appears with
 * the first request.
 *
 * Both splits are derived during render, not stored in state from an effect:
 * an effect would leave consumers reading last render's list for one paint.
 *
 * `enabled` false fetches nothing and reports nothing: a feature switched off
 * must not be calling its endpoint on every dashboard load.
 *
 * @returns {{
 *   pending: Array<object>,
 *   decided: Array<object>,
 *   isApprover: boolean,
 *   pendingCount: number,
 *   isLoading: boolean,
 *   loadError: boolean,
 *   decidingId: number|null,
 *   decideError: boolean,
 *   load: () => void,
 *   decide: (requestId: number, approve: boolean) => Promise<void>,
 * }}
 */
export const useLeaveApprovals = ({ enabled = true } = {}) => {
  const [requests, setRequests] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [decidingId, setDecidingId] = useState(null);
  const [decideError, setDecideError] = useState(false);

  const load = useCallback(() => {
    if (!enabled) return Promise.resolve();
    setIsLoading(true);
    setLoadError(false);
    return getLeaveApprovals()
      .then(({ data }) => setRequests(data ?? []))
      .catch(() => {
        setLoadError(true);
        // A failed reload must not leave a stale queue standing: it would keep
        // offering Approve on requests we can no longer see the state of.
        setRequests([]);
      })
      .finally(() => setIsLoading(false));
  }, [enabled]);

  useEffect(() => {
    load();
  }, [load]);

  const decide = useCallback(
    async (requestId, approve) => {
      // One decision at a time. Approving is irreversible, and a second click
      // while the first is in flight would be answered by the server with a
      // refusal the user reads as their own approval having failed.
      if (decidingId !== null) return;
      setDecidingId(requestId);
      setDecideError(false);
      try {
        await decideLeaveRequest(requestId, approve);
        await load();
      } catch {
        setDecideError(true);
      } finally {
        setDecidingId(null);
      }
    },
    [decidingId, load],
  );

  const pending = requests.filter(
    (row) => row.status === LEAVE_REQUEST_STATUS.PENDING,
  );
  const decided = requests.filter(
    (row) => row.status !== LEAVE_REQUEST_STATUS.PENDING,
  );

  return {
    pending,
    decided,
    isApprover: enabled && !isLoading && !loadError && requests.length > 0,
    pendingCount: pending.length,
    isLoading,
    loadError,
    decidingId,
    decideError,
    load,
    decide,
  };
};
