import { useCallback, useEffect, useState } from "react";

import { adjustLeaveBalance, getLeaveBalances } from "@/api/leaveApi";

/** The message the server sent, which says which rule the correction broke. */
const refusalMessage = (error) =>
  error?.response?.data?.message ?? "Something went wrong. Try again.";

const EMPTY_EXCLUDED = {
  left: [],
  noHireDate: [],
  unreadable: [],
  unresolved: [],
  notInternal: [],
};

/**
 * Everybody the accrual engine pays, and the one write an administrator has.
 *
 * A correction reloads the whole overview rather than patching the row. The
 * server writes the ledger and returns the balance it produced, and the point
 * of reloading is that the figure on screen afterwards is one the server
 * computed, not one the browser worked out by adding.
 *
 * `lastResult` keeps the balance that came back so the caller can show it.
 * Nothing on the server dedupes corrections, so a second submission writes a
 * second row -- that returned figure is the only way to tell what landed.
 *
 * @param {{enabled?: boolean}} [options]
 * @returns {object} The overview, the exclusion groups, and the write.
 */
export const useLeaveBalances = ({ enabled = true } = {}) => {
  const [people, setPeople] = useState([]);
  const [excluded, setExcluded] = useState(EMPTY_EXCLUDED);
  const [profileCount, setProfileCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const [lastResult, setLastResult] = useState(null);

  const load = useCallback(() => {
    if (!enabled) return Promise.resolve();
    setIsLoading(true);
    setLoadError(false);
    return getLeaveBalances()
      .then(({ data }) => {
        setPeople(data?.people ?? []);
        setExcluded({ ...EMPTY_EXCLUDED, ...(data?.excluded ?? {}) });
        setProfileCount(data?.profileCount ?? 0);
      })
      .catch(() => {
        setLoadError(true);
        setPeople([]);
        setExcluded(EMPTY_EXCLUDED);
      })
      .finally(() => setIsLoading(false));
  }, [enabled]);

  useEffect(() => {
    load();
  }, [load]);

  const adjust = useCallback(
    async (payload) => {
      // One at a time, and this guard matters more here than anywhere else in
      // the feature: nothing dedupes corrections, so a double click writes two
      // rows and there is no way to take either back.
      if (isSaving) return false;
      setIsSaving(true);
      setSaveError(null);
      setLastResult(null);
      try {
        const { data } = await adjustLeaveBalance(payload);
        setLastResult(data ?? null);
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

  return {
    people,
    excluded,
    profileCount,
    isLoading,
    loadError,
    isSaving,
    saveError,
    lastResult,
    clearResult: () => setLastResult(null),
    load,
    adjust,
  };
};
