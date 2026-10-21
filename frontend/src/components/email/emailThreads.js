/** The 409 code a reply gets when its thread moved on since it was loaded. */
export const THREAD_CHANGED = "THREAD_CHANGED";

const millis = (iso) => (iso ? Date.parse(iso) || 0 : 0);

/**
 * When a message happened: Gmail's own date when known, else when Purrf
 * stored it.
 *
 * @param {{gmailInternalDate?: string|null, createdAt?: string|null}} message
 * @returns {string|null}
 */
export const messageTime = (message) =>
  message.gmailInternalDate ?? message.createdAt ?? null;

/**
 * The time of a thread's newest message, or of the thread itself when it has
 * none.
 *
 * @param {{messages?: object[], createdAt?: string|null}} thread
 * @returns {string|null}
 */
export const threadActivityAt = (thread) => {
  const times = (thread.messages ?? []).map(messageTime).filter(Boolean);
  if (times.length === 0) return thread.createdAt ?? null;
  return times.reduce((latest, iso) =>
    millis(iso) > millis(latest) ? iso : latest,
  );
};

/**
 * Threads with the most recent activity first, as a new array.
 *
 * @param {object[]} threads
 * @returns {object[]}
 */
export const sortThreadsByActivity = (threads) =>
  [...threads].sort(
    (a, b) => millis(threadActivityAt(b)) - millis(threadActivityAt(a)),
  );

/**
 * The newest message of a thread as loaded: messages arrive oldest first, the
 * order the backend compares `lastSeenMessageId` against.
 *
 * @param {{messages?: object[]}|null} thread
 * @returns {number|null}
 */
export const lastMessageId = (thread) =>
  thread?.messages?.at(-1)?.messageId ?? null;

/**
 * The messages after `messageId`, or all of them when it is not in the thread.
 *
 * @param {{messages?: object[]}} thread
 * @param {number|null} messageId
 * @returns {object[]}
 */
export const messagesAfter = (thread, messageId) => {
  const messages = thread.messages ?? [];
  return messages.slice(
    messages.findIndex((m) => m.messageId === messageId) + 1,
  );
};

/**
 * Who a new email may go to. A conversation from a backend that does not send
 * `recipientOptions` yet offers its `defaultTo` alone.
 *
 * @param {{recipientOptions?: {address: string, label: string}[],
 *          defaultTo?: string|null}|null} conversation
 * @returns {{address: string, label: string|null}[]}
 */
export const recipientOptionsOf = (conversation) => {
  if (conversation?.recipientOptions) return conversation.recipientOptions;
  return conversation?.defaultTo
    ? [{ address: conversation.defaultTo, label: null }]
    : [];
};

/**
 * The addresses ticked when the composer opens: the option matching
 * `defaultTo`, compared case-insensitively as the backend does.
 *
 * @param {{address: string}[]} options
 * @param {string|null} defaultTo
 * @returns {string[]}
 */
export const defaultRecipients = (options, defaultTo) => {
  if (!defaultTo) return [];
  const wanted = defaultTo.toLowerCase();
  const hit = options.find((o) => o.address.toLowerCase() === wanted);
  return hit ? [hit.address] : [];
};

/**
 * The subject a reply goes out under.
 *
 * @param {string|null} subject
 * @returns {string}
 */
export const replySubject = (subject) => {
  const base = subject ?? "";
  return base.startsWith("Re:") ? base : `Re: ${base}`;
};

/**
 * Whether a failed reply was refused because the thread changed.
 *
 * @param {unknown} error
 * @returns {boolean}
 */
export const isThreadChanged = (error) =>
  error?.response?.status === 409 &&
  error?.response?.data?.data?.code === THREAD_CHANGED;
