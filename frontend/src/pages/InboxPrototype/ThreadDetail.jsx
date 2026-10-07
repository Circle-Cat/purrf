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
import {
  activityApplications,
  applicationById,
  assignmentLabel,
  canAssign,
  canMove,
  contactOf,
  formatTime,
  isArchived,
  isUnassigned,
  lastMessage,
  needsReply,
  openBounceOf,
  personOf,
  replyAliasOf,
  serviceOf,
} from "@/pages/InboxPrototype/inboxState";
import { SenderName } from "@/pages/InboxPrototype/ThreadList";
import { SERVICES } from "@/pages/InboxPrototype/mockData";

const KIND_TAG = { auto_reply: "Auto-reply", bounce: "Delivery failed" };

const Attachments = ({ attachments, onDownload }) => (
  <ul aria-label="Attachments" className="mt-2 flex flex-wrap gap-2">
    {attachments.map((a) => (
      <li key={a.name}>
        <button
          type="button"
          onClick={() => onDownload(a.name)}
          className="flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700 hover:bg-slate-100"
        >
          <Paperclip size={12} />
          {a.name}
          <span className="text-slate-500">{a.size}</span>
        </button>
      </li>
    ))}
  </ul>
);

const Message = ({ message, onDownload }) => {
  const machine = message.kind !== "human";
  const inbound = message.direction === "in";
  return (
    <li
      aria-label={`Message ${message.id}`}
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
          {message.sentBy && (
            <span className="font-normal text-slate-500">
              by {message.sentBy}
            </span>
          )}
          {machine && (
            <Badge
              variant="outline"
              className={
                message.kind === "bounce"
                  ? "border-red-200 bg-red-50 text-red-700"
                  : "border-slate-300 bg-slate-100 text-slate-600"
              }
            >
              {KIND_TAG[message.kind]}
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
      <p className="mt-2 whitespace-pre-wrap">{message.body}</p>
      {inbound && message.attachments?.length > 0 && (
        <Attachments
          attachments={message.attachments}
          onDownload={onDownload}
        />
      )}
    </li>
  );
};

/**
 * ThreadDetail
 *
 * The whole conversation, the actions on it, and the reply box. The reply's
 * sending alias is the alias of the service that owns the thread now, and is
 * shown read-only.
 *
 * Sending is refused when a message arrived after the thread was opened (or
 * after the last refusal), so two staff members can't both answer the same
 * question without one of them seeing the other's reply first.
 *
 * @param {{thread: object, onReply: Function, onArchive: Function,
 *   onUnarchive: Function, onAssign: Function, onMove: Function,
 *   onSimulateReply: Function, onSimulateColleague: Function}} props
 * @returns {JSX.Element}
 */
const ThreadDetail = ({
  thread,
  onReply,
  onArchive,
  onUnarchive,
  onAssign,
  onMove,
  onSimulateReply,
  onSimulateColleague,
}) => {
  const latestId = lastMessage(thread).id;
  const [draft, setDraft] = useState("");
  const [moveTarget, setMoveTarget] = useState("");
  const [boardNote, setBoardNote] = useState(false);
  const [download, setDownload] = useState(null);
  const [seenId, setSeenId] = useState(latestId);
  const [stale, setStale] = useState(false);

  const archived = isArchived(thread);
  const bounce = openBounceOf(thread);
  const person = personOf(thread);
  const alias = replyAliasOf(thread);
  const chip = assignmentLabel(thread.assignment);
  const activityApp =
    thread.service === "mentorship"
      ? thread.tracked
        ? applicationById(thread.assignment.context.applicationId)
        : activityApplications(person)[0]
      : null;
  const moveTargets = SERVICES.filter((s) => s.key !== thread.service);
  const sorted = [
    ...thread.messages,
    ...(thread.movedFrom
      ? [
          {
            id: "moved",
            kind: "system",
            at: thread.movedAt,
            body: `Moved from ${serviceOf(thread.movedFrom).label} — replies now sent from ${alias}`,
          },
        ]
      : []),
  ].sort((a, b) => a.at.localeCompare(b.at));

  const send = () => {
    if (seenId !== latestId) {
      setStale(true);
      setSeenId(latestId);
      return;
    }
    setSeenId(onReply(thread.id, draft.trim()));
    setStale(false);
    setDraft("");
  };

  return (
    <section
      aria-label="Thread"
      className="flex flex-col gap-4 rounded-lg border border-slate-200 bg-white p-4"
    >
      <header className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge
            variant="outline"
            className={serviceOf(thread.service).badgeClass}
          >
            {serviceOf(thread.service).label}
          </Badge>
          <h2 className="text-lg font-semibold text-slate-900">
            {thread.subject}
          </h2>
        </div>
        <div className="text-sm">
          <SenderName email={contactOf(thread)} />
        </div>
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          {needsReply(thread) ? (
            <Badge
              variant="outline"
              className="border-orange-200 bg-orange-50 text-orange-700"
            >
              Needs reply
            </Badge>
          ) : (
            <Badge
              variant="outline"
              className="border-slate-200 bg-slate-50 text-slate-600"
            >
              No reply needed
            </Badge>
          )}
          {archived && (
            <Badge
              variant="outline"
              className="border-slate-300 bg-white text-slate-500"
            >
              Archived
            </Badge>
          )}
          {chip ? (
            <Badge
              variant="outline"
              className="border-emerald-200 bg-emerald-50 text-emerald-800"
            >
              {chip}
            </Badge>
          ) : (
            isUnassigned(thread) && (
              <span className="text-slate-500">Unassigned</span>
            )
          )}
        </div>
      </header>

      <div className="flex flex-wrap items-center gap-2 border-y border-slate-200 py-3">
        {thread.tracked && (
          <span className="text-xs text-slate-500">
            Tracked with its application — assignment and service come from
            there.
          </span>
        )}
        {canAssign(thread) && (
          <Button size="sm" onClick={() => onAssign(thread.id)}>
            {thread.assignment ? "Reassign" : "Assign"}
          </Button>
        )}
        {archived ? (
          <Button
            size="sm"
            variant="outline"
            onClick={() => onUnarchive(thread.id)}
          >
            Unarchive
          </Button>
        ) : (
          <Button
            size="sm"
            variant="outline"
            onClick={() => onArchive(thread.id)}
          >
            Archive
          </Button>
        )}
        {canMove(thread) && (
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
              {moveTargets.map((s) => (
                <option key={s.key} value={s.key}>
                  {s.label}
                </option>
              ))}
            </select>
            <Button
              size="sm"
              variant="outline"
              disabled={!moveTarget}
              onClick={() => onMove(thread.id, moveTarget)}
            >
              Move
            </Button>
          </span>
        )}
        {activityApp && (
          <button
            type="button"
            onClick={() => setBoardNote(true)}
            className="text-sm text-sky-700 underline-offset-2 hover:underline"
          >
            View application on Applications Board
          </button>
        )}
        <span className="ml-auto flex flex-col items-end gap-0.5">
          <button
            type="button"
            onClick={() => onSimulateReply(thread.id)}
            className="text-xs text-slate-400 hover:text-slate-600"
            title="Prototype only: append a new message from the sender"
          >
            Dev: simulate new reply
          </button>
          <button
            type="button"
            onClick={() => onSimulateColleague(thread.id)}
            className="text-xs text-slate-400 hover:text-slate-600"
            title="Prototype only: a colleague answers this thread while you have it open"
          >
            Dev: simulate colleague reply
          </button>
        </span>
      </div>

      {boardNote && activityApp && (
        <p className="rounded-md border border-sky-200 bg-sky-50 p-2 text-xs text-sky-800">
          Would open application #{activityApp.id} on the Applications Board
          (not part of this prototype).
        </p>
      )}

      {download && (
        <p className="rounded-md border border-sky-200 bg-sky-50 p-2 text-xs text-sky-800">
          Would download {download}: the server fetches it from Gmail when you
          click, nothing is stored in Purrf, and it always saves as a file
          rather than opening in the browser.
        </p>
      )}

      {canMove(thread) && (
        <p className="text-xs text-slate-500">
          Moving hands the thread to that service as Unassigned. Replies then go
          out from that service&apos;s alias, and you may no longer see it if
          you lack that service&apos;s permission.
        </p>
      )}

      {bounce && (
        <div
          role="alert"
          className="flex items-center gap-2 rounded-md border border-red-200 bg-red-50 p-2 text-sm text-red-800"
        >
          <AlertTriangle size={14} />
          Delivery failed: your email to {bounce.bouncedTo} was not delivered
        </div>
      )}

      <ol className="space-y-2">
        {sorted.map((m) =>
          m.kind === "system" ? (
            <li
              key={m.id}
              className="text-center text-xs text-slate-500 italic"
            >
              {m.body}
            </li>
          ) : (
            <Message key={m.id} message={m} onDownload={setDownload} />
          ),
        )}
      </ol>

      <div className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-3">
        <div className="text-xs text-slate-600">
          From: <span className="font-medium text-slate-800">{alias}</span>
          <span className="ml-3">
            To: <span className="text-slate-800">{contactOf(thread)}</span>
          </span>
        </div>
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
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Write a reply…"
          rows={3}
          className="border-slate-300 bg-white"
        />
        <div className="flex justify-end">
          <Button size="sm" disabled={!draft.trim()} onClick={send}>
            Send reply
          </Button>
        </div>
      </div>
    </section>
  );
};

export default ThreadDetail;
