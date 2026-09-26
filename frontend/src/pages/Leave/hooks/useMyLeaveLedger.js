import { useCallback, useEffect, useState } from "react";
import { getMyLeaveLedger } from "@/api/leaveApi";

/**
 * The signed-in employee's leave ledger — total hours on record
 * and the append-only entry history.
 *
 * @param {{enabled?: boolean}} [options]
 * @returns {object} ledger data, loading/error state, and retry.
 */
export const useMyLeaveLedger = ({ enabled = true } = {}) => {
  const [data, setData] = useState(undefined);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const load = useCallback(() => {
    if (!enabled) return Promise.resolve();
    setIsLoading(true);
    setLoadError(false);
    return getMyLeaveLedger()
      .then(({ data: ledgerData }) => {
        setData(ledgerData);
      })
      .catch(() => {
        setLoadError(true);
        setData(undefined);
      })
      .finally(() => setIsLoading(false));
  }, [enabled]);

  useEffect(() => {
    load();
  }, [load]);

  return {
    data,
    isLoading,
    loadError,
    load,
  };
};
