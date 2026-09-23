import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import FlagBadges from "@/pages/MentorshipAdminPrototype/FlagBadges";
import AccountStateChips from "@/pages/MentorshipAdminPrototype/AccountStateChips";
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
  TEMPLATE_LABELS,
  accountStateOf,
} from "@/pages/MentorshipAdminPrototype/mockData";

const TABS = [
  { key: "participants", label: "Participants" },
  { key: "pairs", label: "Pairs" },
];

/**
 * Statuses that can go into a run. `un_matched` is included: being confirmed
 * as not matched in one run does not rule someone out of the next.
 */
const POOL_STATUSES = ["signed_up", "matched", "un_matched"];

/** A mentee always takes one mentor; a mentor takes up to their own cap. */
const capacityOf = (person) =>
  person.role === "mentor" ? (person.maxPartners ?? 1) : 1;

/**
 * How many meetings someone held *in the round they last took part in*.
 *
 * Shown only under the "Eligible for matching" filter: it is a signal for
 * choosing who goes into a run, and outside matching it answers nothing
 * anyone is asking.
 *
 * Four answers, and only one of them is the number zero. Rendering "never took
 * part" and "was not matched" as 0 would sort a brand-new participant to the
 * top of the chase list, which is exactly backwards.
 */
const LastRound = ({ value }) => {
  if (value.kind === "first-time")
    return <span className="text-slate-500">First time</span>;
  if (value.kind === "unmatched")
    return <span className="text-slate-500">Not matched</span>;
  if (value.kind === "unknown")
    return <span className="text-slate-400">Unknown</span>;
  return (
    <span>
      {value.completed}/{value.required}
    </span>
  );
};

const Mark = ({ on, label, onClick, disabled }) => (
  <button
    type="button"
    disabled={disabled}
    onClick={(e) => {
      e.stopPropagation();
      onClick();
    }}
    title={label}
    className={`rounded px-2 py-0.5 text-xs transition-colors ${
      on
        ? "bg-emerald-100 text-emerald-800"
        : "border border-slate-300 text-slate-400 hover:bg-slate-100"
    } ${disabled ? "cursor-default opacity-60" : ""}`}
  >
    {on ? label : "Mark"}
  </button>
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
  onOpenPair,
  onMarkCell,
  onCompose,
  onBulkMark,
  onConfirmUnmatched,
  flagsByParticipant = {},
  exemptParticipantIds = new Set(),
  emails = [],
  onBulkMarkUnregistered,
  onOpenPerson,
}) => {
  const tab = query.tab ?? "participants";
  const term = query.q ?? "";
  const role = query.role ?? "all";
  const identity = query.identity ?? "all";
  const onboarding = query.onboarding ?? "all";
  const pairStatus = query.pairStatus ?? "all";
  const eligibleOnly = query.filter === "eligible";
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
  const isExempt = (p) => exemptParticipantIds.has(p.participantId);
  /**
   * An approved exemption stands in for onboarding and for nothing else: a
   * block is final, a withdrawal is the person's own choice, and a full slot
   * is a place that does not exist.
   */
  const inPool = (p) =>
    !isBlocked(p) &&
    (p.onboardingDone || isExempt(p)) &&
    POOL_STATUSES.includes(p.approvalStatus) &&
    p.freeSlots > 0;
  const leftOut = {
    blocked: withSlots.filter((p) => isBlocked(p)).length,
    full: withSlots.filter(
      (p) =>
        !isBlocked(p) && p.approvalStatus === "matched" && p.freeSlots <= 0,
    ).length,
    onboarding: withSlots.filter(
      (p) =>
        !p.onboardingDone &&
        !isExempt(p) &&
        !isBlocked(p) &&
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
      (!needle ||
        p.name.toLowerCase().includes(needle) ||
        p.email.toLowerCase().includes(needle)),
  );

  /** Searching on this tab finds a pair by either side — "who is Bob paired with". */
  const pairRows = useMemo(
    () =>
      pairs.filter(
        (p) =>
          (pairStatus === "all" || p.status === pairStatus) &&
          (!needle ||
            p.mentorName.toLowerCase().includes(needle) ||
            p.menteeName.toLowerCase().includes(needle)),
      ),
    [pairs, pairStatus, needle],
  );

  const [exported, setExported] = useState(null);

  const exportChosen = rows.filter(
    (p) => selected.includes(p.participantId) && inPool(p),
  );
  const exportMentors = exportChosen.filter((p) => p.role === "mentor");
  const exportReady =
    exportMentors.length > 0 && exportChosen.some((p) => p.role === "mentee");
  const exportForMatching = () => {
    const partial = exportMentors.filter((m) => m.freeSlots < capacityOf(m));
    setExported(
      `Exported ${exportChosen.length} people for matching.` +
        (partial.length
          ? ` ${partial
              .map(
                (m) =>
                  `${m.name} goes in with ${m.freeSlots} slot${
                    m.freeSlots === 1 ? "" : "s"
                  }, not ${capacityOf(m)}`,
              )
              .join("; ")} — the places already taken stay taken.`
          : ""),
    );
    setSelected([]);
  };

  /** The latest email to someone about the selected round, so nobody is invited twice. */
  const lastEmailTo = (userId) =>
    emails
      .filter(
        (e) =>
          e.userId === userId &&
          e.roundId === round.id &&
          e.direction === "out",
      )
      .sort((a, b) => b.at.localeCompare(a.at))[0];

  const setFilter = (next) => {
    setSelected([]);
    setExported(null);
    onQueryChange({ filter: query.filter === next ? "" : next });
  };

  const nonParticipantRows = nonParticipants.filter(
    (p) =>
      (identity === "all" || p.identity === identity) &&
      (!needle ||
        p.name.toLowerCase().includes(needle) ||
        p.email.toLowerCase().includes(needle)),
  );

  /** The mentee's participant row is where a pair's mid-term mark actually lives. */
  const participantOf = (userId) =>
    participants.find((p) => p.userId === userId);
  const reminderOf = (userId) => participantOf(userId)?.midtermReminderAt;

  const toggle = (id) =>
    setSelected((all) =>
      all.includes(id) ? all.filter((x) => x !== id) : [...all, id],
    );

  const switchTab = (key) => {
    setSelected([]);
    setExported(null);
    onQueryChange({ tab: key === "participants" ? "" : key });
  };

  const selectedPairs = pairs.filter((p) => selected.includes(p.pairId));
  const selectedPeople = participants.filter((p) =>
    selected.includes(p.participantId),
  );
  /** Only someone still waiting to be matched can be confirmed as unmatched. */
  const unmatchable = selectedPeople.filter(
    (p) => p.approvalStatus === "signed_up",
  );

  return (
    <>
      <div className="mb-3 flex gap-1 border-b border-slate-200">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => switchTab(t.key)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm transition-colors ${
              tab === t.key
                ? "border-slate-900 font-medium text-slate-900"
                : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Input
          value={term}
          onChange={(e) => onQueryChange({ q: e.target.value })}
          placeholder={
            tab === "pairs" ? "Search mentor or mentee" : "Search name or email"
          }
          className="h-8 w-56 text-sm"
        />
        {tab === "pairs" ? (
          <Select
            value={pairStatus}
            onValueChange={(v) => onQueryChange({ pairStatus: v })}
          >
            <SelectTrigger className="h-8 w-36 text-xs">
              <SelectValue placeholder="Pair status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Any pair status</SelectItem>
              <SelectItem value="active">Active</SelectItem>
              <SelectItem value="inactive">Inactive</SelectItem>
            </SelectContent>
          </Select>
        ) : null}
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
                <SelectValue placeholder="Onboarding" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Any onboarding</SelectItem>
                <SelectItem value="done">Onboarding done</SelectItem>
                <SelectItem value="not_done">Onboarding not done</SelectItem>
              </SelectContent>
            </Select>
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
                <TableHead>Mentor onboarding</TableHead>
                <TableHead>Mentee onboarding</TableHead>
                <TableHead>Last took part</TableHead>
                <TableHead>Last email</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {nonParticipantRows.map((p) => {
                const last = lastEmailTo(p.userId);
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
                    <TableCell className="text-sm">
                      {p.mentorOnboarding ?? "—"}
                    </TableCell>
                    <TableCell className="text-sm">
                      {p.menteeOnboarding ?? "—"}
                    </TableCell>
                    <TableCell className="text-sm">
                      {p.lastTookPart ?? "Never"}
                    </TableCell>
                    <TableCell className="text-sm">
                      {last
                        ? `${TEMPLATE_LABELS[last.templateKey]} · ${last.at}`
                        : "—"}
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
          Registered this round, onboarding done, not withdrawn, and at least
          one free slot; an approved exemption stands in for onboarding. Not
          listed: {leftOut.full} matched with no free slot ·{" "}
          {leftOut.onboarding} onboarding not done · {leftOut.blocked} blocked ·{" "}
          {leftOut.other} withdrawn or closed out.
        </p>
      ) : null}

      {tab === "participants" && !unregisteredOnly ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-8" />
              <TableHead>Name</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Int / ext</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Account</TableHead>
              <TableHead>Onboarding</TableHead>
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
                <TableCell className="text-sm">{p.identity}</TableCell>
                <TableCell>
                  <Badge variant="secondary">{p.approvalStatus}</Badge>
                  <FlagBadges flags={flagsByParticipant[p.participantId]} />
                </TableCell>
                <TableCell>
                  <AccountStateChips {...accountStateOf(p.userId)} />
                </TableCell>
                <TableCell className="text-sm">
                  {p.onboardingDone ? "Done" : "Not done"}
                  {!p.onboardingDone && isExempt(p) ? (
                    <Badge
                      variant="outline"
                      className="ml-1 border-amber-300 bg-amber-50 text-amber-900"
                    >
                      Exempted
                    </Badge>
                  ) : null}
                </TableCell>
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

      {tab === "pairs" ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-8" />
              <TableHead>Mentor</TableHead>
              <TableHead>Mentee</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>First contact</TableHead>
              <TableHead>Meetings</TableHead>
              <TableHead>Mentee reminder</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {pairRows.map((p) => (
              <TableRow
                key={p.pairId}
                tabIndex={0}
                aria-label={`Open pair ${p.mentorName} and ${p.menteeName}`}
                className="cursor-pointer"
                onClick={() => onOpenPair(p.pairId)}
                onKeyDown={(e) => e.key === "Enter" && onOpenPair(p.pairId)}
              >
                <TableCell onClick={(e) => e.stopPropagation()}>
                  <Checkbox
                    checked={selected.includes(p.pairId)}
                    onCheckedChange={() => toggle(p.pairId)}
                  />
                </TableCell>
                <TableCell className="text-sm">{p.mentorName}</TableCell>
                <TableCell className="text-sm">{p.menteeName}</TableCell>
                <TableCell>
                  <Badge
                    variant={p.status === "active" ? "secondary" : "outline"}
                  >
                    {p.status}
                  </Badge>
                </TableCell>
                <TableCell>
                  <Mark
                    on={Boolean(p.firstContactConfirmedAt)}
                    label={p.firstContactConfirmedAt ?? "Mark"}
                    disabled={!writable}
                    onClick={() => onMarkCell(p.pairId, "firstContact")}
                  />
                </TableCell>
                <TableCell className="text-sm">
                  {p.completed}/{p.required}
                </TableCell>
                <TableCell>
                  <Mark
                    on={Boolean(reminderOf(p.menteeId))}
                    label={reminderOf(p.menteeId) ?? "Mark"}
                    disabled={!writable}
                    onClick={() => onMarkCell(p.pairId, "midterm")}
                  />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : null}

      {exported ? (
        <p className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
          {exported}
        </p>
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
                {["round_invitation", "onboarding_reminder"].map((t) => (
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
              Mark as sent
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
            {tab === "pairs" ? (
              <>
                <strong>{selected.length} pairs</strong> selected —{" "}
                <strong>{selected.length * 2} people</strong>
              </>
            ) : (
              <>
                <strong>{selected.length} people</strong> selected
              </>
            )}
          </span>
          <Button
            size="sm"
            onClick={() =>
              onCompose(
                tab === "pairs"
                  ? selectedPairs.flatMap((p) =>
                      [participantOf(p.mentorId), participantOf(p.menteeId)]
                        .filter(Boolean)
                        .map(({ participantId, name }) => ({
                          participantId,
                          name,
                        })),
                    )
                  : selectedPeople.map(({ participantId, name }) => ({
                      participantId,
                      name,
                    })),
              )
            }
          >
            Send email ·{" "}
            {tab === "pairs" ? selected.length * 2 : selected.length}
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
                onBulkMark(
                  tab === "pairs"
                    ? selectedPairs
                        .map((p) => participantOf(p.menteeId)?.participantId)
                        .filter(Boolean)
                    : selected,
                  bulkTag,
                );
                setSelected([]);
              }}
            >
              Mark as sent
            </Button>
          </div>
          {tab === "participants" && eligibleOnly ? (
            <Button
              size="sm"
              disabled={!exportReady}
              title={
                exportReady
                  ? "Each mentor goes in with the slots they have left, not their cap"
                  : "A run needs at least one mentor and one mentee"
              }
              onClick={exportForMatching}
            >
              Export for matching · {exportChosen.length}
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
