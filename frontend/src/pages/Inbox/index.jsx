import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { deleteInboxThreads } from "@/api/inboxApi";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import AssignDialog from "@/pages/Inbox/AssignDialog";
import DeleteThreadsDialog from "@/pages/Inbox/DeleteThreadsDialog";
import ThreadDetail from "@/pages/Inbox/ThreadDetail";
import ThreadList from "@/pages/Inbox/ThreadList";
import { SERVICES, conversations, serviceOf } from "@/pages/Inbox/inboxDisplay";
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
 * and Recruiting threads; an assigned thread leaves the Inbox. In a service
 * whose threads can be deleted (Unsorted), rows get checkboxes and a bulk
 * Delete. Which threads, counts and actions are available all come from the
 * API.
 *
 * @returns {JSX.Element}
 */
const InboxPage = () => {
  const [params, setParams] = useSearchParams();
  const [needsReply, setNeedsReply] = useState(false);
  const [archived, setArchived] = useState(false);
  const [term, setTerm] = useState("");
  const [q, setQ] = useState("");
  const [userIdTerm, setUserIdTerm] = useState("");
  const [userId, setUserId] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [assigning, setAssigning] = useState(false);
  const [checked, setChecked] = useState(() => new Set());
  const [deleting, setDeleting] = useState(null);
  const [deletePending, setDeletePending] = useState(false);

  const serviceParam = params.get("service");
  const service = SERVICES.some((s) => s.key === serviceParam)
    ? serviceParam
    : ALL;

  // An open thread from another tab would sit beside a list that lacks it.
  useEffect(() => {
    setSelectedId(null);
    setAssigning(false);
  }, [service]);

  useEffect(() => {
    setChecked(new Set());
  }, [service, needsReply, archived, q, userId]);

  useEffect(() => {
    const id = setTimeout(() => setQ(term.trim()), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(id);
  }, [term]);

  useEffect(() => {
    const id = setTimeout(() => setUserId(userIdTerm), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(id);
  }, [userIdTerm]);

  const {
    data: { threads, counts, services },
    refresh,
    drop,
  } = useInboxThreads({
    service: service === ALL ? undefined : service,
    needsReply,
    archived,
    q,
    userId,
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

  const deletable = service !== ALL && serviceOf(service).deletable === true;
  const checkedIds = threads
    .map((t) => t.threadId)
    .filter((id) => checked.has(id));
  const allChecked = threads.length > 0 && checkedIds.length === threads.length;

  const toggle = (id) =>
    setChecked((cur) => {
      const next = new Set(cur);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const toggleAll = () =>
    setChecked(
      allChecked ? new Set() : new Set(threads.map((t) => t.threadId)),
    );

  const confirmDelete = async () => {
    const ids = deleting;
    setDeletePending(true);
    try {
      const { data } = await deleteInboxThreads(ids);
      drop(ids);
      setChecked((cur) => new Set([...cur].filter((id) => !ids.includes(id))));
      if (ids.includes(selectedId)) {
        setSelectedId(null);
        setAssigning(false);
      }
      toast.success(`Deleted ${conversations(data?.deleted ?? ids.length)}.`);
      refresh();
      notifySidebar();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setDeletePending(false);
      setDeleting(null);
    }
  };

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
          placeholder="Search name, email or subject"
          value={term}
          onChange={(e) => setTerm(e.target.value)}
          className="w-full border-slate-300 bg-white sm:w-72"
        />
        <Input
          inputMode="numeric"
          aria-label="User ID"
          placeholder="User ID"
          value={userIdTerm}
          onChange={(e) => setUserIdTerm(e.target.value.replace(/\D/g, ""))}
          className="w-full border-slate-300 bg-white sm:w-32"
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
        <div className="flex min-w-0 flex-col gap-2">
          {deletable && (
            <div className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-2">
              <Checkbox
                aria-label="Select all on this page"
                checked={
                  allChecked
                    ? true
                    : checkedIds.length > 0
                      ? "indeterminate"
                      : false
                }
                disabled={!threads.length}
                onCheckedChange={toggleAll}
                className="border-slate-400 bg-white"
              />
              <span className="text-sm text-slate-600">
                {checkedIds.length
                  ? `${checkedIds.length} selected`
                  : "Select all"}
              </span>
              <Button
                size="sm"
                variant="destructive"
                className="ml-auto"
                disabled={!checkedIds.length}
                onClick={() => setDeleting(checkedIds)}
              >
                Delete ({checkedIds.length})
              </Button>
            </div>
          )}
          <ThreadList
            threads={threads}
            selectedId={selectedId}
            onOpen={setSelectedId}
            checked={deletable ? checked : undefined}
            onToggle={toggle}
            emptyText={
              q
                ? `No threads match "${q}" with these filters.`
                : "No threads match these filters."
            }
          />
        </div>
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
            onDelete={
              serviceOf(thread.service).deletable
                ? () => setDeleting([thread.threadId])
                : undefined
            }
          />
        ) : (
          <p className="hidden rounded-lg border border-dashed border-slate-300 bg-white p-6 text-center text-sm text-slate-500 lg:block">
            {selectedId == null ? "Select a thread to read it." : "Loading…"}
          </p>
        )}
      </div>

      {deleting && (
        <DeleteThreadsDialog
          count={deleting.length}
          pending={deletePending}
          onConfirm={confirmDelete}
          onCancel={() => setDeleting(null)}
        />
      )}

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
