import { useCallback, useEffect, useState } from "react";
import { listNotifiedStages } from "@/api/mentorshipEmailApi";

const NONE = new Map();

// One entry per stage. A stage sent before and scheduled again shows as
// scheduled: the list shows only the latest, a person's timeline the rest.
const entriesOf = (stages, scheduled) => {
  const scheduledAt = new Map(
    (scheduled ?? []).map(({ stage, sendAt }) => [stage, sendAt]),
  );
  const order = [...new Set([...(stages ?? []), ...scheduledAt.keys()])];
  return order.map((stage) => ({
    stage,
    scheduledAt: scheduledAt.get(stage) ?? null,
  }));
};

const byUser = (rows) =>
  new Map(
    (rows ?? []).map(({ userId, stages, scheduled }) => [
      userId,
      entriesOf(stages, scheduled),
    ]),
  );

/**
 * Loads, for each person in a round, the notification stages Kit sent them
 * and the ones confirmed and still to go out, again whenever the round
 * changes. With no round nothing is fetched and the map is empty. `reload`
 * fetches it again in place. A failed load is logged and leaves the map as it
 * was.
 *
 * @param {number|string|null} roundId - The mentorship round's id.
 * @returns {{
 *   stagesByUser: Map<number, Array<{stage: string, scheduledAt: string|null}>>,
 *   reload: () => Promise<void>,
 * }} `scheduledAt` is the send time (ISO) while it is still to go out, null
 *   once sent.
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
