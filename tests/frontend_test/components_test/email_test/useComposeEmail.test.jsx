import { act, renderHook } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { toast } from "sonner";
import { useComposeEmail } from "@/components/email/useComposeEmail";
import { isThreadChanged } from "@/components/email/emailThreads";
import {
  conversationOf,
  messageOf,
  replyOf,
  threadChangedError,
  threadOf,
} from "./email.helper";

const setup = () => {
  const submit = vi.fn().mockResolvedValue(conversationOf());
  const reload = vi.fn();
  const onConversation = vi.fn();
  const hook = renderHook(() =>
    useComposeEmail({ submit, reload, onConversation }),
  );
  return { hook, submit, reload, onConversation };
};

const NEW_EMAIL = {
  to: ["alice@x.com"],
  subject: "Hi",
  body: "Hello",
  threadId: null,
};
const REPLY = {
  to: ["alice@x.com"],
  subject: "Re: Checking in",
  body: "Thanks",
  threadId: 41,
};

describe("useComposeEmail", () => {
  beforeEach(() => {
    vi.spyOn(toast, "success").mockImplementation(() => {});
    vi.spyOn(toast, "error").mockImplementation(() => {});
  });

  it("sends a new email as given and hands back the conversation", async () => {
    const { hook, submit, onConversation } = setup();
    act(() => hook.result.current.openCompose());
    expect(hook.result.current.dialogProps.open).toBe(true);
    expect(hook.result.current.dialogProps.replyThread).toBeNull();

    await act(async () => {
      await hook.result.current.dialogProps.onSend(NEW_EMAIL);
    });

    expect(submit).toHaveBeenCalledWith(NEW_EMAIL);
    expect(onConversation).toHaveBeenCalledWith(conversationOf());
    expect(toast.success).toHaveBeenCalledWith("Email sent.");
    expect(hook.result.current.dialogProps.sending).toBe(false);
  });

  it("replies with the newest message of the thread as opened", async () => {
    const { hook, submit } = setup();
    act(() => hook.result.current.openReply(threadOf()));
    expect(hook.result.current.dialogProps.replyThread.threadId).toBe(41);

    await act(async () => {
      await hook.result.current.dialogProps.onSend(REPLY);
    });

    expect(submit).toHaveBeenCalledWith({ ...REPLY, lastSeenMessageId: 411 });
  });

  it("on THREAD_CHANGED reloads, moves the reply onto the fresh thread and lists what is new", async () => {
    const { hook, submit, reload, onConversation } = setup();
    const newer = replyOf({ messageId: 412, bodyText: "One more thing" });
    const fresh = conversationOf({
      threads: [threadOf({ messages: [messageOf(), replyOf(), newer] })],
    });
    submit.mockRejectedValueOnce(threadChangedError());
    reload.mockResolvedValue(fresh);
    act(() => hook.result.current.openReply(threadOf()));

    let caught;
    await act(async () => {
      caught = await hook.result.current.dialogProps
        .onSend(REPLY)
        .catch((e) => e);
    });

    expect(isThreadChanged(caught)).toBe(true);
    expect(reload).toHaveBeenCalledTimes(1);
    expect(onConversation).toHaveBeenCalledWith(fresh);
    expect(toast.error).not.toHaveBeenCalled();
    expect(hook.result.current.dialogProps.open).toBe(true);
    expect(hook.result.current.dialogProps.replyThread.messages).toHaveLength(
      3,
    );
    expect(
      hook.result.current.dialogProps.staleMessages.map((m) => m.messageId),
    ).toEqual([412]);

    await act(async () => {
      await hook.result.current.dialogProps.onSend(REPLY);
    });
    expect(submit).toHaveBeenLastCalledWith({
      ...REPLY,
      lastSeenMessageId: 412,
    });
    expect(hook.result.current.dialogProps.staleMessages).toEqual([]);
  });

  it("toasts any other failure and does not reload", async () => {
    const { hook, submit, reload } = setup();
    submit.mockRejectedValueOnce(new Error("Gmail is down"));
    act(() => hook.result.current.openReply(threadOf()));

    await act(async () => {
      await hook.result.current.dialogProps.onSend(REPLY).catch(() => {});
    });

    expect(toast.error).toHaveBeenCalledWith("Gmail is down");
    expect(reload).not.toHaveBeenCalled();
    expect(hook.result.current.dialogProps.staleMessages).toEqual([]);
  });

  it("refuses a second send while the first is in flight", async () => {
    const { hook, submit } = setup();
    let finish;
    submit.mockReturnValueOnce(
      new Promise((resolve) => {
        finish = resolve;
      }),
    );
    act(() => hook.result.current.openCompose());

    let first;
    act(() => {
      first = hook.result.current.dialogProps.onSend(NEW_EMAIL);
    });
    await act(async () => {
      await expect(
        hook.result.current.dialogProps.onSend(NEW_EMAIL),
      ).rejects.toThrow("A send is already in flight.");
    });
    expect(submit).toHaveBeenCalledTimes(1);

    await act(async () => {
      finish(conversationOf());
      await first;
    });
  });

  it("starts a reply with no stale messages after a stale one was closed", async () => {
    const { hook, submit, reload } = setup();
    submit.mockRejectedValueOnce(threadChangedError());
    reload.mockResolvedValue(
      conversationOf({
        threads: [
          threadOf({
            messages: [messageOf(), replyOf(), replyOf({ messageId: 412 })],
          }),
        ],
      }),
    );
    act(() => hook.result.current.openReply(threadOf()));
    await act(async () => {
      await hook.result.current.dialogProps.onSend(REPLY).catch(() => {});
    });
    expect(hook.result.current.dialogProps.staleMessages).toHaveLength(1);

    act(() => hook.result.current.dialogProps.onOpenChange(false));
    act(() => hook.result.current.openReply(threadOf()));
    expect(hook.result.current.dialogProps.staleMessages).toEqual([]);
  });
});
