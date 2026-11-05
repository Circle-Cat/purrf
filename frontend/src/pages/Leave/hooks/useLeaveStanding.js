import { useCallback, useEffect, useState } from "react";

import { getLeaveCoverage } from "@/api/leaveApi";

const NOTHING = {
  isCovered: false,
  availableHours: null,
  pendingHours: null,
  usedHours: null,
};

/**
 * Where the viewer stands with the leave feature.
 *
 * Whether it applies is asked of the server rather than inferred from an empty
 * balance: "not covered" and "covered with nothing yet" look identical from
 * here, and the wrong guess shows somebody outside the population a balance of
 * zero, which reads as an entitlement of nothing.
 *
 * The three figures come from the server for the same reason every other
 * figure in this feature does -- available is the balance less what undecided
 * requests already hold, and computing that here would be a second definition
 * free to disagree with the one the overdraft mark uses.
 *
 * Fails closed. Not covered while loading and not covered after an error, so a
 * slow or broken fetch never offers a screen that cannot be served.
 *
 * `enabled` false asks nothing: a feature switched off must not be calling its
 * endpoint on every dashboard load.
 *
 * @param {{enabled?: boolean}} [options]
 * @returns {{isCovered: boolean, availableHours: string|null,
 *   pendingHours: string|null, usedHours: string|null, isLoading: boolean,
 *   loadError: boolean, reload: () => void}}
 */
export const useLeaveStanding = ({ enabled = true } = {}) => {
  const [standing, setStanding] = useState(NOTHING);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const load = useCallback(() => {
    if (!enabled) return Promise.resolve();
    setIsLoading(true);
    setLoadError(false);
    return getLeaveCoverage()
      .then(({ data }) => setStanding({ ...NOTHING, ...(data ?? {}) }))
      .catch(() => {
        setLoadError(true);
        setStanding(NOTHING);
      })
      .finally(() => setIsLoading(false));
  }, [enabled]);

  useEffect(() => {
    load();
  }, [load]);

  const usable = enabled && !isLoading && !loadError;
  return {
    isCovered: usable && Boolean(standing.isCovered),
    availableHours: usable ? standing.availableHours : null,
    pendingHours: usable ? standing.pendingHours : null,
    usedHours: usable ? standing.usedHours : null,
    isLoading,
    loadError,
    reload: load,
  };
};
