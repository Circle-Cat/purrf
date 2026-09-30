import { useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import AssignDialog from "@/pages/InboxPrototype/AssignDialog";
import ThreadDetail from "@/pages/InboxPrototype/ThreadDetail";
import ThreadList from "@/pages/InboxPrototype/ThreadList";
import {
  addMinutes,
  contactOf,
  isArchived,
  isAwaiting,
  isAwaitingIgnoringArchive,
  lastMessage,
  replyAliasOf,
} from "@/pages/InboxPrototype/inboxState";
import { INBOXES, INITIAL_THREADS, NOW } from "@/pages/InboxPrototype/mockData";

const VIEWS = [
  { key: "awaiting", label: "Awaiting reply" },
  { key: "unassigned", label: "Unassigned" },
];

/** `#inbox/recruiting` opens on the Recruiting inbox. */
const inboxFromHash = () => {
  const sub = window.location.hash.replace("#", "").split("/")[1];
  return INBOXES.some((i) => i.key === sub) ? sub : INBOXES[0].key;
};

const inView = (thread, view, showArchived) => {
  if (view === "awaiting") {
    return showArchived
      ? isAwaiting(thread) ||
          (isArchived(thread) && isAwaitingIgnoringArchive(thread))
      : isAwaiting(thread);
  }
  return !thread.assignment && (showArchived || !isArchived(thread));
};

const byNewest = (a, b) => lastMessage(b).at.localeCompare(lastMessage(a).at);

/**
 * InboxPrototype
 *
 * Self-contained, mock-data prototype of the service inboxes for inbound
 * mail. Every alias is a Send-As alias on one mailbox; new mail lands in the
 * inbox of the alias it was addressed to. Staff reply, archive, and assign a
 * thread to a person plus the context that inbox needs.
 *
 * The three inboxes sit in different places in the real product; here they
 * share one switcher so the differences are side by side. Refreshing resets
 * everything.
 *
 * @returns {JSX.Element}
 */
const InboxPrototype = () => {
  const [inbox, setInbox] = useState(inboxFromHash);
  const [view, setView] = useState("awaiting");
  const [showArchived, setShowArchived] = useState(false);
  const [threads, setThreads] = useState(INITIAL_THREADS);
  const [selectedId, setSelectedId] = useState(null);
  const [assigningId, setAssigningId] = useState(null);
  const clock = useRef(NOW);

  const tick = () => {
    clock.current = addMinutes(clock.current, 1);
    return clock.current;
  };

  const patch = (threadId, fn) =>
    setThreads((prev) => prev.map((t) => (t.id === threadId ? fn(t) : t)));

  const meta = INBOXES.find((i) => i.key === inbox);
  const own = threads.filter((t) => t.inbox === inbox);
  const awaitingCount = (key) =>
    threads.filter((t) => t.inbox === key && isAwaiting(t)).length;
  const visible = own
    .filter((t) => inView(t, view, showArchived))
    .sort(byNewest);
  const selected = own.find((t) => t.id === selectedId) ?? null;
  const assigning = threads.find((t) => t.id === assigningId) ?? null;

  const switchInbox = (key) => {
    setInbox(key);
    setSelectedId(null);
    window.history.replaceState(null, "", `#inbox/${key}`);
  };

  const reply = (threadId, body) => {
    const at = tick();
    patch(threadId, (t) => ({
      ...t,
      messages: [
        ...t.messages,
        {
          id: `${t.id}-${at}`,
          direction: "out",
          from: replyAliasOf(t),
          to: contactOf(t),
          at,
          body,
          kind: "human",
        },
      ],
    }));
  };

  const simulateReply = (threadId) => {
    const at = tick();
    patch(threadId, (t) => ({
      ...t,
      messages: [
        ...t.messages,
        {
          id: `${t.id}-${at}`,
          direction: "in",
          from: contactOf(t),
          to: replyAliasOf(t),
          at,
          body: "Just following up on my last message — any news?",
          kind: "human",
        },
      ],
    }));
  };

  const archive = (threadId) => {
    const at = tick();
    patch(threadId, (t) => ({ ...t, archivedAt: at }));
  };

  const unarchive = (threadId) =>
    patch(threadId, (t) => ({ ...t, archivedAt: null }));

  const assign = (threadId, assignment) => {
    patch(threadId, (t) => ({ ...t, assignment }));
    setAssigningId(null);
  };

  const move = (threadId, target) => {
    const at = tick();
    patch(threadId, (t) => ({
      ...t,
      inbox: target,
      movedFrom: t.inbox,
      movedAt: at,
      assignment: null,
    }));
    setSelectedId(null);
  };

  return (
    <div className="min-h-full bg-slate-50">
      <nav
        aria-label="Inboxes"
        className="flex flex-wrap items-center gap-2 border-b border-slate-200 bg-white px-4 py-2"
      >
        <span className="mr-2 text-xs uppercase tracking-wide text-slate-400">
          Inbox
        </span>
        {INBOXES.map((item) => {
          const active = item.key === inbox;
          const count = awaitingCount(item.key);
          return (
            <button
              key={item.key}
              type="button"
              onClick={() => switchInbox(item.key)}
              className={`flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm transition-colors ${
                active
                  ? "border-slate-900 bg-slate-900 text-white"
                  : "border-slate-300 bg-white text-slate-700 hover:bg-slate-100"
              }`}
            >
              {item.label}
              {count > 0 && (
                <span
                  className={`rounded-full px-1.5 text-[11px] ${
                    active
                      ? "bg-slate-700 text-slate-100"
                      : "bg-orange-100 text-orange-700"
                  }`}
                >
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      <main className="mx-auto max-w-6xl space-y-4 p-4 sm:p-6">
        <header className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-semibold text-slate-900">
              {meta.label} inbox
            </h1>
            <Badge
              variant="outline"
              className="border-orange-200 bg-orange-50 text-orange-700"
            >
              Awaiting reply: {awaitingCount(inbox)}
            </Badge>
            {meta.draft && (
              <Badge
                variant="outline"
                className="border-violet-200 bg-violet-50 text-violet-700"
              >
                Draft — scope under discussion
              </Badge>
            )}
          </div>
          <p className="text-sm text-slate-600">
            New mail addressed to{" "}
            <code className="rounded bg-slate-100 px-1 text-slate-800">
              {meta.alias}
            </code>
            {meta.key === "mentorship" &&
              ", plus replies on the Mentee and Mentor application threads"}
            .
          </p>
          <p className="text-xs text-slate-500">{meta.placement}</p>
        </header>

        <div className="flex flex-wrap items-center gap-3">
          <div
            role="tablist"
            aria-label="View"
            className="inline-flex rounded-lg border border-slate-200 bg-white p-1"
          >
            {VIEWS.map((v) => (
              <button
                key={v.key}
                type="button"
                role="tab"
                aria-selected={view === v.key}
                onClick={() => setView(v.key)}
                className={`rounded-md px-3 py-1 text-sm ${
                  view === v.key
                    ? "bg-slate-900 text-white"
                    : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                {v.label}
              </button>
            ))}
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={showArchived}
              onChange={(e) => setShowArchived(e.target.checked)}
            />
            Show archived
          </label>
        </div>

        <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          <ThreadList
            threads={visible}
            selectedId={selectedId}
            onOpen={setSelectedId}
            emptyText={
              view === "awaiting"
                ? "Nothing is waiting for a reply."
                : "Every thread here is assigned."
            }
          />
          {selected ? (
            <ThreadDetail
              key={selected.id}
              thread={selected}
              onReply={reply}
              onArchive={archive}
              onUnarchive={unarchive}
              onAssign={setAssigningId}
              onMove={move}
              onSimulateReply={simulateReply}
            />
          ) : (
            <p className="hidden rounded-lg border border-dashed border-slate-300 bg-white p-6 text-center text-sm text-slate-500 lg:block">
              Select a thread to read it.
            </p>
          )}
        </div>
      </main>

      {assigning && (
        <AssignDialog
          key={assigning.id}
          thread={assigning}
          onCancel={() => setAssigningId(null)}
          onConfirm={assign}
        />
      )}
    </div>
  );
};

export default InboxPrototype;
