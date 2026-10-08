import { useState } from "react";
import {
  AlertTriangle,
  ArrowDownLeft,
  ArrowUpRight,
  Paperclip,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { inboxAttachmentUrl } from "@/api/inboxApi";
import { SenderName } from "@/pages/Inbox/ThreadList";
import { EMAIL_BODY_BOX_CLASS, sanitizeEmailBody } from "@/utils/emailHtml";
import {
  MACHINE_TAG_LABELS,
  SERVICES,
  formatSize,
  formatTime,
  serviceOf,
} from "@/pages/Inbox/inboxDisplay";

const escapeHtml = (s) =>
  s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

const toHtml = (text) =>
  `<p>${text.trim().split("\n").map(escapeHtml).join("<br>")}</p>`;

const Message = ({ threadId, message }) => {
  const machine = message.inboundKind in MACHINE_TAG_LABELS;
  const inbound = message.direction === "inbound";
  const html = message.bodyHtml ? sanitizeEmailBody(message.bodyHtml) : null;
  return (
    <li
      aria-label={`Message ${message.messageId}`}
      className={`rounded-lg border p-3 text-sm ${
        machine
          ? "border-dashed border-slate-300 bg-slate-50 text-slate-500"
          : inbound
            ? "border-slate-200 bg-white text-slate-800"
            : "border-sky-200 bg-sky-50 text-slate-800"
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
        <span className="flex items-center gap-1.5 font-medium text-slate-600">
          {inbound ? <ArrowDownLeft size={12} /> : <ArrowUpRight size={12} />}
          {inbound ? "Received" : "Sent"}
          {message.sentByName && (
            <span className="font-normal text-slate-500">
              by {message.sentByName}
            </span>
          )}
          {machine && (
            <Badge
              variant="outline"
              className={
                message.inboundKind === "bounce"
                  ? "border-red-200 bg-red-50 text-red-700"
                  : "border-slate-300 bg-slate-100 text-slate-600"
              }
            >
              {MACHINE_TAG_LABELS[message.inboundKind]}
            </Badge>
          )}
        </span>
        <span className="text-slate-500">{formatTime(message.at)}</span>
      </div>
      <dl className="mt-1 grid grid-cols-[3rem_1fr] gap-x-2 text-xs text-slate-500">
        <dt>From</dt>
        <dd className="break-all">{message.from}</dd>
        <dt>To</dt>
        <dd className="break-all">{message.to}</dd>
      </dl>
      {html != null ? (
        <div
          className={`mt-2 max-w-none ${EMAIL_BODY_BOX_CLASS} [&_a]:underline [&_ol]:list-decimal [&_ol]:pl-5 [&_p]:my-3 [&_ul]:list-disc [&_ul]:pl-5`}
          dangerouslySetInnerHTML={{ __html: html }}
        />
      ) : (
        <p className="mt-2 whitespace-pre-wrap">{message.bodyText ?? ""}</p>
      )}
      {message.attachments?.length > 0 && (
        <ul aria-label="Attachments" className="mt-2 flex flex-wrap gap-2">
          {message.attachments.map((a, index) => (
            <li key={a.attachmentId ?? index}>
              <a
                href={inboxAttachmentUrl(threadId, message.messageId, index)}
                download
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700 hover:bg-slate-100"
              >
                <Paperclip size={12} />
                {a.name}
                <span className="text-slate-500">{formatSize(a.size)}</span>
              </a>
            </li>
          ))}
        </ul>
      )}
    </li>
  );
};

/**
 * ThreadDetail
 *
 * The whole conversation, the actions on it, and the reply box. The reply is
 * sent from the alias of the service that owns the thread now. Sending is
 * refused by the server when a message arrived after the thread was loaded;
 * `stale` then shows a warning and the draft stays.
 *
 * @param {{thread: object, stale: boolean, pending: boolean, onReply: (html: string) => Promise<boolean>,
 *   onArchive: Function, onUnarchive: Function, onAssign: Function,
 *   onMove: (service: string) => void}} props
 * @returns {JSX.Element}
 */
const ThreadDetail = ({
  thread,
  stale,
  pending,
  onReply,
  onArchive,
  onUnarchive,
  onAssign,
  onMove,
}) => {
  const [draft, setDraft] = useState("");
  const [moveTarget, setMoveTarget] = useState("");
  const service = serviceOf(thread.service);
  const noAlias = !thread.replyAlias;
  const timeline = [
    ...thread.messages.map((m) => ({ ...m, key: m.messageId })),
    ...(thread.movedFrom && thread.movedAt
      ? [
          {
            key: "moved",
            system: true,
            at: thread.movedAt,
            body: `Moved from ${serviceOf(thread.movedFrom).label}${
              thread.replyAlias
                ? `; replies now sent from ${thread.replyAlias}`
                : ""
            }`,
          },
        ]
      : []),
  ].sort((a, b) => new Date(a.at) - new Date(b.at));

  const send = async () => {
    if (await onReply(toHtml(draft))) setDraft("");
  };

  return (
    <section
      aria-label="Thread"
      className="flex flex-col gap-4 rounded-lg border border-slate-200 bg-white p-4"
    >
      <header className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className={service.badgeClass}>
            {service.label}
          </Badge>
          <h2 className="text-lg font-semibold text-slate-900">
            {thread.subject}
          </h2>
        </div>
        <div className="text-sm">
          <SenderName {...thread} />
          {thread.matchedBy && (
            <span className="ml-2 text-xs text-slate-500">
              Matched by {thread.matchedBy} email
            </span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <Badge
            variant="outline"
            className={
              thread.needsReply
                ? "border-orange-200 bg-orange-50 text-orange-700"
                : "border-slate-200 bg-slate-50 text-slate-600"
            }
          >
            {thread.needsReply ? "Needs reply" : "No reply needed"}
          </Badge>
          {thread.archived && (
            <Badge
              variant="outline"
              className="border-slate-300 bg-white text-slate-500"
            >
              Archived
            </Badge>
          )}
        </div>
      </header>

      <div className="flex flex-wrap items-center gap-2 border-y border-slate-200 py-3">
        {thread.canAssign && (
          <Button size="sm" disabled={pending} onClick={onAssign}>
            Assign
          </Button>
        )}
        {thread.archived ? (
          <Button
            size="sm"
            variant="outline"
            disabled={pending}
            onClick={onUnarchive}
          >
            Unarchive
          </Button>
        ) : (
          <Button
            size="sm"
            variant="outline"
            disabled={pending}
            onClick={onArchive}
          >
            Archive
          </Button>
        )}
        <span className="flex items-center gap-1.5">
          <label htmlFor="move-target" className="sr-only">
            Move to
          </label>
          <select
            id="move-target"
            value={moveTarget}
            onChange={(e) => setMoveTarget(e.target.value)}
            className="h-8 rounded-md border border-slate-300 bg-white px-2 text-sm"
          >
            <option value="">Move to…</option>
            {SERVICES.filter((s) => s.key !== thread.service).map((s) => (
              <option key={s.key} value={s.key}>
                {s.label}
              </option>
            ))}
          </select>
          <Button
            size="sm"
            variant="outline"
            disabled={pending || !moveTarget}
            onClick={() => {
              onMove(moveTarget);
              setMoveTarget("");
            }}
          >
            Move
          </Button>
        </span>
      </div>

      <p className="text-xs text-slate-500">
        Moving hands the thread to that service. Replies then go out from that
        service&apos;s alias, and you may no longer see it if you lack that
        service&apos;s permission.
      </p>

      {thread.openBounce && (
        <div
          role="alert"
          className="flex items-center gap-2 rounded-md border border-red-200 bg-red-50 p-2 text-sm text-red-800"
        >
          <AlertTriangle size={14} />
          Delivery failed: your email to {thread.openBounce.bouncedTo} was not
          delivered
        </div>
      )}

      <ol className="space-y-2">
        {timeline.map((m) =>
          m.system ? (
            <li
              key={m.key}
              className="text-center text-xs text-slate-500 italic"
            >
              {m.body}
            </li>
          ) : (
            <Message key={m.key} threadId={thread.threadId} message={m} />
          ),
        )}
      </ol>

      <div className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-3">
        {noAlias ? (
          <p className="text-xs text-slate-600">
            This environment has no alias for this inbox
          </p>
        ) : (
          <div className="text-xs text-slate-600">
            From:{" "}
            <span className="font-medium text-slate-800">
              {thread.replyAlias}
            </span>
            <span className="ml-3">
              To: <span className="text-slate-800">{thread.sender}</span>
            </span>
          </div>
        )}
        {stale && (
          <p
            role="status"
            className="rounded-md border border-amber-300 bg-amber-50 p-2 text-xs text-amber-900"
          >
            Not sent: this thread has new messages since you opened it. Read
            them first; your draft is kept. Send again to send it as is.
          </p>
        )}
        <Textarea
          aria-label="Reply"
          value={draft}
          disabled={noAlias}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Write a reply…"
          rows={3}
          className="border-slate-300 bg-white"
        />
        <div className="flex justify-end">
          <Button
            size="sm"
            disabled={pending || noAlias || !draft.trim()}
            onClick={send}
          >
            Send reply
          </Button>
        </div>
      </div>
    </section>
  );
};

export default ThreadDetail;
