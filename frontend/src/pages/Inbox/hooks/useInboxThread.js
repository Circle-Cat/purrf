import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import {
  archiveInboxThread,
  assignInboxThread,
  getInboxThread,
  moveInboxThread,
  replyToInboxThread,
  unarchiveInboxThread,
  unassignInboxThread,
} from "@/api/inboxApi";
import { useRequestGuard } from "@/hooks/useRequestGuard";

const statusOf = (e) => e?.response?.status;

/**
 * Loads one Inbox thread and exposes its write actions.
 *
 * Every successful write replaces the thread with the returned detail and
 * calls `onChanged`. A 400 while loading means the thread is gone or no
 * longer visible, which calls `onGone`. A 409 on reply sets `stale` and
 * reloads, keeping the caller's draft untouched.
 *
 * @param {number|null} threadId - Selected thread, or null.
 * @param {{onChanged: () => void, onGone: () => void}} callbacks
 * @returns {{thread: object|null, loading: boolean, stale: boolean,
 *   reply: (html: string) => Promise<boolean>, archive: Function,
 *   unarchive: Function, assign: (body: object) => Promise<boolean>,
 *   unassign: () => Promise<boolean>, move: (service: string) => Promise<void>}}
 */
export const useInboxThread = (threadId, { onChanged, onGone }) => {
  const { begin, isCurrent } = useRequestGuard();
  const [thread, setThread] = useState(null);
  const [loading, setLoading] = useState(false);
  const [stale, setStale] = useState(false);

  const load = useCallback(async () => {
    if (threadId == null) return;
    const seq = begin();
    try {
      const { data } = await getInboxThread(threadId);
      if (isCurrent(seq)) setThread(data);
    } catch (e) {
      if (!isCurrent(seq)) return;
      if (statusOf(e) === 400) onGone();
      else toast.error(e.message);
    } finally {
      if (isCurrent(seq)) setLoading(false);
    }
  }, [threadId, begin, isCurrent, onGone]);

  useEffect(() => {
    setThread(null);
    setStale(false);
    setLoading(threadId != null);
    load();
  }, [threadId]); // eslint-disable-line react-hooks/exhaustive-deps

  const write = async (call) => {
    try {
      const { data } = await call();
      setThread(data);
      onChanged();
      return true;
    } catch (e) {
      toast.error(e.message);
      return false;
    }
  };

  const reply = async (body) => {
    try {
      const { data } = await replyToInboxThread(threadId, {
        body,
        lastSeenMessageId: thread.latestMessageId,
      });
      setThread(data);
      setStale(false);
      onChanged();
      return true;
    } catch (e) {
      if (statusOf(e) === 409) {
        setStale(true);
        await load();
      } else {
        toast.error(e.message);
      }
      return false;
    }
  };

  const move = async (service) => {
    if (await write(() => moveInboxThread(threadId, service))) await load();
  };

  return {
    thread,
    loading,
    stale,
    reply,
    archive: () => write(() => archiveInboxThread(threadId)),
    unarchive: () => write(() => unarchiveInboxThread(threadId)),
    assign: (body) => write(() => assignInboxThread(threadId, body)),
    unassign: () => write(() => unassignInboxThread(threadId)),
    move,
  };
};
