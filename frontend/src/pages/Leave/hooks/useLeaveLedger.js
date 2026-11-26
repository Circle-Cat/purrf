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
 *   people: Array<{userId: number, name: string|null, ldap: string|null}>,
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
  // Everyone with history, for the person filter. Kept across a failed or
  // pending load so the filter does not empty while a page is fetched.
  const [people, setPeople] = useState([]);

  const load = useCallback(
    ({ isCancelled } = {}) => {
      setIsLoading(true);
      setLoadError(false);

      return getLeaveLedger({ userId, page, pageSize })
        .then(({ data }) => {
          if (isCancelled?.()) return;

          setEntries(data?.entries ?? []);
          setTotalEntries(data?.totalEntries ?? 0);
          setPeople(data?.people ?? []);
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
    [userId, page, pageSize],
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
    people,
    load: () => load(),
  };
};
