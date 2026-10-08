import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getInboxAssignOptions, searchInboxPeople } from "@/api/inboxApi";
import { useRequestGuard } from "@/hooks/useRequestGuard";
import { stageLabel } from "@/pages/Recruiting/board/stageFormat";
import { formatInTz, resolveViewerTimezone } from "@/utils/dateTime";

const selectClass =
  "w-full rounded-md border border-slate-300 bg-white p-2 text-sm";

const PersonSearch = ({ onPick }) => {
  const { begin, isCurrent } = useRequestGuard();
  const [term, setTerm] = useState("");
  const [hits, setHits] = useState([]);

  const search = (value) => {
    setTerm(value);
    if (!value.trim()) {
      begin();
      setHits([]);
      return;
    }
    const seq = begin();
    searchInboxPeople(value.trim())
      .then(({ data }) => isCurrent(seq) && setHits(data ?? []))
      .catch((e) => isCurrent(seq) && toast.error(e.message));
  };

  return (
    <div className="space-y-2">
      <Input
        aria-label="Search people"
        placeholder="Search by name, user ID or email"
        value={term}
        onChange={(e) => search(e.target.value)}
        className="border-slate-300"
      />
      {term.trim() && (
        <ul className="max-h-48 divide-y divide-slate-100 overflow-y-auto rounded-md border border-slate-200">
          {hits.map((u) => (
            <li key={u.userId}>
              <button
                type="button"
                onClick={() => onPick(u)}
                className="flex w-full justify-between px-3 py-1.5 text-left text-sm hover:bg-slate-50"
              >
                <span>{u.name}</span>
                <span className="text-slate-500">#{u.userId}</span>
              </button>
            </li>
          ))}
          {!hits.length && (
            <li className="px-3 py-2 text-sm text-slate-500">
              No one matches.
            </li>
          )}
        </ul>
      )}
    </div>
  );
};

const RoundPicker = ({ rounds, value, onChange }) => (
  <div className="space-y-1.5">
    <label
      htmlFor="assign-round"
      className="text-sm font-medium text-slate-900"
    >
      Round
    </label>
    <select
      id="assign-round"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={selectClass}
    >
      {rounds.map((r) => (
        <option key={r.roundId} value={r.roundId}>
          {r.name}
          {r.current ? " (current)" : ""}
          {r.registered ? "" : " — Not registered"}
        </option>
      ))}
    </select>
  </div>
);

const appLabel = (a, kind) =>
  [
    `#${a.applicationId}`,
    stageLabel(a.stage, kind),
    a.appliedAt &&
      `Applied ${formatInTz(a.appliedAt, resolveViewerTimezone(), "MMM d, yyyy")}`,
  ]
    .filter(Boolean)
    .join(" · ");

// The live application if there is one, else the newest (the list is newest first).
const defaultApplicationId = (job) => {
  const apps = job?.applications ?? [];
  const pick = apps.find((a) => a.stage !== "rejected") ?? apps[0];
  return pick ? String(pick.applicationId) : "";
};

const JobPicker = ({
  name,
  jobs,
  jobId,
  applicationId,
  onJobChange,
  onApplicationChange,
}) => {
  if (!jobs.length) {
    return (
      <p className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
        {name} has not applied to any job, so this thread can&apos;t be
        assigned. You can still reply without assigning, or Archive it.
      </p>
    );
  }
  const job = jobs.find((j) => String(j.jobId) === jobId);
  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <label
          htmlFor="assign-job"
          className="text-sm font-medium text-slate-900"
        >
          Job
        </label>
        <select
          id="assign-job"
          value={jobId}
          onChange={(e) => onJobChange(e.target.value)}
          className={selectClass}
        >
          <option value="">Select a job…</option>
          {jobs.map((j) => (
            <option key={j.jobId} value={j.jobId}>
              {j.title}
            </option>
          ))}
        </select>
        <p className="text-xs text-slate-500">
          Only jobs this person applied to.
        </p>
      </div>
      {job && (
        <div className="space-y-1.5">
          <label
            htmlFor="assign-application"
            className="text-sm font-medium text-slate-900"
          >
            Application
          </label>
          <select
            id="assign-application"
            value={applicationId}
            onChange={(e) => onApplicationChange(e.target.value)}
            className={selectClass}
          >
            {(job.applications ?? []).map((a) => (
              <option key={a.applicationId} value={a.applicationId}>
                {appLabel(a, job.kind)}
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
};

/**
 * AssignDialog
 *
 * Assign a thread to a person, then to the context its service needs: a round
 * for Mentorship, a job and then one of its applications for Recruiting. The
 * person is prefilled when the sender matches a user; otherwise staff search
 * for one. Once assigned, the thread leaves the Inbox.
 *
 * Mounted fresh for each opening so its state never leaks between threads.
 *
 * @param {{thread: object, onAssign: (body: object) => Promise<boolean>,
 *   onCancel: () => void}} props
 * @returns {JSX.Element}
 */
const AssignDialog = ({ thread, onAssign, onCancel }) => {
  const { begin, isCurrent } = useRequestGuard();
  const [person, setPerson] = useState(thread.person);
  const [searching, setSearching] = useState(false);
  const [options, setOptions] = useState(null);
  const [roundId, setRoundId] = useState("");
  const [jobId, setJobId] = useState("");
  const [applicationId, setApplicationId] = useState("");
  const userId = person?.userId;

  useEffect(() => {
    setOptions(null);
    setJobId("");
    setApplicationId("");
    if (userId == null) return;
    const seq = begin();
    getInboxAssignOptions(thread.threadId, userId)
      .then(({ data }) => {
        if (!isCurrent(seq)) return;
        setOptions(data);
        const rounds = data.rounds ?? [];
        const initial = rounds.find((r) => r.current) ?? rounds[0];
        setRoundId(initial ? String(initial.roundId) : "");
      })
      .catch((e) => isCurrent(seq) && toast.error(e.message));
  }, [userId, thread.threadId]); // eslint-disable-line react-hooks/exhaustive-deps

  const mentorship = thread.service === "mentorship";
  const ready =
    Boolean(person) &&
    !searching &&
    options != null &&
    (mentorship ? roundId !== "" : applicationId !== "");

  const confirm = async () => {
    const body = mentorship
      ? { userId, roundId: Number(roundId) }
      : { userId, applicationId: Number(applicationId) };
    if (await onAssign(body)) onCancel();
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onCancel()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Assign thread</DialogTitle>
          <DialogDescription>{thread.subject}</DialogDescription>
        </DialogHeader>

        <div className="space-y-1.5">
          <div className="text-sm font-medium text-slate-900">Person</div>
          {person && !searching ? (
            <div className="flex items-center justify-between rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
              <div>
                <div aria-label="Selected person">
                  {person.name}{" "}
                  <span className="text-slate-500">· #{person.userId}</span>
                </div>
                {person.userId === thread.person?.userId &&
                  thread.matchedBy && (
                    <div className="text-xs text-slate-500">
                      Matched by {thread.matchedBy} email
                    </div>
                  )}
              </div>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setSearching(true)}
              >
                Change
              </Button>
            </div>
          ) : (
            <>
              {!person && (
                <p className="text-xs text-slate-500">
                  {thread.sender} doesn&apos;t match any user. Pick the person
                  first.
                </p>
              )}
              <PersonSearch
                onPick={(u) => {
                  setPerson({ userId: u.userId, name: u.name });
                  setSearching(false);
                }}
              />
            </>
          )}
        </div>

        {person && !searching && options && mentorship && (
          <RoundPicker
            rounds={options.rounds ?? []}
            value={roundId}
            onChange={setRoundId}
          />
        )}
        {person && !searching && options && !mentorship && (
          <JobPicker
            name={person.name}
            jobs={options.jobs ?? []}
            jobId={jobId}
            applicationId={applicationId}
            onJobChange={(value) => {
              setJobId(value);
              setApplicationId(
                defaultApplicationId(
                  options.jobs.find((j) => String(j.jobId) === value),
                ),
              );
            }}
            onApplicationChange={setApplicationId}
          />
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button disabled={!ready} onClick={confirm}>
            Assign
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default AssignDialog;
