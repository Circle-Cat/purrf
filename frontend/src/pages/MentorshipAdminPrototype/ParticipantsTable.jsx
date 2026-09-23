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
import {
  RECORDED_TAGS,
  NOTE_LABELS,
  accountStateOf,
} from "@/pages/MentorshipAdminPrototype/mockData";

/**
 * Statuses that can go into a run. `un_matched` is included: being confirmed
 * as not matched in one run does not rule someone out of the next.
 */
const POOL_STATUSES = ["signed_up", "matched", "un_matched"];

/** A mentee always takes one mentor; a mentor takes up to their own cap. */
const capacityOf = (person) =>
  person.role === "mentor" ? (person.maxPartners ?? 1) : 1;

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
 * The person axis and the pair axis, as two tabs of one card.
 *
 * Bob Liu carries two mentees. He is one row under Participants and two rows
 * under Pairs, and that difference is the reason the two axes exist at all: a
 * question about a person ("has she registered?") and a question about a
 * pairing ("have they met yet?") cannot be answered by the same row.
 *
 * The tab and every filter come from `query`, which is the URL. Open the third
 * person on a filtered list, come back, and the list is still filtered — the
 * selection is the one thing that deliberately does not survive.
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
  onBulkMark,
  onConfirmUnmatched,
  flagsByParticipant = {},
  exemptParticipantIds = new Set(),
  matchRun = null,
  onRunMatching,
  notes = [],
  notifications = [],
  emails = [],
  onBulkMarkUnregistered,
  onOpenPerson,
}) => {
  // One table since the pair axis was folded into it; kept as a name so the
  // conditions below still read as "on the person table".
  const tab = "participants";
  const term = query.q ?? "";
  const role = query.role ?? "all";
  const identity = query.identity ?? "all";
  const onboarding = query.onboarding ?? "all";
  const eligibleOnly = query.filter === "eligible";
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
  const unregisteredOnly = query.filter === "unregistered";
  const [selected, setSelected] = useState([]);
  const [bulkTag, setBulkTag] = useState(RECORDED_TAGS[3]);
  const [unregisteredTag, setUnregisteredTag] = useState("round_invitation");

  const writable = can("mentorship.admin.write");

  const needle = term.trim().toLowerCase();

  /**
   * Who can go into a matching run right now.
   *
   * Registered this round, onboarding done, not withdrawn, and a free slot.
   * Unmatched people are in. A matched person is in only while they have a
   * free slot — a mentor with three places and two mentees, or anyone whose
   * pair has ended. A matched mentee with an active pair, or a mentor at
   * their cap, is out: sending them would offer places that do not exist.
   *
   * This is a filter on the person axis rather than a table of its own: the
   * people are the same people, and the rule has to be enforced where the
   * list is assembled anyway.
   */
  const activePairsOf = (userId) =>
    pairs.filter(
      (p) =>
        p.status === "active" &&
        (p.mentorId === userId || p.menteeId === userId),
    ).length;
  const withSlots = participants.map((p) => ({
    ...p,
    freeSlots: capacityOf(p) - activePairsOf(p.userId),
  }));
  const isBlocked = (p) => accountStateOf(p.userId).isBlocked;
  const isDeactivated = (p) => !accountStateOf(p.userId).isActive;
  const isExempt = (p) => exemptParticipantIds.has(p.participantId);
  const needsExemption = (p) =>
    (p.historyIssues ?? []).length > 0 && !isExempt(p);
  /**
   * Blocked and deactivated accounts never go in. Training has to be done —
   * there is no exemption for it. A past that needs looking at (a mentee short
   * of the meetings in their latest round, a no show there, a red flag ever)
   * keeps someone out until an exemption is approved for this round; an
   * exemption stands in for that and nothing else.
   */
  const inPool = (p) =>
    !isBlocked(p) &&
    !isDeactivated(p) &&
    p.onboardingDone &&
    !needsExemption(p) &&
    POOL_STATUSES.includes(p.approvalStatus) &&
    p.freeSlots > 0;
  const waitingOnExemption = withSlots.filter(
    (p) =>
      needsExemption(p) &&
      !isBlocked(p) &&
      !isDeactivated(p) &&
      p.onboardingDone &&
      POOL_STATUSES.includes(p.approvalStatus) &&
      p.freeSlots > 0,
  );
  const leftOut = {
    blocked: withSlots.filter((p) => isBlocked(p) || isDeactivated(p)).length,
    full: withSlots.filter(
      (p) =>
        !isBlocked(p) && p.approvalStatus === "matched" && p.freeSlots <= 0,
    ).length,
    onboarding: withSlots.filter(
      (p) =>
        !p.onboardingDone &&
        !isBlocked(p) &&
        !isDeactivated(p) &&
        POOL_STATUSES.includes(p.approvalStatus),
    ).length,
    other: withSlots.filter(
      (p) => !isBlocked(p) && !POOL_STATUSES.includes(p.approvalStatus),
    ).length,
  };

  const rows = withSlots.filter(
    (p) =>
      (!eligibleOnly || inPool(p)) &&
      (role === "all" || p.role === role) &&
      (identity === "all" || p.identity === identity) &&
      (onboarding === "all" || (onboarding === "done") === p.onboardingDone) &&
      passesEmail(p) &&
      (!needle ||
        p.name.toLowerCase().includes(needle) ||
        p.email.toLowerCase().includes(needle)),
  );

  const running = matchRun?.status === "running";
  const runChosen = rows.filter(
    (p) => selected.includes(p.participantId) && inPool(p),
  );
  const runReady =
    !running &&
    runChosen.some((p) => p.role === "mentor") &&
    runChosen.some((p) => p.role === "mentee");

  const setFilter = (next) => {
    setSelected([]);
    onQueryChange({ filter: query.filter === next ? "" : next });
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
  /** Only someone still waiting to be matched can be confirmed as unmatched. */
  const unmatchable = selectedPeople.filter(
    (p) => p.approvalStatus === "signed_up",
  );

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
              { key: "eligible", label: "Eligible for matching" },
              { key: "unregistered", label: "Not registered for this round" },
            ].map((f) => (
              <button
                key={f.key}
                type="button"
                aria-pressed={query.filter === f.key}
                onClick={() => setFilter(f.key)}
                className={`h-8 rounded-md border px-3 text-xs transition-colors ${
                  query.filter === f.key
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

      {tab === "participants" && !query.filter && nonParticipants.length > 0 ? (
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
                      <AccountStateChips {...accountStateOf(p.userId)} />
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
          slot, and nothing in their past waiting on an exemption. Not listed:{" "}
          {leftOut.full} matched with no free slot · {leftOut.onboarding}{" "}
          training not done · {leftOut.blocked} blocked or deactivated ·{" "}
          {leftOut.other} withdrawn or closed out.
          {running ? (
            <strong className="ml-1 text-slate-700">
              A matching run is going in this round; no new run can start until
              it finishes.
            </strong>
          ) : null}
        </p>
      ) : null}
      {tab === "participants" && eligibleOnly && waitingOnExemption.length ? (
        <div className="mb-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          <p className="font-medium">
            {waitingOnExemption.length} need an exemption before they can be
            matched:
          </p>
          <ul className="mt-1 space-y-0.5">
            {waitingOnExemption.map((p) => (
              <li key={p.participantId}>
                <button
                  type="button"
                  className="font-medium underline underline-offset-2"
                  onClick={() => onOpenParticipant(p.participantId)}
                >
                  {p.name}
                </button>{" "}
                — {p.historyIssues.join("; ")}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {tab === "participants" && !unregisteredOnly ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-8" />
              <TableHead>Name</TableHead>
              <TableHead>Role</TableHead>
              {eligibleOnly ? null : (
                <>
                  <TableHead>Int / ext</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Account</TableHead>
                </>
              )}
              <TableHead>Pair</TableHead>
              {eligibleOnly ? null : (
                <>
                  <TableHead>Notifications</TableHead>
                  <TableHead>Training</TableHead>
                </>
              )}
              {eligibleOnly ? (
                <>
                  <TableHead>Free slots</TableHead>
                  <TableHead>Meetings last round</TableHead>
                </>
              ) : null}
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
                {eligibleOnly ? null : (
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
                      <AccountStateChips {...accountStateOf(p.userId)} />
                    </TableCell>
                  </>
                )}
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
                {eligibleOnly ? null : (
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
                  <>
                    <TableCell className="text-sm">
                      {p.freeSlots} of {capacityOf(p)}
                    </TableCell>
                    <TableCell className="text-sm">
                      <LastRound value={p.lastRound} />
                    </TableCell>
                  </>
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
          <div className="flex items-center gap-2">
            <Select value={unregisteredTag} onValueChange={setUnregisteredTag}>
              <SelectTrigger className="h-8 w-52 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[
                  "round_invitation",
                  "admission_notice",
                  "onboarding_reminder",
                ].map((t) => (
                  <SelectItem key={t} value={t}>
                    {NOTE_LABELS[t]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                onBulkMarkUnregistered(
                  nonParticipantRows
                    .filter((p) => selected.includes(`u${p.userId}`))
                    .map((p) => p.userId),
                  unregisteredTag,
                );
                setSelected([]);
              }}
            >
              Mark as notified
            </Button>
          </div>
          <span className="text-xs text-slate-500">
            For invitations and reminders sent on Teams. The note is kept
            against the person and this round, so it is on their timeline if
            they register.
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
          <div className="flex items-center gap-2">
            <Select value={bulkTag} onValueChange={setBulkTag}>
              <SelectTrigger className="h-8 w-52 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {RECORDED_TAGS.filter((t) => t !== "round_invitation").map(
                  (t) => (
                    <SelectItem key={t} value={t}>
                      {NOTE_LABELS[t]}
                    </SelectItem>
                  ),
                )}
              </SelectContent>
            </Select>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                onBulkMark(selected, bulkTag);
                setSelected([]);
              }}
            >
              Mark as notified
            </Button>
          </div>
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
          {tab === "participants" ? (
            <Button
              size="sm"
              variant="outline"
              disabled={unmatchable.length === 0}
              title="Only people still signed up can be confirmed as unmatched"
              onClick={() => {
                onConfirmUnmatched(unmatchable);
                setSelected([]);
              }}
            >
              Confirm as unmatched · {unmatchable.length}
            </Button>
          ) : null}
          <span className="text-xs text-slate-500">
            Reminders to internal members go out on Teams, which Purrf cannot
            send — so they are marked here after the fact, in one go.
          </span>
        </div>
      ) : null}
    </>
  );
};

export default ParticipantsTable;
