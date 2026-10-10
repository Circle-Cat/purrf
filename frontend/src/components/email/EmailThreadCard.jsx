import { AlertTriangle, Paperclip } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EMAIL_BODY_BOX_CLASS, sanitizeEmailBody } from "@/utils/emailHtml";
import { formatSize } from "@/pages/Inbox/inboxDisplay";
import { messageTime } from "@/components/email/emailThreads";

const DIRECTION_LABELS = { outbound: "Sent", inbound: "Received" };

const KIND_TAGS = {
  auto_reply: {
    label: "Auto-reply",
    className: "border-slate-300 bg-slate-100 text-slate-600",
  },
  bounce: {
    label: "Delivery failed",
    className: "border-red-200 bg-red-50 text-red-700",
  },
};

const ATTACHMENT_CLASS =
  "flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700";

/**
 * One stored message. Auto-replies and delivery-failure reports
 * (`inboundKind`) are tagged and dimmed so they read as noise next to human
 * replies. Attachments link to `attachmentUrl(messageId, index)` when it is
 * given and are listed by name otherwise.
 *
 * @param {{message: object, formatTime: (iso: string) => string,
 *          attachmentUrl?: (messageId: number, index: number) => string}} props
 */
export const EmailMessage = ({ message, formatTime, attachmentUrl }) => {
  const kind =
    message.inboundKind ??
    (message.failedRecipients != null ? "bounce" : undefined);
  const tag = KIND_TAGS[kind];
  const html =
    message.bodyHtml != null && message.bodyHtml !== ""
      ? sanitizeEmailBody(message.bodyHtml)
      : null;
  const when = messageTime(message);
  const attachments = message.attachments ?? [];
  return (
    <li
      className={`rounded border p-2 text-sm ${
        tag ? "border-dashed border-slate-300 bg-slate-50 text-slate-500" : ""
      }`}
    >
      <div className="mb-1 flex flex-wrap items-center gap-x-1.5 text-slate-500">
        <span className="font-medium text-slate-700">
          {DIRECTION_LABELS[message.direction] ?? message.direction}
        </span>
        {message.sentByName ? <span>by {message.sentByName}</span> : null}
        {when ? <span>· {formatTime(when)}</span> : null}
        {tag && (
          <Badge variant="outline" className={tag.className}>
            {tag.label}
          </Badge>
        )}
      </div>
      <dl className="mb-1 grid grid-cols-[2.25rem_1fr] gap-x-2 text-xs text-slate-500">
        <dt>From</dt>
        <dd className="break-all text-slate-700">{message.fromAddress}</dd>
        <dt>To</dt>
        <dd className="break-all text-slate-700">{message.toAddresses}</dd>
      </dl>
      {html != null ? (
        // Mail bodies are foreign HTML, and Tailwind's preflight zeroes <p>
        // margins, drops list markers and strips link underlines; without
        // these hooks a message reads as one dense block whose links look
        // like plain text.
        <div
          className={`max-w-none text-slate-700 ${EMAIL_BODY_BOX_CLASS} [&_a]:underline [&_ol]:list-decimal [&_ol]:pl-5 [&_p]:my-3 [&_ul]:list-disc [&_ul]:pl-5`}
          dangerouslySetInnerHTML={{ __html: html }}
        />
      ) : (
        <p className="whitespace-pre-wrap text-slate-700">
          {message.bodyText ?? ""}
        </p>
      )}
      {attachments.length > 0 && (
        <ul aria-label="Attachments" className="mt-2 flex flex-wrap gap-2">
          {attachments.map((attachment, index) => {
            const href = attachmentUrl?.(message.messageId, index);
            const label = (
              <>
                <Paperclip size={12} />
                {attachment.name}
                <span className="text-slate-500">
                  {formatSize(attachment.size)}
                </span>
              </>
            );
            return (
              <li key={index}>
                {href ? (
                  <a
                    href={href}
                    download
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`${ATTACHMENT_CLASS} hover:bg-slate-100`}
                  >
                    {label}
                  </a>
                ) : (
                  <span className={ATTACHMENT_CLASS}>{label}</span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </li>
  );
};

/**
 * One email thread: its subject, whether it waits on a reply, an unanswered
 * delivery failure, and every message oldest first. Reply is offered only
 * with `canReply`; `replyDisabledHint` keeps it rendered but disabled and
 * titled.
 *
 * @param {{thread: object, formatTime: (iso: string) => string,
 *          attachmentUrl?: (messageId: number, index: number) => string,
 *          canReply?: boolean, replyDisabledHint?: string,
 *          onReply?: (thread: object) => void}} props
 */
const EmailThreadCard = ({
  thread,
  formatTime,
  attachmentUrl,
  canReply = false,
  replyDisabledHint,
  onReply,
}) => (
  <div className="space-y-2">
    <div className="flex items-center justify-between gap-2">
      <span className="flex flex-wrap items-center gap-2 text-sm font-medium text-slate-700">
        {thread.subject || "(no subject)"}
        {thread.needsReply && (
          <Badge
            variant="outline"
            className="border-orange-200 bg-orange-50 text-orange-700"
          >
            Needs reply
          </Badge>
        )}
      </span>
      {canReply && (
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={Boolean(replyDisabledHint)}
          title={replyDisabledHint}
          onClick={() => onReply(thread)}
        >
          Reply
        </Button>
      )}
    </div>
    {thread.openBounce && (
      <div
        role="alert"
        className="flex items-center gap-2 rounded-md border border-red-200 bg-red-50 p-2 text-sm text-red-800"
      >
        <AlertTriangle size={14} />
        {`Delivery failed: your email to ${thread.openBounce.bouncedTo} was not delivered`}
      </div>
    )}
    <ul className="space-y-2">
      {(thread.messages ?? []).map((message) => (
        <EmailMessage
          key={message.messageId}
          message={message}
          formatTime={formatTime}
          attachmentUrl={attachmentUrl}
        />
      ))}
    </ul>
  </div>
);

export default EmailThreadCard;
