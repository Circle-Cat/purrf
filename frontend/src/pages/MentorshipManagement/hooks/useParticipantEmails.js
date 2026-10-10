import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  getParticipantEmails,
  refreshParticipantEmails,
  replyParticipantEmail,
  sendParticipantEmail,
} from "@/api/mentorshipApi";

// Which (round, person) each conversation object was fetched for, so a late
// result for someone no longer shown is not applied to the page.
const owner = new WeakMap();

const own = (conversation, key) => {
  if (conversation && typeof conversation === "object") {
    owner.set(conversation, key);
  }
  return conversation;
};

/**
 * One person's email conversation in one round, and the calls that change it.
 *
 * Loads again whenever the round or person changes; with no round nothing is
 * fetched. A failed load is logged, leaves no conversation (so the rest of
 * the page still shows) and sets `loadError` until the person changes or a
 * load or refresh brings the conversation. `reload` and `submit` resolve to a conversation and
 * leave applying it to the caller (useComposeEmail does). `submit` sends a
 * reply when the payload names a thread and a new email otherwise. `refresh`
 * applies what it gets and resolves to how many new messages came in (every
 * inbound message counts, bounces and auto-replies included), or null when it
 * failed (after a toast) or the page moved to someone else meanwhile.
 * `setConversation` ignores a conversation fetched for someone no longer shown.
 *
 * @param {number|string|null} roundId
 * @param {number|string} userId
 * @returns {{conversation: object|null, loadError: boolean,
 *   setConversation: (conversation: object) => void,
 *   reload: () => Promise<object>,
 *   submit: (payload: object) => Promise<object>,
 *   refresh: () => Promise<number|null>}}
 */
export const useParticipantEmails = (roundId, userId) => {
  const [conversation, setConversationRaw] = useState(null);
  const [loadError, setLoadError] = useState(false);
  const key = `${roundId}|${userId}`;
  const keyRef = useRef(key);
  keyRef.current = key;

  const setConversation = useCallback((next) => {
    const from = next && typeof next === "object" ? owner.get(next) : undefined;
    if (from !== undefined && from !== keyRef.current) return;
    setConversationRaw(next);
  }, []);

  useEffect(() => {
    setConversationRaw(null);
    setLoadError(false);
    if (!roundId || !userId) return undefined;
    let cancelled = false;
    const asked = `${roundId}|${userId}`;
    getParticipantEmails(roundId, userId)
      .then(({ data }) => {
        if (!cancelled) setConversationRaw(own(data ?? null, asked));
      })
      .catch((err) => {
        console.error("Failed to fetch the emails with this person", err);
        if (!cancelled) setLoadError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [roundId, userId]);

  const reload = useCallback(
    () =>
      getParticipantEmails(roundId, userId).then(({ data }) =>
        own(data, `${roundId}|${userId}`),
      ),
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
      ).then(({ data }) => own(data, `${roundId}|${userId}`)),
    [roundId, userId],
  );

  const refresh = useCallback(async () => {
    const asked = key;
    try {
      const { data } = await refreshParticipantEmails(roundId, userId);
      if (keyRef.current !== asked) return null;
      setConversationRaw(own(data.conversation, asked));
      setLoadError(false);
      return data.newReplies;
    } catch (err) {
      if (keyRef.current !== asked) return null;
      toast.error(err.message);
      return null;
    }
  }, [roundId, userId, key]);

  return { conversation, loadError, setConversation, reload, submit, refresh };
};
