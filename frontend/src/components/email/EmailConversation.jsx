import { Button } from "@/components/ui/button";
import EmailThreadCard from "@/components/email/EmailThreadCard";
import { sortThreadsByActivity } from "@/components/email/emailThreads";

/**
 * One context's email conversation: a Send email action and every thread,
 * most recent activity first.
 *
 * `canSend` off drops Send email and Reply entirely, for a read-only view.
 * `sendDisabledHint` keeps them rendered but disabled and titled, for a viewer
 * who owns the context but lacks the grant sending needs.
 *
 * @param {{conversation: {threads: object[]}|null,
 *          formatTime: (iso: string) => string,
 *          attachmentUrl?: (messageId: number, index: number) => string,
 *          canSend: boolean, sendDisabledHint?: string,
 *          onCompose?: () => void,
 *          onReply?: (thread: object) => void}} props
 */
const EmailConversation = ({
  conversation,
  formatTime,
  attachmentUrl,
  canSend,
  sendDisabledHint,
  onCompose,
  onReply,
}) => {
  const threads = sortThreadsByActivity(conversation?.threads ?? []);
  return (
    <div className="space-y-4">
      {canSend && (
        <div className="flex items-center gap-2">
          <Button
            type="button"
            size="sm"
            disabled={Boolean(sendDisabledHint)}
            title={sendDisabledHint}
            onClick={onCompose}
          >
            Send email
          </Button>
        </div>
      )}
      {threads.length === 0 ? (
        <p className="text-sm text-slate-400">No emails yet.</p>
      ) : (
        <ul className="space-y-4">
          {threads.map((thread) => (
            <li key={thread.threadId}>
              <EmailThreadCard
                thread={thread}
                formatTime={formatTime}
                attachmentUrl={attachmentUrl}
                canReply={canSend}
                replyDisabledHint={sendDisabledHint}
                onReply={onReply}
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default EmailConversation;
