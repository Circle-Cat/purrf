import { useState } from "react";
import { toast } from "sonner";

const messageOf = (err, fallback) => err?.response?.data?.message || fallback;

/**
 * Runs one approval action at a time: the call, then a success toast and
 * `onChanged`, or the server's refusal as an error toast. While one runs,
 * `busy` is on, so its buttons can be turned off.
 *
 * @param {() => Promise<void>|void} onChanged - Reload what the action changed.
 * @returns {{busy: boolean,
 *            act: (call: () => Promise<unknown>, done: string,
 *                  fallback: string) => Promise<boolean>}}
 *   `act` resolves to whether the call succeeded.
 */
export const useApprovalAction = (onChanged) => {
  const [busy, setBusy] = useState(false);

  const act = async (call, done, fallback) => {
    setBusy(true);
    try {
      await call();
      toast.success(done);
      await onChanged();
      return true;
    } catch (err) {
      toast.error(messageOf(err, fallback));
      return false;
    } finally {
      setBusy(false);
    }
  };

  return { busy, act };
};
