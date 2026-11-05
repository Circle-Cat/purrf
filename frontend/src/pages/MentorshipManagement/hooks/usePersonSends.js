import { useEffect, useState } from "react";
import { listPersonSends } from "@/api/mentorshipEmailApi";

const NONE = [];

/**
 * Loads one person's Kit sends in a round, again whenever the round or person
 * changes. With no round nothing is fetched and the list is empty. A failed
 * load is logged and leaves the list empty, so the rest of the page still
 * shows.
 *
 * @param {number|string|null} roundId - The mentorship round's id.
 * @param {number|string} userId - The person's user id.
 * @returns {Array<{sendId: number, stage: string, subject: string,
 *   delivered: boolean, reason: string|null, at: string}>}
 */
export const usePersonSends = (roundId, userId) => {
  const [sends, setSends] = useState(NONE);

  useEffect(() => {
    setSends(NONE);
    if (!roundId || !userId) return undefined;
    let cancelled = false;
    listPersonSends(roundId, userId)
      .then((rows) => {
        if (!cancelled) setSends(rows ?? NONE);
      })
      .catch((err) => {
        console.error("Failed to fetch the sends to this person", err);
      });
    return () => {
      cancelled = true;
    };
  }, [roundId, userId]);

  return sends;
};
