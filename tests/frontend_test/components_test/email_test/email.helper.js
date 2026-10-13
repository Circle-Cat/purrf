// Values a swapped read would expose are kept distinct: thread 41 vs message
// ids 410/411, the person's primary vs alternative address, and the alias
// that sends vs the person who receives.

export const messageOf = (overrides = {}) => ({
  messageId: 410,
  direction: "outbound",
  fromAddress: "mentorship@circlecat.org",
  toAddresses: "alice@x.com",
  subject: "Checking in",
  bodyHtml: "<p>How is it going?</p>",
  bodyText: "How is it going?",
  snippet: "How is it going?",
  sentByUserId: 9,
  sentByName: "Dana Wu",
  gmailInternalDate: "2026-10-01T16:00:00Z",
  createdAt: "2026-10-01T16:00:05Z",
  failedRecipients: null,
  inboundKind: null,
  attachments: [],
  ...overrides,
});

export const replyOf = (overrides = {}) =>
  messageOf({
    messageId: 411,
    direction: "inbound",
    fromAddress: "alice@x.com",
    toAddresses: "mentorship@circlecat.org",
    bodyHtml: "<p>All good, thanks</p>",
    bodyText: "All good, thanks",
    snippet: "All good, thanks",
    sentByUserId: null,
    sentByName: null,
    gmailInternalDate: "2026-10-02T17:30:00Z",
    createdAt: "2026-10-02T17:31:00Z",
    inboundKind: "human",
    ...overrides,
  });

export const threadOf = (overrides = {}) => ({
  threadId: 41,
  subject: "Checking in",
  syncedAt: "2026-10-02T17:31:00Z",
  createdAt: "2026-10-01T16:00:05Z",
  messages: [messageOf(), replyOf()],
  needsReply: true,
  openBounce: null,
  replyAlias: "mentorship@circlecat.org",
  replyTo: "alice@x.com",
  ...overrides,
});

export const conversationOf = (overrides = {}) => ({
  threads: [threadOf()],
  defaultTo: "alice@x.com",
  canSend: true,
  senderAddress: "mentorship@circlecat.org",
  recipientOptions: [
    { address: "alice@x.com", label: "Primary contact" },
    { address: "alice.alt@y.org", label: "Alternative" },
  ],
  ...overrides,
});

/** The rejection axios hands back for a reply into a thread that moved on. */
export const threadChangedError = () =>
  Object.assign(new Error("This thread has new messages."), {
    response: {
      status: 409,
      data: {
        success: false,
        message: "This thread has new messages.",
        data: { code: "THREAD_CHANGED" },
      },
    },
  });
