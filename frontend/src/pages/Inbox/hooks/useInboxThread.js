import { useCallback, useEffect, useRef, useState } from "react";
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
 *   unassign: () => Promise<boolean>, move: (service: string) => Promise<void>,
 *   pending: boolean}}
 */
export const useInboxThread = (threadId, { onChanged, onGone }) => {
  const { begin, isCurrent } = useRequestGuard();
  const [thread, setThread] = useState(null);
  const [loading, setLoading] = useState(false);
  const [stale, setStale] = useState(false);
  const [pendingId, setPendingId] = useState(null);
  const selectedRef = useRef(threadId);
  const busyRef = useRef(null);
  selectedRef.current = threadId;

  const load = useCallback(async () => {
    const seq = begin();
    if (threadId == null) return;
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

  // Runs one write for the thread open now. The response is applied only
  // while that thread is still the open one, and it supersedes any load that
  // started earlier.
  const guarded = async (run) => {
    const id = threadId;
    if (busyRef.current === id) return false;
    busyRef.current = id;
    setPendingId(id);
    try {
      return await run(id, () => selectedRef.current === id);
    } finally {
      if (busyRef.current === id) busyRef.current = null;
      setPendingId((cur) => (cur === id ? null : cur));
    }
  };

  const apply = (data) => {
    begin();
    setThread(data);
    setLoading(false);
  };

  const write = (call) =>
    guarded(async (id, stillOpen) => {
      try {
        const { data } = await call(id);
        if (stillOpen()) apply(data);
        onChanged();
        return true;
      } catch (e) {
        if (stillOpen()) toast.error(e.message);
        return false;
      }
    });

  const reply = (body) =>
    guarded(async (id, stillOpen) => {
      try {
        const { data } = await replyToInboxThread(id, {
          body,
          lastSeenMessageId: thread.latestMessageId,
        });
        if (stillOpen()) {
          apply(data);
          setStale(false);
        }
        onChanged();
        return true;
      } catch (e) {
        if (!stillOpen()) return false;
        if (statusOf(e) === 409) {
          setStale(true);
          await load();
        } else {
          toast.error(e.message);
        }
        return false;
      }
    });

  const move = async (service) => {
    if (await write((id) => moveInboxThread(id, service))) {
      if (selectedRef.current === threadId) await load();
    }
  };

  return {
    thread,
    loading,
    stale,
    pending: pendingId != null && pendingId === threadId,
    reply,
    archive: () => write((id) => archiveInboxThread(id)),
    unarchive: () => write((id) => unarchiveInboxThread(id)),
    assign: (body) => write((id) => assignInboxThread(id, body)),
    unassign: () => write((id) => unassignInboxThread(id)),
    move,
  };
};
