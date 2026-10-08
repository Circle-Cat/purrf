import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import AssignDialog from "@/pages/Inbox/AssignDialog";
import ThreadDetail from "@/pages/Inbox/ThreadDetail";
import ThreadList from "@/pages/Inbox/ThreadList";
import { SERVICES, serviceOf } from "@/pages/Inbox/inboxDisplay";
import { useInboxThread } from "@/pages/Inbox/hooks/useInboxThread";
import { useInboxThreads } from "@/pages/Inbox/hooks/useInboxThreads";

const ALL = "all";
const SEARCH_DEBOUNCE_MS = 300;

const chipClass = (on) =>
  `rounded-full border px-3 py-1 text-sm transition-colors ${
    on
      ? "border-slate-900 bg-slate-900 text-white"
      : "border-slate-300 bg-white text-slate-700 hover:bg-slate-100"
  }`;

const notifySidebar = () => window.dispatchEvent(new Event("inbox:changed"));

/**
 * Inbox
 *
 * Threads that someone else started and that are not assigned yet, for every
 * service the viewer may see, in one list. Staff filter, search, open a
 * thread, reply, archive, move it to another service and assign Mentorship
 * and Recruiting threads; an assigned thread leaves the Inbox. Which threads,
 * counts and actions are available all come from the API.
 *
 * @returns {JSX.Element}
 */
const InboxPage = () => {
  const [params, setParams] = useSearchParams();
  const [needsReply, setNeedsReply] = useState(false);
  const [archived, setArchived] = useState(false);
  const [term, setTerm] = useState("");
  const [q, setQ] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [assigning, setAssigning] = useState(false);

  const serviceParam = params.get("service");
  const service = SERVICES.some((s) => s.key === serviceParam)
    ? serviceParam
    : ALL;

  useEffect(() => {
    const id = setTimeout(() => setQ(term.trim()), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(id);
  }, [term]);

  const {
    data: { threads, counts, services },
    refresh,
  } = useInboxThreads({
    service: service === ALL ? undefined : service,
    needsReply,
    archived,
    q,
  });

  const onChanged = useCallback(() => {
    refresh();
    notifySidebar();
  }, [refresh]);

  const onGone = useCallback(() => {
    setSelectedId(null);
    setAssigning(false);
    refresh();
    notifySidebar();
  }, [refresh]);

  const detail = useInboxThread(selectedId, { onChanged, onGone });
  const { thread } = detail;

  const pickService = (key) =>
    setParams(key === ALL ? {} : { service: key }, { replace: true });

  const totalNeedsReply = services.reduce((n, s) => n + s.needsReply, 0);
  const filters = [
    {
      key: "needsReply",
      label: "Needs reply",
      count: counts.needsReply,
      on: needsReply,
      set: setNeedsReply,
    },
  ];

  return (
    <div className="flex flex-col gap-4 p-6">
      <header className="flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-semibold text-slate-900">Inbox</h1>
        <Badge
          variant="outline"
          className="border-orange-200 bg-orange-50 text-orange-700"
        >
          Needs reply: {totalNeedsReply}
        </Badge>
      </header>

      <div
        role="group"
        aria-label="Services"
        className="flex flex-wrap items-center gap-2"
      >
        {[
          { key: ALL, label: "All", needsReply: totalNeedsReply },
          ...services.map((s) => ({
            key: s.key,
            label: serviceOf(s.key).label,
            needsReply: s.needsReply,
          })),
        ].map((s) => (
          <button
            key={s.key}
            type="button"
            aria-pressed={service === s.key}
            onClick={() => pickService(s.key)}
            className={chipClass(service === s.key)}
          >
            {s.label}
            {s.needsReply > 0 && (
              <span className="ml-1.5 rounded-full bg-orange-100 px-1.5 text-[11px] text-orange-700">
                {s.needsReply}
              </span>
            )}
          </button>
        ))}
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
          {filters.map((f) => (
            <button
              key={f.key}
              type="button"
              aria-pressed={f.on}
              onClick={() => f.set(!f.on)}
              className={chipClass(f.on)}
            >
              {f.label} ({f.count})
            </button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input
            type="checkbox"
            checked={archived}
            onChange={(e) => setArchived(e.target.checked)}
          />
          Show archived
        </label>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <ThreadList
          threads={threads}
          selectedId={selectedId}
          onOpen={setSelectedId}
          emptyText={
            q
              ? `No threads match "${q}" with these filters.`
              : "No threads match these filters."
          }
        />
        {thread ? (
          <ThreadDetail
            key={thread.threadId}
            thread={thread}
            stale={detail.stale}
            pending={detail.pending}
            onReply={detail.reply}
            onArchive={detail.archive}
            onUnarchive={detail.unarchive}
            onAssign={() => setAssigning(true)}
            onMove={detail.move}
          />
        ) : (
          <p className="hidden rounded-lg border border-dashed border-slate-300 bg-white p-6 text-center text-sm text-slate-500 lg:block">
            {selectedId == null ? "Select a thread to read it." : "Loading…"}
          </p>
        )}
      </div>

      {assigning && thread && (
        <AssignDialog
          key={thread.threadId}
          thread={thread}
          onAssign={detail.assign}
          onCancel={() => setAssigning(false)}
        />
      )}
    </div>
  );
};

export default InboxPage;
