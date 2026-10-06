import { useEffect, useState } from "react";
import { getMatchingResults, getMatchingRun } from "@/api/mentorshipApi";

/**
 * Loads where a round's latest matching run stands, again whenever the round
 * changes. With no round nothing is fetched.
 *
 * @param {number|string|null} roundId - The mentorship round's id.
 * @returns {{overview: Object|null, isLoading: boolean, error: boolean}}
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

  return { overview, isLoading, error };
};

/**
 * Loads one page of a round's matching results.
 *
 * @param {number|string} roundId - The mentorship round's id.
 * @param {{limit: number, offset: number, matched?: boolean}} query
 * @returns {{page: Object|null, isLoading: boolean, error: boolean}}
 */
export const useMatchingResults = (roundId, { limit, offset, matched }) => {
  const [page, setPage] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(false);
    getMatchingResults(roundId, { limit, offset, matched })
      .then(({ data }) => {
        if (!cancelled) setPage(data ?? null);
      })
      .catch((err) => {
        console.error("Failed to fetch the matching results", err);
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [roundId, limit, offset, matched]);

  return { page, isLoading, error };
};
