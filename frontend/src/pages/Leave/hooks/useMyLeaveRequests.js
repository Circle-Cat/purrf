import { useCallback, useEffect, useState } from "react";

import {
  getMyLeaveRequests,
  submitLeaveRequest,
  withdrawLeaveRequest,
} from "@/api/leaveApi";
import { LEAVE_REQUEST_STATUS } from "@/constants/LeaveRequest";

/** The message the server sent, which names what to do about the refusal. */
const refusalMessage = (error) =>
  error?.response?.data?.message ?? "Something went wrong. Try again.";

/**
 * The signed-in employee's own requests, and the two things they can do.
 *
 * Filing and withdrawing both reload the list rather than patching it in
 * place. The stored request carries figures the client never computed -- the
 * hours the days actually came to, and whether it was marked as short notice
 * -- so the list is the only place those appear.
 *
 * Refusals are surfaced with the server's own wording. Each one names the fix
 * (which request it clashed with, how much notice was needed), and a generic
 * "could not save" would throw that away.
 *
 * @param {{enabled?: boolean}} [options]
 * @returns {{
 *   requests: Array<object>,
 *   isLoading: boolean,
 *   loadError: boolean,
 *   isSaving: boolean,
 *   saveError: string|null,
 *   withdrawingId: number|null,
 *   load: () => void,
 *   file: (payload: object) => Promise<boolean>,
 *   withdraw: (requestId: number) => Promise<void>,
 * }}
 */
export const useMyLeaveRequests = ({ enabled = true } = {}) => {
  const [requests, setRequests] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const [withdrawingId, setWithdrawingId] = useState(null);

  const load = useCallback(() => {
    if (!enabled) return Promise.resolve();
    setIsLoading(true);
    setLoadError(false);
    return getMyLeaveRequests()
      .then(({ data }) => setRequests(data ?? []))
      .catch(() => {
        setLoadError(true);
        setRequests([]);
      })
      .finally(() => setIsLoading(false));
  }, [enabled]);

  useEffect(() => {
    load();
  }, [load]);

  const file = useCallback(
    async (payload) => {
      // One at a time. A second submission while the first is in flight would
      // be refused by the overlap check, and that refusal reads as the first
      // one having failed.
      if (isSaving) return false;
      setIsSaving(true);
      setSaveError(null);
      try {
        await submitLeaveRequest(payload);
        await load();
        return true;
      } catch (error) {
        setSaveError(refusalMessage(error));
        return false;
      } finally {
        setIsSaving(false);
      }
    },
    [isSaving, load],
  );

  const withdraw = useCallback(
    async (requestId) => {
      if (withdrawingId !== null) return;
      setWithdrawingId(requestId);
      setSaveError(null);
      try {
        await withdrawLeaveRequest(requestId);
        await load();
      } catch (error) {
        setSaveError(refusalMessage(error));
      } finally {
        setWithdrawingId(null);
      }
    },
    [withdrawingId, load],
  );

  return {
    requests,
    isLoading,
    loadError,
    isSaving,
    saveError,
    withdrawingId,
    load,
    file,
    withdraw,
  };
};

/** Whether a request is still the employee's to take back. */
export const isWithdrawable = (row) =>
  row.status === LEAVE_REQUEST_STATUS.PENDING;
