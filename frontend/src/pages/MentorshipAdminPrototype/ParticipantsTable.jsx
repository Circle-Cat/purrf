import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
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
} from "@/pages/MentorshipAdminPrototype/mockData";

const TABS = [
  { key: "participants", label: "Participants" },
  { key: "non-participants", label: "Non-participants" },
  { key: "pairs", label: "Pairs" },
];

/**
 * How many meetings someone held *in the round they last took part in*.
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
  nonParticipants,
  pairs,
  can,
  onOpenParticipant,
  onOpenPair,
  onMarkCell,
  onCompose,
  onBulkMark,
  onConfirmUnmatched,
}) => {
  const tab = query.tab ?? "participants";
  const term = query.q ?? "";
  const role = query.role ?? "all";
  const identity = query.identity ?? "all";
  const onboarding = query.onboarding ?? "all";
  const pairStatus = query.pairStatus ?? "all";
  const [selected, setSelected] = useState([]);
  const [bulkTag, setBulkTag] = useState(RECORDED_TAGS[3]);

  const writable = can("mentorship.admin.write");

  const needle = term.trim().toLowerCase();

  const rows = useMemo(
    () =>
      participants.filter(
        (p) =>
          (role === "all" || p.role === role) &&
          (identity === "all" || p.identity === identity) &&
          (onboarding === "all" ||
            (onboarding === "done") === p.onboardingDone) &&
          (!needle ||
            p.name.toLowerCase().includes(needle) ||
            p.email.toLowerCase().includes(needle)),
      ),
    [participants, role, identity, onboarding, needle],
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

  const nonParticipantRows = nonParticipants.filter(
    (p) =>
      !needle ||
      p.name.toLowerCase().includes(needle) ||
      p.email.toLowerCase().includes(needle),
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
          </>
        ) : null}
      </div>

      {tab === "participants" ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-8" />
              <TableHead>Name</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Int / ext</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Onboarding</TableHead>
              <TableHead>Meetings last round</TableHead>
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
                </TableCell>
                <TableCell className="text-sm">
                  {p.onboardingDone ? "Done" : "Not done"}
                </TableCell>
                <TableCell className="text-sm">
                  <LastRound value={p.lastRound} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : null}

      {tab === "non-participants" ? (
        <>
          <p className="mb-2 text-xs text-slate-500">
            Admitted to a mentorship posting but not registered for this round.
            They are not filtered out of the Participants tab — they were never
            in it.
          </p>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Int / ext</TableHead>
                <TableHead>Mentor onboarding</TableHead>
                <TableHead>Mentee onboarding</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {nonParticipantRows.map((p) => (
                <TableRow key={p.userId}>
                  <TableCell>
                    <div className="font-medium">{p.name}</div>
                    <div className="text-xs text-slate-500">{p.email}</div>
                  </TableCell>
                  <TableCell className="text-sm">{p.identity}</TableCell>
                  <TableCell className="text-sm">
                    {p.mentorOnboarding ?? "—"}
                  </TableCell>
                  <TableCell className="text-sm">
                    {p.menteeOnboarding ?? "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </>
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

      {selected.length > 0 && writable ? (
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
                {RECORDED_TAGS.map((t) => (
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
