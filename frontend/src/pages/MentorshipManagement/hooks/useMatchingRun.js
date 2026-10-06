import { useCallback, useEffect, useState } from "react";
import {
  getMatchingResults,
  getMatchingRun,
  getMatchingUnmatched,
} from "@/api/mentorshipApi";

/**
 * Loads where a round's latest matching run stands, again whenever the round
 * changes. With no round nothing is fetched. `reload` fetches it again in
 * place, keeping what is shown until the answer comes.
 *
 * @param {number|string|null} roundId - The mentorship round's id.
 * @returns {{overview: Object|null, isLoading: boolean, error: boolean,
 *            reload: () => Promise<void>}}
 */
export const useMatchingRun = (roundId) => {
  const [overview, setOverview] = useState(null);
  const [isLoading, setIsLoading] = useState(Boolean(roundId));
  const [error, setError] = useState(false);

  useEffect(() => {
    setOverview(null);
    setError(false);
    if (!roundId) {
      setIsLoading(false);
      return undefined;
    }
    let cancelled = false;
    setIsLoading(true);
    getMatchingRun(roundId)
      .then(({ data }) => {
        if (!cancelled) setOverview(data ?? null);
      })
      .catch((err) => {
        console.error("Failed to fetch the matching run", err);
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [roundId]);

  const reload = useCallback(() => {
    if (!roundId) return Promise.resolve();
    return getMatchingRun(roundId)
      .then(({ data }) => setOverview(data ?? null))
      .catch((err) => {
        console.error("Failed to fetch the matching run", err);
      });
  }, [roundId]);

  return { overview, isLoading, error, reload };
};

/**
 * Loads one page from `load(roundId, {limit, offset, ...})`, again whenever
 * any argument changes; a new `reloadKey` alone fetches the same page again.
 */
const usePage = (load, what, roundId, query, reloadKey) => {
  const [page, setPage] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(false);
  const queryKey = JSON.stringify(query);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(false);
    load(roundId, JSON.parse(queryKey))
      .then(({ data }) => {
        if (!cancelled) setPage(data ?? null);
      })
      .catch((err) => {
        console.error(`Failed to fetch the ${what}`, err);
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [load, what, roundId, queryKey, reloadKey]);

  return { page, isLoading, error };
};

/**
 * Loads one page of a round's matching results, one item per mentee.
 *
 * @param {number|string} roundId - The mentorship round's id.
 * @param {{limit: number, offset: number, matched?: boolean}} query
 * @param {number} [reloadKey] - Change it to fetch the same page again.
 * @returns {{page: Object|null, isLoading: boolean, error: boolean}}
 */
export const useMatchingResults = (
  roundId,
  { limit, offset, matched },
  reloadKey = 0,
) =>
  usePage(
    getMatchingResults,
    "matching results",
    roundId,
    { limit, offset, matched },
    reloadKey,
  );

/**
 * Loads one page of the people a round's matching left without a partner,
 * one item per person, mentees first.
 *
 * @param {number|string} roundId - The mentorship round's id.
 * @param {{limit: number, offset: number}} query
 * @param {number} [reloadKey] - Change it to fetch the same page again.
 * @returns {{page: Object|null, isLoading: boolean, error: boolean}}
 */
export const useMatchingUnmatched = (
  roundId,
  { limit, offset },
  reloadKey = 0,
) =>
  usePage(
    getMatchingUnmatched,
    "unmatched people",
    roundId,
    { limit, offset },
    reloadKey,
  );
