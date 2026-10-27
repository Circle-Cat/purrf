import { useCallback, useEffect, useState } from "react";
import { getLeaveLedger } from "@/api/leaveApi";

/**
 * Fetches and manages state for the leave balance history ledger.
 *
 * Automatically refetches whenever `userId`, `page`, or `pageSize` changes.
 *
 * @param {{ userId?: number | string | null, page?: number, pageSize?: number }} [options]
 * @returns {{
 *   entries: Array,
 *   totalEntries: number,
 *   isLoading: boolean,
 *   loadError: boolean,
 *   load: (opts?: { isCancelled?: () => boolean }) => Promise<void>
 * }}
 */
export const useLeaveLedger = ({
  userId = null,
  page = 1,
  pageSize = 50,
  enabled = true,
} = {}) => {
  const [entries, setEntries] = useState([]);
  const [totalEntries, setTotalEntries] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const load = useCallback(
    ({ isCancelled } = {}) => {
      if (!enabled) return Promise.resolve();

      setIsLoading(true);
      setLoadError(false);

      return getLeaveLedger({ userId, page, pageSize })
        .then(({ data }) => {
          if (isCancelled?.()) return;

          setEntries(data?.entries ?? []);
          setTotalEntries(data?.totalEntries ?? 0);
        })
        .catch(() => {
          if (isCancelled?.()) return;

          setLoadError(true);
          setEntries([]);
          setTotalEntries(0);
        })
        .finally(() => {
          if (isCancelled?.()) return;

          setIsLoading(false);
        });
    },
    [userId, page, pageSize, enabled],
  );

  useEffect(() => {
    let ignore = false;

    load({ isCancelled: () => ignore });

    return () => {
      ignore = true;
    };
  }, [load]);

  return {
    entries,
    totalEntries,
    isLoading,
    loadError,
    load,
  };
};
