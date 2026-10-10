import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  isThreadChanged,
  lastMessageId,
  messagesAfter,
} from "@/components/email/emailThreads";

const NO_MESSAGES = [];

/**
 * Drives ComposeEmailDialog for one conversation: whether it is open, which
 * thread a reply goes into, the send, and a thread that moved on meanwhile.
 *
 * `submit` gets the dialog's payload, plus `lastSeenMessageId` on a reply
 * (the newest message of the thread as the sender opened it), and resolves to
 * the updated conversation, which goes to `onConversation`. A reply refused
 * because the thread changed reloads the conversation, moves the reply onto
 * the reloaded thread and lists the messages the sender has not seen; sending
 * again then goes out as is. Any other failure toasts. Every failure rejects,
 * which keeps the dialog open with its draft. A reloaded conversation that no
 * longer holds the thread closes the dialog with a toast.
 *
 * `contextKey` names whose conversation this is (an application, a person in
 * a round). When it changes the dialog closes and the reply and stale
 * messages are dropped, and a send still in flight for the old key no longer
 * touches the conversation or the dialog.
 *
 * @param {{submit: (payload: object) => Promise<object>,
 *          reload: () => Promise<object>,
 *          onConversation: (conversation: object) => void,
 *          contextKey?: unknown}} options
 * @returns {{openCompose: () => void, openReply: (thread: object) => void,
 *   dialogProps: {open: boolean, onOpenChange: (open: boolean) => void,
 *     replyThread: object|null, staleMessages: object[],
 *     onSend: (payload: object) => Promise<void>, sending: boolean}}}
 */
export const useComposeEmail = ({
  submit,
  reload,
  onConversation,
  contextKey,
}) => {
  const [open, setOpen] = useState(false);
  const [replyThread, setReplyThread] = useState(null);
  const [staleMessages, setStaleMessages] = useState(NO_MESSAGES);
  const [sending, setSending] = useState(false);
  const busyRef = useRef(false);
  const contextRef = useRef(contextKey);

  useEffect(() => {
    if (contextRef.current === contextKey) return;
    contextRef.current = contextKey;
    setOpen(false);
    setReplyThread(null);
    setStaleMessages(NO_MESSAGES);
  }, [contextKey]);

  const openCompose = () => {
    setReplyThread(null);
    setStaleMessages(NO_MESSAGES);
    setOpen(true);
  };

  const openReply = (thread) => {
    setReplyThread(thread);
    setStaleMessages(NO_MESSAGES);
    setOpen(true);
  };

  const showWhatChanged = async (threadId, lastSeen, startedIn) => {
    let fresh;
    try {
      fresh = await reload();
    } catch (error) {
      toast.error(error.message);
      return;
    }
    if (contextRef.current !== startedIn) return;
    onConversation(fresh);
    const thread = fresh?.threads?.find((t) => t.threadId === threadId);
    if (!thread) {
      toast.error("This thread is no longer available.");
      setOpen(false);
      return;
    }
    setReplyThread(thread);
    setStaleMessages(messagesAfter(thread, lastSeen));
  };

  const onSend = async (payload) => {
    if (busyRef.current) throw new Error("A send is already in flight.");
    busyRef.current = true;
    setSending(true);
    const lastSeen = replyThread ? lastMessageId(replyThread) : null;
    const startedIn = contextRef.current;
    let conversation;
    try {
      conversation = await submit(
        replyThread ? { ...payload, lastSeenMessageId: lastSeen } : payload,
      );
    } catch (error) {
      if (replyThread && isThreadChanged(error)) {
        await showWhatChanged(replyThread.threadId, lastSeen, startedIn);
      } else {
        toast.error(error.message);
      }
      throw error;
    } finally {
      busyRef.current = false;
      setSending(false);
    }
    toast.success("Email sent.");
    // Rejecting leaves alone whatever dialog the new context has open.
    if (contextRef.current !== startedIn) {
      throw new Error("Sent from a conversation no longer shown.");
    }
    onConversation(conversation);
    setStaleMessages(NO_MESSAGES);
  };

  return {
    openCompose,
    openReply,
    dialogProps: {
      open,
      onOpenChange: setOpen,
      replyThread,
      staleMessages,
      onSend,
      sending,
    },
  };
};
