import { describe, it, expect } from "vitest";
import {
  defaultRecipients,
  isThreadChanged,
  lastMessageId,
  messagesAfter,
  messageTime,
  recipientOptionsOf,
  replySubject,
  sortThreadsByActivity,
  threadActivityAt,
} from "@/components/email/emailThreads";
import {
  conversationOf,
  messageOf,
  replyOf,
  threadChangedError,
  threadOf,
} from "./email.helper";

describe("emailThreads", () => {
  it("dates a message by Gmail first, then by when Purrf stored it", () => {
    expect(messageTime(messageOf())).toBe("2026-10-01T16:00:00Z");
    expect(messageTime(messageOf({ gmailInternalDate: null }))).toBe(
      "2026-10-01T16:00:05Z",
    );
  });

  it("dates a thread by its newest message, else by the thread", () => {
    expect(threadActivityAt(threadOf())).toBe("2026-10-02T17:30:00Z");
    expect(threadActivityAt(threadOf({ messages: [] }))).toBe(
      "2026-10-01T16:00:05Z",
    );
  });

  it("sorts threads newest activity first without touching the input", () => {
    const older = threadOf({
      threadId: 40,
      messages: [
        messageOf({
          messageId: 400,
          gmailInternalDate: "2026-09-01T16:00:00Z",
        }),
      ],
    });
    const newer = threadOf();
    const input = [older, newer];
    expect(sortThreadsByActivity(input).map((t) => t.threadId)).toEqual([
      41, 40,
    ]);
    expect(input.map((t) => t.threadId)).toEqual([40, 41]);
  });

  it("takes the last message as the newest one seen", () => {
    expect(lastMessageId(threadOf())).toBe(411);
    expect(lastMessageId(threadOf({ messages: [] }))).toBeNull();
    expect(lastMessageId(null)).toBeNull();
  });

  it("lists the messages after the one seen", () => {
    const thread = threadOf({
      messages: [messageOf(), replyOf(), replyOf({ messageId: 412 })],
    });
    expect(messagesAfter(thread, 411).map((m) => m.messageId)).toEqual([412]);
    expect(messagesAfter(thread, null).map((m) => m.messageId)).toEqual([
      410, 411, 412,
    ]);
  });

  it("reads a conversation without recipientOptions as its defaultTo", () => {
    expect(
      recipientOptionsOf({ threads: [], defaultTo: "cand@x.com" }),
    ).toEqual([{ address: "cand@x.com", label: null }]);
    expect(recipientOptionsOf({ threads: [], defaultTo: null })).toEqual([]);
    expect(recipientOptionsOf(null)).toEqual([]);
    expect(recipientOptionsOf(conversationOf())).toEqual(
      conversationOf().recipientOptions,
    );
  });

  it("ticks the option matching defaultTo whatever its case", () => {
    const options = conversationOf().recipientOptions;
    expect(defaultRecipients(options, "Alice@X.com")).toEqual(["alice@x.com"]);
    expect(defaultRecipients(options, "nobody@x.com")).toEqual([]);
    expect(defaultRecipients(options, null)).toEqual([]);
  });

  it("puts Re: in front of a subject once", () => {
    expect(replySubject("Checking in")).toBe("Re: Checking in");
    expect(replySubject("Re: Checking in")).toBe("Re: Checking in");
    expect(replySubject(null)).toBe("Re: ");
  });

  it("recognizes only the THREAD_CHANGED conflict", () => {
    expect(isThreadChanged(threadChangedError())).toBe(true);
    expect(
      isThreadChanged({ response: { status: 409, data: { data: null } } }),
    ).toBe(false);
    expect(isThreadChanged(new Error("boom"))).toBe(false);
  });
});
