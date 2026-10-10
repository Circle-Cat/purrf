import { useRef, useState } from "react";
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
 * which keeps the dialog open with its draft.
 *
 * @param {{submit: (payload: object) => Promise<object>,
 *          reload: () => Promise<object>,
 *          onConversation: (conversation: object) => void}} options
 * @returns {{openCompose: () => void, openReply: (thread: object) => void,
 *   dialogProps: {open: boolean, onOpenChange: (open: boolean) => void,
 *     replyThread: object|null, staleMessages: object[],
 *     onSend: (payload: object) => Promise<void>, sending: boolean}}}
 */
export const useComposeEmail = ({ submit, reload, onConversation }) => {
  const [open, setOpen] = useState(false);
  const [replyThread, setReplyThread] = useState(null);
  const [staleMessages, setStaleMessages] = useState(NO_MESSAGES);
  const [sending, setSending] = useState(false);
  const busyRef = useRef(false);

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

  const showWhatChanged = async (threadId, lastSeen) => {
    let fresh;
    try {
      fresh = await reload();
    } catch (error) {
      toast.error(error.message);
      return;
    }
    onConversation(fresh);
    const thread = fresh?.threads?.find((t) => t.threadId === threadId);
    if (!thread) return;
    setReplyThread(thread);
    setStaleMessages(messagesAfter(thread, lastSeen));
  };

  const onSend = async (payload) => {
    if (busyRef.current) throw new Error("A send is already in flight.");
    busyRef.current = true;
    setSending(true);
    const lastSeen = replyThread ? lastMessageId(replyThread) : null;
    try {
      const conversation = await submit(
        replyThread ? { ...payload, lastSeenMessageId: lastSeen } : payload,
      );
      onConversation(conversation);
      setStaleMessages(NO_MESSAGES);
      toast.success("Email sent.");
    } catch (error) {
      if (replyThread && isThreadChanged(error)) {
        await showWhatChanged(replyThread.threadId, lastSeen);
      } else {
        toast.error(error.message);
      }
      throw error;
    } finally {
      busyRef.current = false;
      setSending(false);
    }
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
