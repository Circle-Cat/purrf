import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import FlagBadges from "@/pages/MentorshipAdminPrototype/FlagBadges";
import AccountStateChips from "@/pages/MentorshipAdminPrototype/AccountStateChips";
import EmailDots from "@/pages/MentorshipAdminPrototype/EmailDots";
import PairCell from "@/pages/MentorshipAdminPrototype/PairCell";
import NotificationFilter from "@/pages/MentorshipAdminPrototype/NotificationFilter";
import { describeLastRound } from "@/pages/MentorshipAdminPrototype/lastRound";
import {
  EMAIL_STEPS,
  stepState,
  stepsFor,
} from "@/pages/MentorshipAdminPrototype/emailStatus";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { NOTE_LABELS } from "@/pages/MentorshipAdminPrototype/mockData";
import {
  capacityOf,
  freeSlotsOf,
  matchingBlocker,
} from "@/pages/MentorshipAdminPrototype/eligibility";

/**
 * How many meetings someone held in the latest round they took part in
 * before this one — or that they never took part, were not matched, or left.
 *
 * Shown only under the "Eligible for matching" filter: it is a signal for
 * choosing who goes into a run, and outside matching it answers nothing
 * anyone is asking. Only the counts are numbers; "first time" and "not
 * matched" are never shown as 0, which would sort a newcomer to the top of
 * the chase list.
 */
const LastRound = ({ value }) => (
  <span
    className={
      value.kind === "first-time" || value.kind === "unmatched"
        ? "text-slate-500"
        : ""
    }
  >
    {describeLastRound(value)}
  </span>
);

/**
 * ParticipantsTable
 *
 * One row per person registered for the round, with their pairs inside the
 * row: Bob Liu carries two mentees and is still one row, with one line per
 * pair in the Pair column.
 *
 * Every filter comes from `query`, which is the URL. Open the third person on
 * a filtered list, come back, and the list is still filtered — the selection
 * is the one thing that deliberately does not survive.
 *
 * @returns {JSX.Element}
 */
const ParticipantsTable = ({
  query,
  onQueryChange,
  participants,
  round,
  nonParticipants,
  pairs,
  can,
  onOpenParticipant,
  onMarkCell,
  onCompose,
  flagsByParticipant = {},
  exemptParticipantIds = new Set(),
  accountOf,
  matchRun = null,
  onRunMatching,
  matchingOpen = false,
  roundRunning = false,
  notes = [],
  notifications = [],
  emails = [],
  onOpenPerson,
}) => {
  // One table since the pair axis was folded into it; kept as a name so the
  // conditions below still read as "on the person table".
  const tab = "participants";
  const term = query.q ?? "";
  const role = query.role ?? "all";
  const identity = query.identity ?? "all";
  const onboarding = query.onboarding ?? "all";
  // Matching and the unregistered list only mean something while the round
  // runs, from recruitment to its end; a past round offers neither.
  const eligibleOnly = roundRunning && query.filter === "eligible";
  // Only until this round's matching closes; after that there is nothing left
  // to exempt anyone for.
  const exemptionOnly = matchingOpen && query.filter === "needs_exemption";
  const narrow = eligibleOnly || exemptionOnly;
  const emailStep = query.email ?? "all";
  const emailState = query.emailState ?? "all";
  /**
   * "Who has not had the mid-term reminder" — the question the email filter
   * answers. Both halves have to be chosen for it to narrow anything.
   */
  const passesEmail = (person) => {
    if (emailStep === "all" || emailState === "all") return true;
    const step = EMAIL_STEPS.find((s) => s.key === emailStep);
    return step
      ? stepState(step, person, emails, notes, notifications).state ===
          emailState
      : true;
  };
  const unregisteredOnly = roundRunning && query.filter === "unregistered";
  const [selected, setSelected] = useState([]);

  const writable = can("mentorship.admin.write");

  const needle = term.trim().toLowerCase();

  /**
   * Who can go into a matching run right now — the rule is in eligibility.js,
   * shared with the re-check made when a run is published.
   *
   * Unmatched people are in. A matched person is in only while they have a
   * free slot — a mentor with three places and two mentees, or anyone whose
   * pair has ended. A matched mentee with an active pair, or a mentor at
   * their cap, is out: sending them would offer places that do not exist.
   */
  const withSlots = participants.map((p) => {
    const blocker = matchingBlocker(p, {
      pairs,
      account: accountOf(p.userId),
      exempt: exemptParticipantIds.has(p.participantId),
      historyIssues: p.historyIssues ?? [],
    });
    return { ...p, freeSlots: freeSlotsOf(p, pairs), blocker };
  });
  const inPool = (p) => p.blocker === null;
  const count = (reason) =>
    withSlots.filter((p) => p.blocker === reason).length;
  const leftOut = {
    blocked: count("blocked") + count("deactivated"),
    full: count("full"),
    onboarding: count("training"),
    other: count("status"),
  };

  // The ordinary filters — search, role, identity, training, notification —
  // narrow the Needs exemption list and its count the same way they narrow
  // every other list, so the number on the button is the number it opens.
  const passesBasics = (p) =>
    (role === "all" || p.role === role) &&
    (identity === "all" || p.identity === identity) &&
    (onboarding === "all" || (onboarding === "done") === p.onboardingDone) &&
    passesEmail(p) &&
    (!needle ||
      p.name.toLowerCase().includes(needle) ||
      p.email.toLowerCase().includes(needle));
  const waitingOnExemption = withSlots.filter(
    (p) => p.blocker === "history" && passesBasics(p),
  );

  const rows = withSlots.filter(
    (p) =>
      (!eligibleOnly || inPool(p)) &&
      (!exemptionOnly || p.blocker === "history") &&
      passesBasics(p),
  );

  const running = matchRun?.status === "running";
  const runChosen = rows.filter(
    (p) => selected.includes(p.participantId) && inPool(p),
  );
  const runReady =
    !running &&
    runChosen.some((p) => p.role === "mentor") &&
    runChosen.some((p) => p.role === "mentee");

  /**
   * The registered and the unregistered are offered different notifications.
   * Crossing between them drops a notification filter the other side has no
   * such step for, rather than keep narrowing by something the control can
   * no longer show.
   */
  const setFilter = (next) => {
    setSelected([]);
    const filter = query.filter === next ? "" : next;
    const steps = stepsFor(filter !== "unregistered");
    const keepEmail = steps.some((s) => s.key === emailStep);
    onQueryChange({
      filter,
      ...(keepEmail ? {} : { email: "", emailState: "" }),
    });
  };

  const nonParticipantRows = nonParticipants.filter(
    (p) =>
      (identity === "all" || p.identity === identity) &&
      passesEmail({ userId: p.userId, roundId: round.id }) &&
      (!needle ||
        p.name.toLowerCase().includes(needle) ||
        p.email.toLowerCase().includes(needle)),
  );

  const toggle = (id) =>
    setSelected((all) =>
      all.includes(id) ? all.filter((x) => x !== id) : [...all, id],
    );

  const selectedPeople = participants.filter((p) =>
    selected.includes(p.participantId),
  );
  const pressed = {
    eligible: eligibleOnly,
    needs_exemption: exemptionOnly,
    unregistered: unregisteredOnly,
  };

  return (
    <>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Input
          value={term}
          onChange={(e) => onQueryChange({ q: e.target.value })}
          placeholder="Search name or email"
          className="h-8 w-56 text-sm"
        />
        {tab === "participants" ? (
          <>
            <Select
              value={role}
              onValueChange={(v) => onQueryChange({ role: v })}
            >
              <SelectTrigger className="h-8 w-32 text-xs">
                <SelectValue placeholder="Role" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All roles</SelectItem>
                <SelectItem value="mentor">Mentor</SelectItem>
                <SelectItem value="mentee">Mentee</SelectItem>
              </SelectContent>
            </Select>
            <Select
              value={identity}
              onValueChange={(v) => onQueryChange({ identity: v })}
            >
              <SelectTrigger className="h-8 w-40 text-xs">
                <SelectValue placeholder="Internal / external" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Internal & external</SelectItem>
                <SelectItem value="internal">Internal</SelectItem>
                <SelectItem value="external">External</SelectItem>
              </SelectContent>
            </Select>
          </>
        ) : null}
        {tab === "participants" ? (
          <>
            <Select
              value={onboarding}
              onValueChange={(v) => onQueryChange({ onboarding: v })}
            >
              <SelectTrigger className="h-8 w-40 text-xs">
                <SelectValue placeholder="Training" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Any training</SelectItem>
                <SelectItem value="done">Training done</SelectItem>
                <SelectItem value="not_done">Training not done</SelectItem>
              </SelectContent>
            </Select>
            <NotificationFilter
              steps={stepsFor(!unregisteredOnly)}
              step={emailStep}
              state={emailState}
              onChange={onQueryChange}
            />
            {[
              {
                key: "eligible",
                label: "Eligible for matching",
                disabled: !roundRunning,
                title: roundRunning
                  ? undefined
                  : "Only while the round is running, from recruitment to its end",
              },
              {
                key: "needs_exemption",
                // Counted on every visit, listed on demand: a number cannot be
                // missed the way a list nobody opens can, and it costs no room.
                label:
                  matchingOpen && waitingOnExemption.length
                    ? `Needs exemption · ${waitingOnExemption.length}`
                    : "Needs exemption",
                disabled: !matchingOpen,
                // Stands out while someone is waiting: it is the one filter
                // that means there is something to do.
                urgent: matchingOpen && waitingOnExemption.length > 0,
                title: matchingOpen
                  ? "Registered people whose past needs an exemption before they can be matched"
                  : `Only until this round's matching closes (${round.timeline.matchNotificationAt})`,
              },
              {
                key: "unregistered",
                label: "Not registered for this round",
                disabled: !roundRunning,
                title: roundRunning
                  ? undefined
                  : "Only while the round is running, from recruitment to its end",
              },
            ].map((f) => (
              <button
                key={f.key}
                type="button"
                aria-pressed={pressed[f.key]}
                disabled={f.disabled}
                title={f.title}
                onClick={() => setFilter(f.key)}
                className={`h-8 rounded-md border px-3 text-xs transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
                  f.urgent
                    ? pressed[f.key]
                      ? "border-amber-600 bg-amber-600 font-medium text-white"
                      : "border-amber-400 bg-amber-100 font-medium text-amber-900 hover:bg-amber-200"
                    : pressed[f.key]
                      ? "border-slate-900 bg-slate-900 text-white"
                      : "border-slate-300 text-slate-600 hover:bg-slate-100"
                }`}
              >
                {f.label}
              </button>
            ))}
          </>
        ) : null}
      </div>

      {tab === "participants" &&
      !query.filter &&
      roundRunning &&
      nonParticipants.length > 0 ? (
        <p className="mb-2 text-xs text-slate-500">
          {nonParticipants.length} people in the programme have not registered
          for {round.name}.{" "}
          <button
            type="button"
            className="font-medium text-slate-700 underline underline-offset-2"
            onClick={() => setFilter("unregistered")}
          >
            Show them
          </button>
        </p>
      ) : null}

      {tab === "participants" && unregisteredOnly ? (
        <>
          <p className="mb-2 text-xs text-slate-500">
            In the programme — admitted to a mentor or mentee posting, or
            registered for an earlier round — and not registered for{" "}
            {round.name}. This is who a new round&apos;s invitation and the
            onboarding reminders go to.
          </p>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-8" />
                <TableHead>Name</TableHead>
                <TableHead>Int / ext</TableHead>
                <TableHead>Account</TableHead>
                <TableHead>Notifications</TableHead>
                <TableHead>Mentor training</TableHead>
                <TableHead>Mentee training</TableHead>
                <TableHead>Last took part</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {nonParticipantRows.map((p) => {
                return (
                  <TableRow key={p.userId}>
                    <TableCell>
                      <Checkbox
                        aria-label={`Select ${p.name}`}
                        checked={selected.includes(`u${p.userId}`)}
                        onCheckedChange={() => toggle(`u${p.userId}`)}
                      />
                    </TableCell>
                    <TableCell>
                      <button
                        type="button"
                        className="text-left font-medium underline-offset-2 hover:underline"
                        onClick={() => onOpenPerson(p.userId)}
                      >
                        {p.name}
                      </button>
                      <div className="text-xs text-slate-500">{p.email}</div>
                    </TableCell>
                    <TableCell className="text-sm">{p.identity}</TableCell>
                    <TableCell>
                      <AccountStateChips {...accountOf(p.userId)} />
                    </TableCell>
                    <TableCell>
                      <EmailDots
                        person={{ userId: p.userId, roundId: round.id }}
                        registered={false}
                        emails={emails}
                        notes={notes}
                        notifications={notifications}
                        onOpen={() => onOpenPerson(p.userId, "email")}
                      />
                    </TableCell>
                    <TableCell className="text-sm">
                      {p.mentorOnboarding ?? "—"}
                    </TableCell>
                    <TableCell className="text-sm">
                      {p.menteeOnboarding ?? "—"}
                    </TableCell>
                    <TableCell className="text-sm">
                      {p.lastTookPart ?? "Never"}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </>
      ) : null}

      {tab === "participants" && eligibleOnly ? (
        <p className="mb-2 text-xs text-slate-500">
          Registered this round, training done, not withdrawn, at least one free
          slot, and nothing in their past waiting on an exemption — everyone
          here can be matched. Not listed: {leftOut.full} matched with no free
          slot · {leftOut.onboarding} training not done · {leftOut.blocked}{" "}
          blocked or deactivated · {leftOut.other} withdrawn or closed out
          {waitingOnExemption.length
            ? ` · ${waitingOnExemption.length} waiting on an exemption (see Needs exemption)`
            : ""}
          .
          {running ? (
            <strong className="ml-1 text-slate-700">
              A matching run is going in this round; no new run can start until
              it finishes.
            </strong>
          ) : null}
        </p>
      ) : null}

      {tab === "participants" && !unregisteredOnly ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-8" />
              <TableHead>Name</TableHead>
              <TableHead>Role</TableHead>
              {exemptionOnly ? <TableHead>Why</TableHead> : null}
              {narrow ? null : (
                <>
                  <TableHead>Int / ext</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Account</TableHead>
                </>
              )}
              {exemptionOnly ? null : <TableHead>Pair</TableHead>}
              {narrow ? null : (
                <>
                  <TableHead>Notifications</TableHead>
                  <TableHead>Training</TableHead>
                </>
              )}
              {eligibleOnly ? <TableHead>Free slots</TableHead> : null}
              {narrow ? <TableHead>Meetings last round</TableHead> : null}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((p) => (
              <TableRow key={p.participantId}>
                <TableCell>
                  <Checkbox
                    checked={selected.includes(p.participantId)}
                    onCheckedChange={() => toggle(p.participantId)}
                  />
                </TableCell>
                <TableCell>
                  <button
                    type="button"
                    className="text-left font-medium underline-offset-2 hover:underline"
                    onClick={() => onOpenParticipant(p.participantId)}
                  >
                    {p.name}
                  </button>
                  <div className="text-xs text-slate-500">{p.email}</div>
                </TableCell>
                <TableCell className="text-sm">{p.role}</TableCell>
                {exemptionOnly ? (
                  <TableCell className="text-xs text-amber-900">
                    <ul className="space-y-0.5">
                      {p.historyIssues.map((issue) => (
                        <li key={issue}>{issue}</li>
                      ))}
                    </ul>
                  </TableCell>
                ) : null}
                {narrow ? null : (
                  <>
                    <TableCell className="text-sm">{p.identity}</TableCell>
                    <TableCell>
                      <div className="flex flex-col items-start gap-1">
                        <Badge variant="secondary">{p.approvalStatus}</Badge>
                        <FlagBadges
                          stacked
                          flags={flagsByParticipant[p.participantId]}
                        />
                      </div>
                    </TableCell>
                    <TableCell>
                      <AccountStateChips {...accountOf(p.userId)} />
                    </TableCell>
                  </>
                )}
                {exemptionOnly ? null : (
                  <TableCell>
                    <PairCell
                      person={p}
                      pairs={pairs}
                      writable={writable}
                      onMarkFirstContact={(pairId) =>
                        onMarkCell(pairId, "firstContact")
                      }
                    />
                  </TableCell>
                )}
                {narrow ? null : (
                  <>
                    <TableCell>
                      <EmailDots
                        person={p}
                        registered
                        emails={emails}
                        notes={notes}
                        notifications={notifications}
                        onOpen={() =>
                          onOpenParticipant(p.participantId, "email")
                        }
                      />
                    </TableCell>
                    <TableCell className="text-sm">
                      {p.onboardingDone ? "Done" : "Not done"}
                    </TableCell>
                  </>
                )}
                {eligibleOnly ? (
                  <TableCell className="text-sm">
                    {p.freeSlots} of {capacityOf(p)}
                  </TableCell>
                ) : null}
                {narrow ? (
                  <TableCell className="text-sm">
                    <LastRound value={p.lastRound} />
                  </TableCell>
                ) : null}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : null}

      {unregisteredOnly &&
      tab === "participants" &&
      selected.length > 0 &&
      writable ? (
        <div className="mt-4 flex flex-wrap items-center gap-3 rounded-md border border-slate-200 bg-slate-50 px-4 py-3">
          <span className="text-sm">
            <strong>{selected.length} people</strong> selected
          </span>
          <Button
            size="sm"
            onClick={() =>
              onCompose(
                nonParticipantRows
                  .filter((p) => selected.includes(`u${p.userId}`))
                  .map(({ userId, name }) => ({ userId, name })),
                "mentorship_round_recruitment",
              )
            }
          >
            Send email · {selected.length}
          </Button>
          <span className="text-xs text-slate-500">
            Invited some other way, such as on Teams? Mark each person on their
            own page, with a note of how it was sent.
          </span>
        </div>
      ) : null}

      {!(unregisteredOnly && tab === "participants") &&
      selected.length > 0 &&
      writable ? (
        <div className="mt-4 flex flex-wrap items-center gap-3 rounded-md border border-slate-200 bg-slate-50 px-4 py-3">
          <span className="text-sm">
            <strong>{selected.length} people</strong> selected
          </span>
          <Button
            size="sm"
            onClick={() =>
              onCompose(
                selectedPeople.map(({ participantId, name }) => ({
                  participantId,
                  name,
                })),
              )
            }
          >
            Send email · {selected.length}
          </Button>
          {tab === "participants" && eligibleOnly ? (
            <Button
              size="sm"
              disabled={!runReady}
              title={
                running
                  ? "A run is already going in this round"
                  : runReady
                    ? "Each mentor goes in with the slots they have left, not their cap"
                    : "A run needs at least one mentor and one mentee"
              }
              onClick={() => {
                onRunMatching(runChosen);
                setSelected([]);
              }}
            >
              Run matching · {runChosen.length}
            </Button>
          ) : null}
          <span className="text-xs text-slate-500">
            Notified some other way, such as on Teams? Mark each person on their
            own page, with a note of how it was sent.
          </span>
        </div>
      ) : null}
    </>
  );
};

export default ParticipantsTable;
