import { useCallback, useRef, useState } from "react";
import { toast } from "sonner";
import { listUserAssignments } from "@/api/trainingApi";

/**
 * The read behind expanding one person's row: what courses they hold.
 *
 * One row is open at a time, and each person is read once. The answer does
 * not change while the operator looks at it, and re-reading it on every
 * collapse would spend a request per glance down a page.
 *
 * @returns {{expandedUserId: ?number, rowsByUserId: Object<number, Array>,
 *   loadingUserId: ?number, toggle: (userId: number) => void}}
 */
export function useUserAssignments() {
  const [expandedUserId, setExpandedUserId] = useState(null);
  const [rowsByUserId, setRowsByUserId] = useState({});
  const [loadingUserId, setLoadingUserId] = useState(null);
  // A second click while the first read is in flight must not fire a second
  // request; the row is already opening.
  const inFlight = useRef(new Set());

  const toggle = useCallback(
    (userId) => {
      setExpandedUserId((current) => (current === userId ? null : userId));

      const alreadyRead = Object.prototype.hasOwnProperty.call(
        rowsByUserId,
        userId,
      );
      if (alreadyRead || inFlight.current.has(userId)) return;

      inFlight.current.add(userId);
      setLoadingUserId(userId);
      listUserAssignments(userId)
        .then(({ data }) =>
          setRowsByUserId((current) => ({
            ...current,
            [userId]: data?.rows ?? [],
          })),
        )
        .catch((error) => {
          toast.error(error.message);
          // Left out of the cache on purpose: the next expand should retry
          // rather than show an empty list as though the person held nothing.
          setExpandedUserId((current) => (current === userId ? null : current));
        })
        .finally(() => {
          inFlight.current.delete(userId);
          setLoadingUserId((current) => (current === userId ? null : current));
        });
    },
    [rowsByUserId],
  );

  return { expandedUserId, rowsByUserId, loadingUserId, toggle };
}
