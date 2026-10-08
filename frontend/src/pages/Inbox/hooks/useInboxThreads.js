import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { listInboxThreads } from "@/api/inboxApi";
import { useRequestGuard } from "@/hooks/useRequestGuard";

const EMPTY = {
  threads: [],
  counts: { needsReply: 0 },
  services: [],
};

/**
 * Loads the Inbox thread list for the given filters; unset filters are not
 * sent. Responses from superseded requests are dropped.
 *
 * @param {{service?: string, needsReply?: boolean, archived?: boolean,
 *   q?: string, userId?: string}} filters
 * @returns {{data: object, loading: boolean, refresh: () => Promise<void>}}
 */
export const useInboxThreads = ({
  service,
  needsReply,
  archived,
  q,
  userId,
}) => {
  const { begin, isCurrent } = useRequestGuard();
  const [data, setData] = useState(EMPTY);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const params = {};
    if (service) params.service = service;
    if (needsReply) params.needsReply = true;
    if (archived) params.archived = true;
    if (q) params.q = q;
    if (userId) params.userId = Number(userId);
    const seq = begin();
    try {
      const res = await listInboxThreads(params);
      if (isCurrent(seq)) setData(res.data ?? EMPTY);
    } catch (e) {
      if (isCurrent(seq)) toast.error(e.message);
    } finally {
      if (isCurrent(seq)) setLoading(false);
    }
  }, [service, needsReply, archived, q, userId, begin, isCurrent]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { data, loading, refresh };
};
