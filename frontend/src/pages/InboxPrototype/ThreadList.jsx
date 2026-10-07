import { Badge } from "@/components/ui/badge";
import {
  assignmentLabel,
  contactOf,
  formatTime,
  isArchived,
  isUnassigned,
  needsReply,
  lastMessage,
  machineTagOf,
  matchSender,
  serviceOf,
} from "@/pages/InboxPrototype/inboxState";

const TAG_STYLES = {
  "Auto-reply": "border-slate-300 bg-slate-100 text-slate-600",
  "Delivery failed": "border-red-200 bg-red-50 text-red-700",
  Archived: "border-slate-300 bg-white text-slate-500",
  "Needs reply": "border-orange-200 bg-orange-50 text-orange-700",
  Unassigned: "border-sky-200 bg-sky-50 text-sky-700",
  Moved: "border-violet-200 bg-violet-50 text-violet-700",
};

/**
 * SenderName
 *
 * `Name · #id` for a sender the lookup resolves; the bare address plus an
 * `No matching user` badge otherwise.
 *
 * @param {{email: string}} props
 * @returns {JSX.Element}
 */
export const SenderName = ({ email }) => {
  const match = matchSender(email);
  if (match) {
    return (
      <span className="font-medium text-slate-900">
        {match.user.name}
        <span className="font-normal text-slate-500">
          {" "}
          · #{match.user.userId}
        </span>
      </span>
    );
  }
  return (
    <span className="flex flex-wrap items-center gap-1.5">
      <span className="font-medium text-slate-900">{email}</span>
      <Badge
        variant="outline"
        className="border-amber-300 bg-amber-50 text-amber-800"
      >
        No matching user
      </Badge>
    </span>
  );
};

/**
 * ThreadList
 *
 * The Inbox rows under the current filters, every service mixed in one list.
 * Each row is a button — the whole row opens the thread.
 *
 * @param {{threads: object[], selectedId: string|null, onOpen: Function,
 *   emptyText: string}} props
 * @returns {JSX.Element}
 */
const ThreadList = ({ threads, selectedId, onOpen, emptyText }) => {
  if (!threads.length) {
    return (
      <p className="rounded-lg border border-dashed border-slate-300 bg-white p-6 text-center text-sm text-slate-500">
        {emptyText}
      </p>
    );
  }

  return (
    <ul className="divide-y divide-slate-200 overflow-hidden rounded-lg border border-slate-200 bg-white">
      {threads.map((thread) => {
        const last = lastMessage(thread);
        const tags = [
          needsReply(thread) ? "Needs reply" : null,
          isUnassigned(thread) ? "Unassigned" : null,
          machineTagOf(thread),
          isArchived(thread) ? "Archived" : null,
          thread.movedFrom
            ? `Moved from ${serviceOf(thread.movedFrom).label}`
            : null,
        ].filter(Boolean);
        const chip = assignmentLabel(thread.assignment);
        return (
          <li key={thread.id}>
            <button
              type="button"
              onClick={() => onOpen(thread.id)}
              aria-label={`Open thread ${thread.subject}`}
              className={`block w-full px-4 py-3 text-left text-sm transition-colors ${
                thread.id === selectedId ? "bg-sky-50" : "hover:bg-slate-50"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <SenderName email={contactOf(thread)} />
                <span className="shrink-0 text-xs text-slate-500">
                  {formatTime(last.at)}
                </span>
              </div>
              <div className="mt-0.5 flex flex-wrap items-center gap-1.5">
                <Badge
                  variant="outline"
                  className={serviceOf(thread.service).badgeClass}
                >
                  {serviceOf(thread.service).label}
                </Badge>
                <span className="font-medium text-slate-800">
                  {thread.subject}
                </span>
              </div>
              <div className="truncate text-slate-500">{last.body}</div>
              {(tags.length > 0 || chip) && (
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {tags.map((tag) => (
                    <Badge
                      key={tag}
                      variant="outline"
                      className={
                        TAG_STYLES[tag.startsWith("Moved") ? "Moved" : tag]
                      }
                    >
                      {tag}
                    </Badge>
                  ))}
                  {chip && (
                    <Badge
                      variant="outline"
                      className="border-emerald-200 bg-emerald-50 text-emerald-800"
                    >
                      {chip}
                    </Badge>
                  )}
                </div>
              )}
            </button>
          </li>
        );
      })}
    </ul>
  );
};

export default ThreadList;
