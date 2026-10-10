import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { toast } from "sonner";
import { useParticipantEmails } from "@/pages/MentorshipManagement/hooks/useParticipantEmails";
import {
  getParticipantEmails,
  refreshParticipantEmails,
  replyParticipantEmail,
  sendParticipantEmail,
} from "@/api/mentorshipApi";
import { conversationOf } from "../../../components_test/email_test/email.helper";

vi.mock("@/api/mentorshipApi", () => ({
  getParticipantEmails: vi.fn(),
  sendParticipantEmail: vi.fn(),
  replyParticipantEmail: vi.fn(),
  refreshParticipantEmails: vi.fn(),
}));

describe("useParticipantEmails", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(toast, "error").mockImplementation(() => {});
    getParticipantEmails.mockResolvedValue({ data: conversationOf() });
  });

  it("loads the person's conversation in the round", async () => {
    const { result } = renderHook(() => useParticipantEmails("7", "3104"));
    await waitFor(() =>
      expect(result.current.conversation).toEqual(conversationOf()),
    );
    expect(getParticipantEmails).toHaveBeenCalledWith("7", "3104");
  });

  it("fetches nothing without a round", () => {
    const { result } = renderHook(() => useParticipantEmails(null, "3104"));
    expect(getParticipantEmails).not.toHaveBeenCalled();
    expect(result.current.conversation).toBeNull();
  });

  it("logs a failed load and leaves no conversation", async () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    getParticipantEmails.mockRejectedValue(new Error("network"));
    const { result } = renderHook(() => useParticipantEmails("7", "3104"));
    await waitFor(() => expect(error).toHaveBeenCalled());
    expect(result.current.conversation).toBeNull();
    error.mockRestore();
  });

  it("sends a new email to the send endpoint", async () => {
    sendParticipantEmail.mockResolvedValue({ data: conversationOf() });
    const { result } = renderHook(() => useParticipantEmails("7", "3104"));
    let returned;
    await act(async () => {
      returned = await result.current.submit({
        to: ["alice@x.com"],
        subject: "Checking in",
        body: "Hi",
        threadId: null,
      });
    });
    expect(sendParticipantEmail).toHaveBeenCalledWith("7", "3104", {
      to: ["alice@x.com"],
      subject: "Checking in",
      body: "Hi",
    });
    expect(replyParticipantEmail).not.toHaveBeenCalled();
    expect(returned).toEqual(conversationOf());
  });

  it("sends a reply to the reply endpoint", async () => {
    replyParticipantEmail.mockResolvedValue({ data: conversationOf() });
    const { result } = renderHook(() => useParticipantEmails("7", "3104"));
    await act(async () => {
      await result.current.submit({
        to: ["alice@x.com"],
        subject: "Re: Checking in",
        body: "Thanks",
        threadId: 41,
        lastSeenMessageId: 411,
      });
    });
    expect(replyParticipantEmail).toHaveBeenCalledWith("7", "3104", 41, {
      body: "Thanks",
      lastSeenMessageId: 411,
    });
    expect(sendParticipantEmail).not.toHaveBeenCalled();
  });

  it("reloads without touching state itself", async () => {
    const { result } = renderHook(() => useParticipantEmails("7", "3104"));
    await waitFor(() => expect(result.current.conversation).not.toBeNull());
    const fresh = conversationOf({ threads: [] });
    getParticipantEmails.mockResolvedValueOnce({ data: fresh });
    let returned;
    await act(async () => {
      returned = await result.current.reload();
    });
    expect(returned).toEqual(fresh);
    expect(result.current.conversation).toEqual(conversationOf());
  });

  it("refreshes, keeps the new conversation and returns the count", async () => {
    const fresh = conversationOf({ defaultTo: "alice.alt@y.org" });
    refreshParticipantEmails.mockResolvedValue({
      data: { conversation: fresh, newReplies: 2 },
    });
    const { result } = renderHook(() => useParticipantEmails("7", "3104"));
    let count;
    await act(async () => {
      count = await result.current.refresh();
    });
    expect(refreshParticipantEmails).toHaveBeenCalledWith("7", "3104");
    expect(count).toBe(2);
    expect(result.current.conversation).toEqual(fresh);
  });

  it("toasts a failed refresh and returns null", async () => {
    refreshParticipantEmails.mockRejectedValue(new Error("Gmail is down"));
    const { result } = renderHook(() => useParticipantEmails("7", "3104"));
    let count;
    await act(async () => {
      count = await result.current.refresh();
    });
    expect(count).toBeNull();
    expect(toast.error).toHaveBeenCalledWith("Gmail is down");
  });

  describe("when the person changes mid-flight", () => {
    const deferred = () => {
      let resolve;
      let reject;
      const promise = new Promise((res, rej) => {
        resolve = res;
        reject = rej;
      });
      return { promise, resolve, reject };
    };
    const forB = conversationOf({ defaultTo: "bob@y.org" });
    const forA = conversationOf({ defaultTo: "alice@x.com" });

    const showB = async () => {
      getParticipantEmails.mockImplementation((_r, u) =>
        Promise.resolve({ data: u === "B" ? forB : forA }),
      );
      const hook = renderHook(({ u }) => useParticipantEmails("7", u), {
        initialProps: { u: "A" },
      });
      await waitFor(() => expect(hook.result.current.conversation).toBe(forA));
      return hook;
    };
    const moveToB = async (hook) => {
      hook.rerender({ u: "B" });
      await waitFor(() => expect(hook.result.current.conversation).toBe(forB));
    };

    it("ignores a late submit result for the previous person", async () => {
      const late = deferred();
      sendParticipantEmail.mockReturnValue(late.promise);
      const hook = await showB();
      let pending;
      act(() => {
        pending = hook.result.current.submit({
          to: ["a"],
          subject: "s",
          body: "b",
          threadId: null,
        });
      });
      await moveToB(hook);
      late.resolve({ data: conversationOf({ defaultTo: "late@x.com" }) });
      const returned = await pending;
      act(() => hook.result.current.setConversation(returned));
      expect(hook.result.current.conversation).toBe(forB);
    });

    it("ignores a late reload result for the previous person", async () => {
      const hook = await showB();
      const late = deferred();
      getParticipantEmails.mockReturnValueOnce(late.promise);
      let pending;
      act(() => {
        pending = hook.result.current.reload();
      });
      await moveToB(hook);
      late.resolve({ data: conversationOf({ defaultTo: "late@x.com" }) });
      const returned = await pending;
      act(() => hook.result.current.setConversation(returned));
      expect(hook.result.current.conversation).toBe(forB);
    });

    it("returns null for a late refresh without changing state or toasting", async () => {
      const late = deferred();
      refreshParticipantEmails.mockReturnValue(late.promise);
      const hook = await showB();
      let pending;
      act(() => {
        pending = hook.result.current.refresh();
      });
      await moveToB(hook);
      late.resolve({
        data: {
          conversation: conversationOf({ defaultTo: "late@x.com" }),
          newReplies: 3,
        },
      });
      expect(await pending).toBeNull();
      expect(hook.result.current.conversation).toBe(forB);
      expect(toast.error).not.toHaveBeenCalled();
    });

    it("does not toast a late refresh failure for the previous person", async () => {
      const late = deferred();
      refreshParticipantEmails.mockReturnValue(late.promise);
      const hook = await showB();
      let pending;
      act(() => {
        pending = hook.result.current.refresh();
      });
      await moveToB(hook);
      late.reject(new Error("Gmail is down"));
      expect(await pending).toBeNull();
      expect(toast.error).not.toHaveBeenCalled();
    });

    it("still applies a result for the person on screen", async () => {
      const next = conversationOf({ defaultTo: "new@x.com" });
      sendParticipantEmail.mockResolvedValue({ data: next });
      const hook = await showB();
      let returned;
      await act(async () => {
        returned = await hook.result.current.submit({
          to: ["a"],
          subject: "s",
          body: "b",
          threadId: null,
        });
      });
      act(() => hook.result.current.setConversation(returned));
      expect(hook.result.current.conversation).toBe(next);
    });
  });
});
