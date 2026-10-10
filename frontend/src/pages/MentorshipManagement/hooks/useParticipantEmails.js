import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  getParticipantEmails,
  refreshParticipantEmails,
  replyParticipantEmail,
  sendParticipantEmail,
} from "@/api/mentorshipApi";

/**
 * One person's email conversation in one round, and the calls that change it.
 *
 * Loads again whenever the round or person changes; with no round nothing is
 * fetched. A failed load is logged and leaves no conversation, so the rest of
 * the page still shows. `reload` and `submit` resolve to a conversation and
 * leave applying it to the caller (useComposeEmail does). `submit` sends a
 * reply when the payload names a thread and a new email otherwise. `refresh`
 * applies what it gets and resolves to how many new messages came in (every
 * inbound message counts, bounces and auto-replies included), or null when it
 * failed (after a toast) or the page moved to someone else meanwhile.
 *
 * @param {number|string|null} roundId
 * @param {number|string} userId
 * @returns {{conversation: object|null,
 *   setConversation: (conversation: object) => void,
 *   reload: () => Promise<object>,
 *   submit: (payload: object) => Promise<object>,
 *   refresh: () => Promise<number|null>}}
 */
export const useParticipantEmails = (roundId, userId) => {
  const [conversation, setConversation] = useState(null);
  const key = `${roundId}|${userId}`;
  const keyRef = useRef(key);
  keyRef.current = key;

  useEffect(() => {
    setConversation(null);
    if (!roundId || !userId) return undefined;
    let cancelled = false;
    getParticipantEmails(roundId, userId)
      .then(({ data }) => {
        if (!cancelled) setConversation(data ?? null);
      })
      .catch((err) => {
        console.error("Failed to fetch the emails with this person", err);
      });
    return () => {
      cancelled = true;
    };
  }, [roundId, userId]);

  const reload = useCallback(
    () => getParticipantEmails(roundId, userId).then(({ data }) => data),
    [roundId, userId],
  );

  const submit = useCallback(
    (payload) =>
      (payload.threadId != null
        ? replyParticipantEmail(roundId, userId, payload.threadId, {
            body: payload.body,
            lastSeenMessageId: payload.lastSeenMessageId,
          })
        : sendParticipantEmail(roundId, userId, {
            to: payload.to,
            subject: payload.subject,
            body: payload.body,
          })
      ).then(({ data }) => data),
    [roundId, userId],
  );

  const refresh = useCallback(async () => {
    const asked = key;
    try {
      const { data } = await refreshParticipantEmails(roundId, userId);
      if (keyRef.current !== asked) return null;
      setConversation(data.conversation);
      return data.newReplies;
    } catch (err) {
      toast.error(err.message);
      return null;
    }
  }, [roundId, userId, key]);

  return { conversation, setConversation, reload, submit, refresh };
};
