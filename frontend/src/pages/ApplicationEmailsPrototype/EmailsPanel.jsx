import DOMPurify from "dompurify";
import { AlertTriangle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  formatWhen,
  needsReply,
  openBounceOf,
} from "@/pages/ApplicationEmailsPrototype/emailState";

const EMAIL_DIRECTION_LABELS = { outbound: "Sent", inbound: "Received" };

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

const NeedsReplyBadge = () => (
  <Badge
    variant="outline"
    className="border-orange-200 bg-orange-50 text-orange-700"
  >
    Needs reply
  </Badge>
);

const EmailMessageBubble = ({ message }) => {
  const html =
    message.bodyHtml != null && message.bodyHtml !== ""
      ? DOMPurify.sanitize(message.bodyHtml)
      : null;
  const tag = KIND_TAGS[message.kind];
  return (
    <li
      aria-label={`Message ${message.messageId}`}
      className={`rounded border p-2 text-sm ${
        tag
          ? "border-dashed border-slate-300 bg-slate-50 opacity-75"
          : "border-slate-200"
      }`}
    >
      <div className="mb-1 flex flex-wrap items-center gap-x-1.5 text-slate-500">
        <span className="font-medium text-slate-700">
          {EMAIL_DIRECTION_LABELS[message.direction] ?? message.direction}
        </span>
        <span>· {formatWhen(message.gmailInternalDate)}</span>
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
        <dd className="break-all text-slate-700">{message.to.join(", ")}</dd>
        {message.cc.length > 0 && (
          <>
            <dt>Cc</dt>
            <dd className="break-all text-slate-700">
              {message.cc.join(", ")}
            </dd>
          </>
        )}
      </dl>
      {html != null ? (
        <div
          className="max-w-none text-slate-700 [&_a]:underline [&_ol]:list-decimal [&_ol]:pl-5 [&_p]:my-3 [&_ul]:list-disc [&_ul]:pl-5"
          dangerouslySetInnerHTML={{ __html: html }}
        />
      ) : (
        <p className="whitespace-pre-wrap text-slate-700">
          {message.bodyText ?? ""}
        </p>
      )}
    </li>
  );
};

/**
 * EmailsPanel
 *
 * One application's email conversation, as the Emails tab renders it today,
 * with this prototype's changes: every message names From and To, auto-replies
 * and bounces are tagged and dimmed, an unanswered bounce raises a banner, and
 * a thread waiting on us says Needs reply.
 *
 * @param {{threads: object[], onCompose: Function, onReply: Function,
 *   onRefresh: Function}} props
 * @returns {JSX.Element}
 */
const EmailsPanel = ({ threads, onCompose, onReply, onRefresh }) => (
  <div className="space-y-4">
    <div className="flex items-center gap-2">
      <Button type="button" size="sm" onClick={onCompose}>
        Send email
      </Button>
      <Button type="button" size="sm" variant="outline" onClick={onRefresh}>
        Refresh
      </Button>
    </div>
    {threads.length === 0 ? (
      <p className="text-sm text-slate-400">No emails yet.</p>
    ) : (
      <ul className="space-y-4">
        {threads.map((thread) => {
          const bounce = openBounceOf(thread);
          const sorted = [...thread.messages].sort((a, b) =>
            a.gmailInternalDate.localeCompare(b.gmailInternalDate),
          );
          return (
            <li
              key={thread.threadId}
              aria-label={`Thread ${thread.subject}`}
              className="space-y-2"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="flex flex-wrap items-center gap-2 text-sm font-medium text-slate-700">
                  {thread.subject || "(no subject)"}
                  {needsReply(thread) && <NeedsReplyBadge />}
                </span>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => onReply(thread)}
                >
                  Reply
                </Button>
              </div>
              {bounce && (
                <div
                  role="alert"
                  className="flex items-center gap-2 rounded-md border border-red-200 bg-red-50 p-2 text-sm text-red-800"
                >
                  <AlertTriangle size={14} />
                  Delivery failed: your email to {bounce.bouncedTo} was not
                  delivered
                </div>
              )}
              <ul className="space-y-2">
                {sorted.map((message) => (
                  <EmailMessageBubble
                    key={message.messageId}
                    message={message}
                  />
                ))}
              </ul>
            </li>
          );
        })}
      </ul>
    )}
  </div>
);

export default EmailsPanel;
