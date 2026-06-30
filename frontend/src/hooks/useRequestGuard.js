import { useCallback, useEffect, useRef } from "react";

/**
 * Guards async fetches against stale-response races and post-unmount updates.
 *
 * Many hooks refetch whenever their inputs change (selected row, search query,
 * page, sort). Without ordering, a slow earlier request can resolve after a
 * newer one and overwrite the newer result. This hook hands out a monotonic id
 * per request; a response should only be applied while its id is still the
 * latest and the component is still mounted.
 *
 * Usage:
 *   const { begin, isCurrent } = useRequestGuard();
 *   const fetchX = useCallback(async () => {
 *     const seq = begin();
 *     const { data } = await api(...);
 *     if (!isCurrent(seq)) return; // superseded or unmounted
 *     setState(data);
 *   }, [...]);
 *
 * @returns {{ begin: () => number, isCurrent: (seq: number) => boolean }}
 *   `begin` starts a new request and returns its id; `isCurrent` reports
 *   whether that id is still the latest and the component is mounted.
 */
export function useRequestGuard() {
  const seqRef = useRef(0);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  // Stable identities so callers can list them in useCallback/useEffect deps
  // without retriggering on every render.
  const begin = useCallback(() => ++seqRef.current, []);
  const isCurrent = useCallback(
    (seq) => mountedRef.current && seq === seqRef.current,
    [],
  );

  return { begin, isCurrent };
}
