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
    <label htmlFor="assign-round" className="text-sm font-medium text-slate-900">
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

const JobPicker = ({ name, jobs, value, onChange }) => {
  if (!jobs.length) {
    return (
      <p className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
        {name} has not applied to any employment job, so this thread
        can&apos;t be assigned. You can still reply without assigning, or
        Archive it.
      </p>
    );
  }
  const pick = jobs.find((j) => String(j.jobId) === value);
  return (
    <div className="space-y-1.5">
      <label htmlFor="assign-job" className="text-sm font-medium text-slate-900">
        Job
      </label>
      <select
        id="assign-job"
        value={value}
        onChange={(e) => onChange(e.target.value)}
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
        Only employment jobs this person applied to.
      </p>
      {pick && (
        <p className="text-sm text-slate-700">
          {pick.fallback
            ? `Attaches to most recent application #${pick.applicationId} (${pick.applicationStatus})`
            : `Attaches to application #${pick.applicationId} (${pick.applicationStatus})`}
        </p>
      )}
    </div>
  );
};

/**
 * AssignDialog
 *
 * Assign a thread to a person, then to the context its service needs: a round
 * for Mentorship, a job (and so an application) for Recruiting. The person is
 * prefilled when the sender matches a user; otherwise staff search for one.
 * An assigned thread can also drop its assignment.
 *
 * Mounted fresh for each opening so its state never leaks between threads.
 *
 * @param {{thread: object, onAssign: (body: object) => Promise<boolean>,
 *   onUnassign: () => Promise<boolean>, onCancel: () => void}} props
 * @returns {JSX.Element}
 */
const AssignDialog = ({ thread, onAssign, onUnassign, onCancel }) => {
  const { begin, isCurrent } = useRequestGuard();
  const [person, setPerson] = useState(thread.person);
  const [searching, setSearching] = useState(false);
  const [options, setOptions] = useState(null);
  const [roundId, setRoundId] = useState("");
  const [jobId, setJobId] = useState("");
  const userId = person?.userId;

  useEffect(() => {
    setOptions(null);
    setJobId("");
    if (userId == null) return;
    const seq = begin();
    getInboxAssignOptions(thread.threadId, userId)
      .then(({ data }) => {
        if (!isCurrent(seq)) return;
        setOptions(data);
        const rounds = data.rounds ?? [];
        const keep = rounds.find(
          (r) => r.roundId === thread.assignment?.roundId,
        );
        const initial = keep ?? rounds.find((r) => r.current) ?? rounds[0];
        setRoundId(initial ? String(initial.roundId) : "");
        const job = (data.jobs ?? []).find(
          (j) => j.applicationId === thread.assignment?.applicationId,
        );
        if (job) setJobId(String(job.jobId));
      })
      .catch((e) => isCurrent(seq) && toast.error(e.message));
  }, [userId, thread.threadId]); // eslint-disable-line react-hooks/exhaustive-deps

  const mentorship = thread.service === "mentorship";
  const ready =
    Boolean(person) &&
    !searching &&
    options != null &&
    (mentorship ? roundId !== "" : jobId !== "");

  const confirm = async () => {
    const body = mentorship
      ? { userId, roundId: Number(roundId) }
      : { userId, jobId: Number(jobId) };
    if (await onAssign(body)) onCancel();
  };

  const remove = async () => {
    if (await onUnassign()) onCancel();
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onCancel()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {thread.assignment ? "Reassign thread" : "Assign thread"}
          </DialogTitle>
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
            value={jobId}
            onChange={setJobId}
          />
        )}

        <DialogFooter>
          {thread.assignment && (
            <Button
              variant="ghost"
              className="mr-auto text-red-700 hover:bg-red-50 hover:text-red-800"
              onClick={remove}
            >
              Remove assignment
            </Button>
          )}
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
