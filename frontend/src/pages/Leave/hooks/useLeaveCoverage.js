import { useCallback, useEffect, useState } from "react";

import { getLeaveCoverage } from "@/api/leaveApi";

/**
 * Whether the leave feature applies to the current viewer.
 *
 * Asked of the server rather than inferred from an empty balance: "not
 * covered" and "covered with nothing yet" look identical from here, and the
 * wrong guess shows somebody outside the population a balance of zero, which
 * reads as an entitlement of nothing.
 *
 * Fails closed. False while loading and false after an error, so a slow or
 * broken fetch never offers a screen that cannot be served. The cost is a card
 * appearing a moment late.
 *
 * `enabled` false asks nothing: a feature switched off must not be calling its
 * endpoint on every dashboard load.
 *
 * @param {{enabled?: boolean}} [options]
 * @returns {{isCovered: boolean, isLoading: boolean, loadError: boolean}}
 */
export const useLeaveCoverage = ({ enabled = true } = {}) => {
  const [isCovered, setIsCovered] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const load = useCallback(() => {
    if (!enabled) return Promise.resolve();
    setIsLoading(true);
    setLoadError(false);
    return getLeaveCoverage()
      .then(({ data }) => setIsCovered(Boolean(data?.isCovered)))
      .catch(() => {
        setLoadError(true);
        setIsCovered(false);
      })
      .finally(() => setIsLoading(false));
  }, [enabled]);

  useEffect(() => {
    load();
  }, [load]);

  return {
    isCovered: enabled && !isLoading && !loadError && isCovered,
    isLoading,
    loadError,
  };
};
