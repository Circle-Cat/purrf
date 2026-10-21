import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { getInboxCount } from "@/api/inboxApi";

/**
 * How many Inbox threads need a reply, for the sidebar badge.
 *
 * Refreshes on route change, tab visibility, window focus and the
 * "inbox:changed" window event (dispatched after Inbox write actions). There
 * is deliberately no timer. Does not request at all while `enabled` is false.
 * A failed request clears the count (no number is shown) and is silent.
 *
 * @param {boolean} enabled - Whether the viewer may see the Inbox.
 * @returns {{count: number, refresh: () => Promise<void>}}
 */
export const useInboxCount = (enabled) => {
  const [count, setCount] = useState(0);
  const { pathname } = useLocation();
  // Set synchronously so overlapping triggers (focus plus visibilitychange)
  // share one request.
  const inFlight = useRef(false);

  const refresh = useCallback(async () => {
    if (!enabled || inFlight.current) return;
    inFlight.current = true;
    try {
      const { data } = await getInboxCount();
      setCount(data?.needsReply ?? 0);
    } catch {
      setCount(0);
    } finally {
      inFlight.current = false;
    }
  }, [enabled]);

  useEffect(() => {
    refresh();
  }, [pathname, refresh]);

  useEffect(() => {
    if (!enabled) return undefined;
    const onVisibilityChange = () => {
      if (document.visibilityState === "visible") refresh();
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    window.addEventListener("focus", refresh);
    window.addEventListener("inbox:changed", refresh);
    return () => {
      document.removeEventListener("visibilitychange", onVisibilityChange);
      window.removeEventListener("focus", refresh);
      window.removeEventListener("inbox:changed", refresh);
    };
  }, [enabled, refresh]);

  return { count: enabled ? count : 0, refresh };
};
