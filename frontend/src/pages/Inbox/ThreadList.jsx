import { Badge } from "@/components/ui/badge";
import {
  MACHINE_TAG_LABELS,
  formatTime,
  serviceOf,
} from "@/pages/Inbox/inboxDisplay";

const TAG_STYLES = {
  "Auto-reply": "border-slate-300 bg-slate-100 text-slate-600",
  "Delivery failed": "border-red-200 bg-red-50 text-red-700",
  Archived: "border-slate-300 bg-white text-slate-500",
  "Needs reply": "border-orange-200 bg-orange-50 text-orange-700",
  Moved: "border-violet-200 bg-violet-50 text-violet-700",
};

/**
 * SenderName
 *
 * `Name · #id` for a sender matched to a user; the bare address plus a
 * `No matching user` badge otherwise.
 *
 * @param {{sender: string, person: {userId: number, name: string}|null,
 *   noMatchingUser: boolean}} props
 * @returns {JSX.Element}
 */
export const SenderName = ({ sender, person, noMatchingUser }) => {
  if (person) {
    return (
      <span className="font-medium text-slate-900">
        {person.name}
        <span className="font-normal text-slate-500"> · #{person.userId}</span>
      </span>
    );
  }
  return (
    <span className="flex flex-wrap items-center gap-1.5">
      <span className="font-medium text-slate-900">{sender}</span>
      {noMatchingUser && (
        <Badge
          variant="outline"
          className="border-amber-300 bg-amber-50 text-amber-800"
        >
          No matching user
        </Badge>
      )}
    </span>
  );
};

/**
 * ThreadList
 *
 * The Inbox rows under the current filters, every service mixed in one list.
 * Each row is a button; the whole row opens the thread.
 *
 * @param {{threads: object[], selectedId: number|null, onOpen: Function,
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
        const service = serviceOf(thread.service);
        const tags = [
          thread.needsReply ? "Needs reply" : null,
          MACHINE_TAG_LABELS[thread.machineTag] ?? null,
          thread.archived ? "Archived" : null,
          thread.movedFrom
            ? `Moved from ${serviceOf(thread.movedFrom).label}`
            : null,
        ].filter(Boolean);
        return (
          <li key={thread.threadId}>
            <button
              type="button"
              onClick={() => onOpen(thread.threadId)}
              aria-label={`Open thread ${thread.subject}`}
              className={`block w-full px-4 py-3 text-left text-sm transition-colors ${
                thread.threadId === selectedId
                  ? "bg-sky-50"
                  : "hover:bg-slate-50"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <SenderName {...thread} />
                <span className="shrink-0 text-xs text-slate-500">
                  {formatTime(thread.lastActivityAt)}
                </span>
              </div>
              <div className="mt-0.5 flex flex-wrap items-center gap-1.5">
                <Badge variant="outline" className={service.badgeClass}>
                  {service.label}
                </Badge>
                <span className="font-medium text-slate-800">
                  {thread.subject}
                </span>
              </div>
              <div className="truncate text-slate-500">{thread.snippet}</div>
              {tags.length > 0 && (
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
