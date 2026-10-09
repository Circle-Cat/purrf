import { useCallback, useEffect, useState } from "react";
import { listNotifiedStages } from "@/api/mentorshipEmailApi";

const NONE = new Map();

const byUser = (rows) =>
  new Map((rows ?? []).map(({ userId, stages }) => [userId, stages ?? []]));

/**
 * Loads which notification stages each person was actually sent in a round,
 * again whenever the round changes. With no round nothing is fetched and the
 * map is empty. `reload` fetches it again in place. A failed load is logged
 * and leaves the map as it was.
 *
 * @param {number|string|null} roundId - The mentorship round's id.
 * @returns {{stagesByUser: Map<number, string[]>, reload: () => Promise<void>}}
 */
export const useNotifiedStages = (roundId) => {
  const [stagesByUser, setStagesByUser] = useState(NONE);

  useEffect(() => {
    setStagesByUser(NONE);
    if (!roundId) return undefined;
    let cancelled = false;
    listNotifiedStages(roundId)
      .then((rows) => {
        if (!cancelled) setStagesByUser(byUser(rows));
      })
      .catch((err) => {
        console.error("Failed to fetch the notified stages", err);
      });
    return () => {
      cancelled = true;
    };
  }, [roundId]);

  const reload = useCallback(() => {
    if (!roundId) return Promise.resolve();
    return listNotifiedStages(roundId)
      .then((rows) => setStagesByUser(byUser(rows)))
      .catch((err) => {
        console.error("Failed to fetch the notified stages", err);
      });
  }, [roundId]);

  return { stagesByUser, reload };
};
