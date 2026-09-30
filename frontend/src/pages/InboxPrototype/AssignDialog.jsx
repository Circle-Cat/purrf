import { useState } from "react";
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
import {
  contactOf,
  employmentApplications,
  matchSender,
  pickApplication,
  userById,
} from "@/pages/InboxPrototype/inboxState";
import {
  CURRENT_ROUND,
  JOBS,
  ROUNDS,
  USERS,
} from "@/pages/InboxPrototype/mockData";

const PersonSearch = ({ onPick }) => {
  const [term, setTerm] = useState("");
  const needle = term.trim().toLowerCase();
  const hits = USERS.filter(
    (u) =>
      !needle ||
      u.name.toLowerCase().includes(needle) ||
      String(u.userId).includes(needle) ||
      u.primaryEmail.includes(needle) ||
      u.alternativeEmails.some((e) => e.includes(needle)),
  );
  return (
    <div className="space-y-2">
      <Input
        aria-label="Search people"
        placeholder="Search by name, user ID or email"
        value={term}
        onChange={(e) => setTerm(e.target.value)}
        className="border-slate-300"
      />
      <ul className="max-h-48 divide-y divide-slate-100 overflow-y-auto rounded-md border border-slate-200">
        {hits.map((u) => (
          <li key={u.userId}>
            <button
              type="button"
              onClick={() => onPick(u.userId)}
              className="flex w-full justify-between px-3 py-1.5 text-left text-sm hover:bg-slate-50"
            >
              <span>{u.name}</span>
              <span className="text-slate-500">#{u.userId}</span>
            </button>
          </li>
        ))}
        {!hits.length && (
          <li className="px-3 py-2 text-sm text-slate-500">No one matches.</li>
        )}
      </ul>
    </div>
  );
};

const RoundPicker = ({ person, round, onRound }) => (
  <div className="space-y-1.5">
    <label
      htmlFor="assign-round"
      className="text-sm font-medium text-slate-900"
    >
      Round
    </label>
    <select
      id="assign-round"
      value={round}
      onChange={(e) => onRound(e.target.value)}
      className="w-full rounded-md border border-slate-300 bg-white p-2 text-sm"
    >
      {ROUNDS.map((r) => (
        <option key={r} value={r}>
          {r}
          {r === CURRENT_ROUND ? " (current)" : ""}
          {person.rounds.includes(r) ? "" : " — Not registered"}
        </option>
      ))}
    </select>
  </div>
);

const JobPicker = ({ person, jobKey, onJob }) => {
  const apps = employmentApplications(person);
  if (!apps.length) {
    return (
      <p className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
        {person.name} has not applied to any employment job, so this thread
        can&apos;t be assigned. You can still reply without assigning, or
        Archive it.
      </p>
    );
  }
  const jobKeys = [...new Set(apps.map((a) => a.job))];
  const pick = jobKey ? pickApplication(person, jobKey) : null;
  return (
    <div className="space-y-1.5">
      <label
        htmlFor="assign-job"
        className="text-sm font-medium text-slate-900"
      >
        Job
      </label>
      <select
        id="assign-job"
        value={jobKey}
        onChange={(e) => onJob(e.target.value)}
        className="w-full rounded-md border border-slate-300 bg-white p-2 text-sm"
      >
        <option value="">Select a job…</option>
        {jobKeys.map((k) => (
          <option key={k} value={k}>
            {JOBS[k].title}
          </option>
        ))}
      </select>
      <p className="text-xs text-slate-500">
        Only employment jobs this person applied to.
      </p>
      {pick && (
        <p className="text-sm text-slate-700">
          {pick.fallback
            ? `Attaches to most recent application #${pick.application.id} (${pick.application.status})`
            : `Attaches to application #${pick.application.id} (${pick.application.status})`}
        </p>
      )}
    </div>
  );
};

const initialPerson = (thread) =>
  thread.assignment?.userId ??
  matchSender(contactOf(thread))?.user.userId ??
  null;

const initialJob = (thread) => {
  const ctx = thread.assignment?.context;
  if (ctx?.kind !== "application") return "";
  const user = userById(thread.assignment.userId);
  return user.applications.find((a) => a.id === ctx.applicationId)?.job ?? "";
};

/**
 * AssignDialog
 *
 * Assign a thread to a person, then to the context its inbox needs: a round
 * for Mentorship, a job (and so an application) for Recruiting, nothing more
 * for Inquiries. The person is prefilled when the sender's address matches a
 * user; an unknown sender has to be picked first.
 *
 * Mounted fresh for each opening, so its state never leaks between threads.
 *
 * @param {{thread: object, onCancel: Function, onConfirm: Function}} props
 * @returns {JSX.Element}
 */
const AssignDialog = ({ thread, onCancel, onConfirm }) => {
  const match = matchSender(contactOf(thread));
  const [personId, setPersonId] = useState(() => initialPerson(thread));
  const [searching, setSearching] = useState(false);
  const [round, setRound] = useState(
    thread.assignment?.context?.round ?? CURRENT_ROUND,
  );
  const [jobKey, setJobKey] = useState(() => initialJob(thread));

  const person = personId ? userById(personId) : null;
  const matchedHint =
    match && match.user.userId === personId
      ? match.matchedBy === "alternative"
        ? "Matched by alternative email"
        : "Matched by primary email"
      : null;

  let context = null;
  let ready = Boolean(person);
  if (person && thread.inbox === "mentorship") {
    context = { kind: "round", round };
  }
  if (person && thread.inbox === "recruiting") {
    const pick = jobKey ? pickApplication(person, jobKey) : null;
    context = pick
      ? { kind: "application", applicationId: pick.application.id }
      : null;
    ready = Boolean(pick);
  }

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
                {matchedHint && (
                  <div className="text-xs text-slate-500">{matchedHint}</div>
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
                  {contactOf(thread)} doesn&apos;t match any user. Pick the
                  person first.
                </p>
              )}
              <PersonSearch
                onPick={(id) => {
                  setPersonId(id);
                  setJobKey("");
                  setSearching(false);
                }}
              />
            </>
          )}
        </div>

        {person && !searching && thread.inbox === "mentorship" && (
          <RoundPicker person={person} round={round} onRound={setRound} />
        )}
        {person && !searching && thread.inbox === "recruiting" && (
          <JobPicker person={person} jobKey={jobKey} onJob={setJobKey} />
        )}
        {person && !searching && thread.inbox === "inquiries" && (
          <p className="text-xs text-slate-500">
            Inquiries assign to a person only — there is no round or job.
          </p>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button
            disabled={!ready || searching}
            onClick={() => onConfirm(thread.id, { userId: personId, context })}
          >
            Assign
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default AssignDialog;
