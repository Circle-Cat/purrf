import { useCallback, useEffect, useState } from "react";
import { listNotifiedStages } from "@/api/mentorshipEmailApi";

const NONE = new Map();

// Per stage, its sent entry first (Kit's own wins over a mark by hand), then
// a stage only marked by hand, then the send still to go out. A stage sent
// before and scheduled again shows as both; a person's timeline has the rest.
const entriesOf = (stages, scheduled, manual) => {
  const sent = new Set(stages ?? []);
  const byHand = new Set((manual ?? []).filter((stage) => !sent.has(stage)));
  const scheduledAt = new Map(
    (scheduled ?? []).map(({ stage, sendAt }) => [stage, sendAt]),
  );
  const order = [...new Set([...sent, ...byHand, ...scheduledAt.keys()])];
  return order.flatMap((stage) => [
    ...(sent.has(stage) ? [{ stage, scheduledAt: null }] : []),
    ...(byHand.has(stage) ? [{ stage, scheduledAt: null, manual: true }] : []),
    ...(scheduledAt.has(stage)
      ? [{ stage, scheduledAt: scheduledAt.get(stage) }]
      : []),
  ]);
};

const byUser = (rows) =>
  new Map(
    (rows ?? []).map(({ userId, stages, scheduled, manual }) => [
      userId,
      entriesOf(stages, scheduled, manual),
    ]),
  );

/**
 * Loads, for each person in a round, the notification stages Kit sent them,
 * the ones marked notified by hand, and the ones confirmed and still to go
 * out, again whenever the round changes. With no round nothing is fetched and
 * the map is empty. `reload` fetches it again in place. A failed load is
 * logged and leaves the map as it was.
 *
 * @param {number|string|null} roundId - The mentorship round's id.
 * @returns {{
 *   stagesByUser: Map<number, Array<{stage: string, scheduledAt: string|null, manual?: boolean}>>,
 *   reload: () => Promise<void>,
 * }} `scheduledAt` is the send time (ISO) while it is still to go out, null
 *   once sent. `manual` is true for a stage marked notified by hand and not
 *   sent by Kit.
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
