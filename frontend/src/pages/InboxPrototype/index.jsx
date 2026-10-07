import { useRef, useState } from "react";
import { Inbox } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import AssignDialog from "@/pages/InboxPrototype/AssignDialog";
import ThreadDetail from "@/pages/InboxPrototype/ThreadDetail";
import ThreadList from "@/pages/InboxPrototype/ThreadList";
import {
  addMinutes,
  contactOf,
  byListOrder,
  isArchived,
  isUnassigned,
  matchesSearch,
  needsReply,
  replyAliasOf,
} from "@/pages/InboxPrototype/inboxState";
import {
  INITIAL_THREADS,
  NOW,
  SERVICES,
} from "@/pages/InboxPrototype/mockData";

/** Filter chips; selected ones combine with AND. */
const FILTERS = [
  { key: "needsReply", label: "Needs reply", test: needsReply },
  { key: "unassigned", label: "Unassigned", test: isUnassigned },
];

const ALL = "all";

/** `#inbox/recruiting` opens filtered to Recruiting. */
const serviceFromHash = () => {
  const sub = window.location.hash.replace("#", "").split("/")[1];
  return SERVICES.some((s) => s.key === sub) ? sub : ALL;
};

const chipClass = (on) =>
  `rounded-full border px-3 py-1 text-sm transition-colors ${
    on
      ? "border-slate-900 bg-slate-900 text-white"
      : "border-slate-300 bg-white text-slate-700 hover:bg-slate-100"
  }`;

/**
 * InboxPrototype
 *
 * Self-contained, mock-data prototype of the one Inbox for inbound mail.
 * Every alias is a Send-As alias on one mailbox; new mail is tagged with the
 * service of the alias it was addressed to, and every service's threads share
 * one list. What a viewer sees follows their permissions: each service has
 * its own. Staff reply, archive, move a thread to another service, and assign
 * Mentorship and Recruiting threads to a person plus the context that service
 * needs.
 *
 * Refreshing resets everything.
 *
 * @returns {JSX.Element}
 */
const InboxPrototype = () => {
  const [granted, setGranted] = useState(() => SERVICES.map((s) => s.key));
  const [service, setService] = useState(serviceFromHash);
  const [active, setActive] = useState([]);
  const [showArchived, setShowArchived] = useState(false);
  const [term, setTerm] = useState("");
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

  const visibleServices = SERVICES.filter((s) => granted.includes(s.key));
  const scope = service === ALL ? granted : [service];
  const viewable = threads.filter((t) => granted.includes(t.service));
  const scoped = viewable.filter((t) => scope.includes(t.service));
  const live = scoped.filter((t) => !isArchived(t));
  const totalNeedsReply = viewable.filter(needsReply).length;
  const visible = scoped
    .filter(
      (t) =>
        (showArchived || !isArchived(t)) &&
        FILTERS.every((f) => !active.includes(f.key) || f.test(t)) &&
        matchesSearch(t, term),
    )
    .sort(byListOrder);
  const selected = viewable.find((t) => t.id === selectedId) ?? null;
  const assigning = threads.find((t) => t.id === assigningId) ?? null;

  const toggleFilter = (key) =>
    setActive((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key],
    );

  const pickService = (key) => {
    setService(key);
    window.history.replaceState(
      null,
      "",
      key === ALL ? "#inbox" : `#inbox/${key}`,
    );
  };

  const toggleGrant = (key) => {
    const next = granted.includes(key)
      ? granted.filter((k) => k !== key)
      : [...granted, key];
    setGranted(next);
    if (service !== ALL && !next.includes(service)) pickService(ALL);
  };

  const append = (threadId, message) =>
    patch(threadId, (t) => ({ ...t, messages: [...t.messages, message] }));

  const reply = (threadId, body) => {
    const at = tick();
    const thread = threads.find((t) => t.id === threadId);
    const id = `${threadId}-${at}`;
    append(threadId, {
      id,
      direction: "out",
      from: replyAliasOf(thread),
      to: contactOf(thread),
      at,
      body,
      kind: "human",
    });
    return id;
  };

  const simulateReply = (threadId) => {
    const at = tick();
    const thread = threads.find((t) => t.id === threadId);
    append(threadId, {
      id: `${threadId}-${at}`,
      direction: "in",
      from: contactOf(thread),
      to: replyAliasOf(thread),
      at,
      body: "Just following up on my last message — any news?",
      kind: "human",
      attachments: [],
    });
  };

  const simulateColleague = (threadId) => {
    const at = tick();
    const thread = threads.find((t) => t.id === threadId);
    append(threadId, {
      id: `${threadId}-${at}`,
      direction: "out",
      from: replyAliasOf(thread),
      to: contactOf(thread),
      at,
      body: "Thanks for writing in — I'm looking into this and will get back to you shortly.",
      kind: "human",
      sentBy: "Alex Kim",
    });
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
      service: target,
      movedFrom: t.service,
      movedAt: at,
      assignment: null,
      archivedAt: null,
    }));
  };

  return (
    <div className="min-h-full bg-slate-50">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-slate-200 bg-white px-4 py-2 text-sm">
        <div className="flex items-center gap-2">
          <span className="text-xs uppercase tracking-wide text-slate-400">
            Sidebar
          </span>
          {visibleServices.length ? (
            <span
              aria-label="Sidebar Inbox entry"
              className="flex items-center gap-1.5 rounded-md bg-slate-900 px-3 py-1.5 text-white"
            >
              <Inbox size={14} />
              Inbox
              {totalNeedsReply > 0 && (
                <span className="rounded-full bg-orange-500 px-1.5 text-[11px] text-white">
                  {totalNeedsReply}
                </span>
              )}
            </span>
          ) : (
            <span className="text-slate-500 italic">
              No Inbox entry: the viewer holds none of the three permissions.
            </span>
          )}
        </div>
        <fieldset className="flex flex-wrap items-center gap-3">
          <legend className="sr-only">Viewer permissions</legend>
          <span className="text-xs text-slate-400">
            Dev: viewer permissions
          </span>
          {SERVICES.map((s) => (
            <label
              key={s.key}
              className="flex items-center gap-1.5 text-xs text-slate-600"
            >
              <input
                type="checkbox"
                checked={granted.includes(s.key)}
                onChange={() => toggleGrant(s.key)}
              />
              <code>{s.permission}</code>
            </label>
          ))}
        </fieldset>
      </div>

      {visibleServices.length > 0 && (
        <main className="mx-auto max-w-6xl space-y-4 p-4 sm:p-6">
          <header className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-xl font-semibold text-slate-900">Inbox</h1>
              <Badge
                variant="outline"
                className="border-orange-200 bg-orange-50 text-orange-700"
              >
                Needs reply: {totalNeedsReply}
              </Badge>
            </div>
            <p className="text-sm text-slate-600">
              New mail to{" "}
              {visibleServices.map((s, i) => (
                <span key={s.key}>
                  {i > 0 && (i === visibleServices.length - 1 ? " and " : ", ")}
                  <code className="rounded bg-slate-100 px-1 text-slate-800">
                    {s.alias}
                  </code>
                </span>
              ))}
              {granted.includes("mentorship") &&
                ", plus replies on the Mentee and Mentor application threads"}
              .
            </p>
          </header>

          <div
            role="group"
            aria-label="Services"
            className="flex flex-wrap items-center gap-2"
          >
            {[{ key: ALL, label: "All" }, ...visibleServices].map((s) => {
              const count = viewable.filter(
                (t) => (s.key === ALL || t.service === s.key) && needsReply(t),
              ).length;
              return (
                <button
                  key={s.key}
                  type="button"
                  aria-pressed={service === s.key}
                  onClick={() => pickService(s.key)}
                  className={chipClass(service === s.key)}
                >
                  {s.label}
                  {count > 0 && (
                    <span className="ml-1.5 rounded-full bg-orange-100 px-1.5 text-[11px] text-orange-700">
                      {count}
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Input
              type="search"
              aria-label="Search threads"
              placeholder="Search name, #user ID, email or subject"
              value={term}
              onChange={(e) => setTerm(e.target.value)}
              className="w-full border-slate-300 bg-white sm:w-72"
            />
            <div
              role="group"
              aria-label="Filters"
              className="flex flex-wrap items-center gap-2"
            >
              {FILTERS.map((f) => {
                const on = active.includes(f.key);
                return (
                  <button
                    key={f.key}
                    type="button"
                    aria-pressed={on}
                    onClick={() => toggleFilter(f.key)}
                    className={chipClass(on)}
                  >
                    {f.label} ({live.filter(f.test).length})
                  </button>
                );
              })}
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
                term.trim()
                  ? `No threads match "${term.trim()}" with these filters.`
                  : "No threads match these filters."
              }
            />
            {selected ? (
              <ThreadDetail
                key={`${selected.id}-${selected.service}`}
                thread={selected}
                onReply={reply}
                onArchive={archive}
                onUnarchive={unarchive}
                onAssign={setAssigningId}
                onMove={move}
                onSimulateReply={simulateReply}
                onSimulateColleague={simulateColleague}
              />
            ) : (
              <p className="hidden rounded-lg border border-dashed border-slate-300 bg-white p-6 text-center text-sm text-slate-500 lg:block">
                Select a thread to read it.
              </p>
            )}
          </div>
        </main>
      )}

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
