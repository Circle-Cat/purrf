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
 *   load: () => Promise<void>
 * }}
 */
export const useLeaveLedger = ({
  userId = null,
  page = 1,
  pageSize = 50,
} = {}) => {
  const [entries, setEntries] = useState([]);
  const [totalEntries, setTotalEntries] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const load = useCallback(() => {
    setIsLoading(true);
    setLoadError(false);

    return getLeaveLedger({ userId, page, pageSize })
      .then(({ data }) => {
        setEntries(data?.entries ?? []);
        setTotalEntries(data?.totalEntries ?? data?.total ?? 0);
      })
      .catch(() => {
        setLoadError(true);
        setEntries([]);
        setTotalEntries(0);
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [userId, page, pageSize]);

  useEffect(() => {
    load();
  }, [load]);

  return {
    entries,
    totalEntries,
    isLoading,
    loadError,
    load,
  };
};
