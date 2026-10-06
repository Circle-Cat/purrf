import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  Card,
  CardAction,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import Table from "@/components/common/Table";
import { useParticipantSearch } from "@/pages/MentorshipManagement/hooks/useParticipantSearch";
import { useParticipantSearchRounds } from "@/pages/MentorshipManagement/hooks/useParticipantSearchRounds";
import { MentorshipParticipantRoles } from "@/constants/MentorshipParticipantRoles";
import { MentorshipApprovalStatus } from "@/constants/MentorshipApprovalStatus";
import { userDisplayName } from "@/utils/userName";
import MeetingLogDialog from "@/pages/MentorshipManagement/components/MeetingLogDialog";
import StateChips from "@/pages/AdminAccounts/components/StateChips";
import { useMeetingLog } from "@/pages/MentorshipManagement/hooks/useMeetingLog";
import { attendanceIssueLines } from "@/pages/MentorshipManagement/utils/attendanceIssues";
import { useMatchingRun } from "@/pages/MentorshipManagement/hooks/useMatchingRun";
import { RUN_STATUS } from "@/pages/MentorshipManagement/utils/matchingLabels";
import { startMatchingRun } from "@/api/mentorshipApi";
import { useFeatureFlags } from "@/hooks/useFeatureFlags";
import { FEATURE_FLAGS } from "@/constants/FeatureFlags";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

const ALL_ROLES = "__all__";
const ALL_APPROVAL_STATUSES = "__all__";
const ALL_ONBOARDING_STATUSES = "__all__";
const ANY_ACCOUNT = "__all__";
const BOTH_INTERNAL_EXTERNAL = "__all__";
const REGISTERED = "registered";
const NOT_REGISTERED = "not_registered";
const ELIGIBLE = "eligible";

const NO_SELECTION = new Map();

/**
 * Maps table column accessors to backend sort_by field names. Only columns
 * backed by a whitelisted sort field belong here — every other column is
 * unsortable.
 * @type {Record<string, string>}
 */
const ACCESSOR_TO_SORT_FIELD = {
  name: "user_id",
};

const COLUMNS = [
  { header: "Name", accessor: "name", sortable: true },
  { header: "Role", accessor: "role" },
  { header: "Training", accessor: "training" },
  { header: "Int / ext", accessor: "internal" },
  { header: "Approval", accessor: "approval" },
  { header: "Account", accessor: "account" },
  { header: "Pair", accessor: "pair" },
];

/**
 * A column header that explains the column in a tooltip on hover or focus.
 *
 * @param {{ label: string, hint: string }} props
 */
const HintedHeader = ({ label, hint }) => (
  <TooltipProvider>
    <Tooltip>
      <TooltipTrigger asChild>
        <span tabIndex={0} className="cursor-help">
          {label}
        </span>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs font-normal">{hint}</TooltipContent>
    </Tooltip>
  </TooltipProvider>
);

const NOT_REGISTERED_COLUMNS = [
  { header: "Name", accessor: "name", sortable: true },
  { header: "Admitted as", accessor: "admittedAs" },
  { header: "Int / ext", accessor: "internal" },
  { header: "Account", accessor: "account" },
  {
    header: (
      <HintedHeader
        label="Rounds taken part"
        hint="Every round the person registered for, including rounds where they were not matched or stopped early."
      />
    ),
    accessor: "roundsTakenPart",
  },
  { header: "Last round", accessor: "lastRound" },
];

/**
 * @param {string|null} status - An onboarding course status.
 * @returns {string} "No course" when there is no course to take.
 */
const trainingLabel = (status) => {
  if (status == null) return "No course";
  return status === "done" ? "Done" : "Not done";
};

const NameCell = ({ row }) => (
  <>
    <div className="font-medium">{userDisplayName(row)}</div>
    <div className="text-xs text-muted-foreground">
      ID {row.userId}
      {row.primaryEmail ? ` · ${row.primaryEmail}` : ""}
    </div>
  </>
);

/**
 * Active pairs first, ended ones after, each group in pair id order.
 *
 * @param {Array<{pairId: number, partner: {isActive: boolean|null}}>} pairs
 */
const orderPairs = (pairs) =>
  [...pairs].sort(
    (a, b) =>
      Number(a.partner.isActive === false) -
        Number(b.partner.isActive === false) || a.pairId - b.pairId,
  );

/**
 * A red "!" whose tooltip lists a live pair's flagged meetings, one per line.
 *
 * @param {{ lines: string[] }} props
 */
const AttendanceMark = ({ lines }) => (
  <TooltipProvider>
    <Tooltip>
      <TooltipTrigger
        type="button"
        aria-label={`Attendance issues: ${lines.join(", ")}`}
        className="inline-flex h-4 w-4 cursor-help items-center justify-center rounded-full bg-red-600 text-[10px] font-bold text-white"
      >
        !
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">
        {lines.map((line) => (
          <div key={line}>{line}</div>
        ))}
      </TooltipContent>
    </Tooltip>
  </TooltipProvider>
);

/**
 * Every pair the person is in this round, one item each: the partner with
 * their user ID (and Ended when the pairing is over, greyed), and under it
 * the meeting progress that opens that pair's log. A live pair with flagged
 * meetings turns red and carries an attendance mark.
 *
 * @param {{ row: Object, onOpenMeetings: (pair: Object) => void }} props
 */
const PairCell = ({ row, onOpenMeetings }) => {
  if (!row.pairs?.length) return "—";

  const isMentee = row.participantRole === MentorshipParticipantRoles.MENTEE;
  const subjectName = userDisplayName(row);

  return (
    <ul className="space-y-1">
      {orderPairs(row.pairs).map((pair) => {
        const ended = pair.partner.isActive === false;
        const partnerName = userDisplayName(pair.partner);
        const [mentorName, menteeName] = isMentee
          ? [partnerName, subjectName]
          : [subjectName, partnerName];
        const issues = ended
          ? []
          : attendanceIssueLines(pair.attendanceIssues, {
              mentorName,
              menteeName,
            });
        return (
          <li
            key={pair.pairId}
            aria-label={`Pair ${mentorName} and ${menteeName}`}
            className={`flex flex-col items-start gap-0.5 text-xs ${
              ended ? "text-slate-400" : issues.length ? "text-red-700" : ""
            }`}
          >
            <span className="inline-flex flex-wrap items-center gap-x-2">
              <span className="font-medium">
                {`with ${partnerName} (${pair.partner.id})`}
              </span>
              {ended && (
                <span className="rounded border border-slate-200 px-1 text-[10px]">
                  Ended
                </span>
              )}
              {issues.length > 0 && <AttendanceMark lines={issues} />}
            </span>
            <button
              type="button"
              onClick={() => onOpenMeetings(pair)}
              className={`underline hover:opacity-80 ${
                ended || issues.length ? "" : "text-primary"
              }`}
            >
              Meetings {pair.completedMeetingCount}/
              {row.requiredMeetings ?? "—"}
            </button>
          </li>
        );
      })}
    </ul>
  );
};

/**
 * The Participants card: one round's participants, searched by user ID,
 * name/email, role, internal/external, account, training and approval status.
 * The List filter picks which people: everyone registered (the default), only
 * those eligible for matching, or the people admitted to the programme who
 * have not registered for the round. The last two are only offered while the
 * round is in progress.
 *
 * The round is picked in the card header from the rounds the API lists,
 * latest first, and the first is selected by default. Search stays disabled
 * until the rounds have loaded, and when there are none a hint takes the
 * dropdown's place.
 *
 * Every row starts with the person's display name over their user ID and
 * primary email; training is resolved from their role in the round, and the
 * Pair cell lists every pair they are in, each opening its own meeting log.
 *
 * In the Eligible for matching list, while the matching-run flag is on, people
 * can be picked (across pages) and a matching run started for them; a run
 * needs at least one mentor and one mentee, and none may be running in the
 * round. Picks are dropped whenever the list or its filters change. The
 * header's matching results button, also behind the flag, follows the round
 * in the Round select.
 */
const ParticipantSearchCard = () => {
  const rounds = useParticipantSearchRounds();

  const {
    rows,
    total,
    loading,
    hasSearched,
    canSearch,
    userId,
    setUserId,
    q,
    setQ,
    accountStatus,
    setAccountStatus,
    internal,
    setInternal,
    roundId,
    setRoundId,
    participantRole,
    setParticipantRole,
    approvalStatus,
    setApprovalStatus,
    onboardingStatus,
    setOnboardingStatus,
    submitSearch,
    committedRoundId,
    listKey,
    eligible,
    notRegistered,
    listNotRegistered,
    setListNotRegistered,
    canListNotRegistered,
    listEligible,
    setListEligible,
    canListEligible,
    refetch,
    offset,
    limit,
    nextPage,
    prevPage,
    sortBy,
    order,
    toggleSort,
  } = useParticipantSearch(rounds);

  const navigate = useNavigate();
  const location = useLocation();
  const flags = useFeatureFlags();
  // The backend refuses every matching endpoint while the flag is off.
  const matchingOn = Boolean(flags[FEATURE_FLAGS.MATCHING_RUN]);
  const showRunUi = matchingOn && eligible && hasSearched && canSearch;

  const { overview: shownRun } = useMatchingRun(
    matchingOn ? roundId || null : null,
  );
  // The run starts in the committed round, which the Round select may have
  // moved away from without searching.
  const { overview: otherRun } = useMatchingRun(
    showRunUi && committedRoundId !== roundId ? committedRoundId : null,
  );
  const committedRun = committedRoundId === roundId ? shownRun : otherRun;

  const openMatching = (id) =>
    navigate(ROUTE_PATHS.MENTORSHIP_MATCHING(id), {
      state: { returnSearch: location.search },
    });

  // userId -> participantRole, tagged with the list it was picked in.
  const [selection, setSelection] = useState({ key: "", picked: NO_SELECTION });
  const picked = selection.key === listKey ? selection.picked : NO_SELECTION;
  const setPicked = (people, on) => {
    const next = new Map(picked);
    people.forEach((row) =>
      on ? next.set(row.userId, row.participantRole) : next.delete(row.userId),
    );
    setSelection({ key: listKey, picked: next });
  };
  const pickedRoles = [...picked.values()];
  const mentorCount = pickedRoles.filter(
    (r) => r === MentorshipParticipantRoles.MENTOR,
  ).length;
  const menteeCount = pickedRoles.filter(
    (r) => r === MentorshipParticipantRoles.MENTEE,
  ).length;
  const canRun =
    mentorCount > 0 &&
    menteeCount > 0 &&
    committedRun?.status !== RUN_STATUS.RUNNING;
  const committedRoundName =
    (rounds ?? []).find((r) => String(r.id) === committedRoundId)?.name ?? "";

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [starting, setStarting] = useState(false);

  const runMatching = async () => {
    setStarting(true);
    try {
      await startMatchingRun({
        roundId: Number(committedRoundId),
        participantIds: [...picked.keys()],
      });
      setSelection({ key: "", picked: NO_SELECTION });
      setConfirmOpen(false);
      openMatching(committedRoundId);
    } catch (err) {
      toast.error(
        err?.response?.data?.message ?? "Failed to start the matching run",
      );
    } finally {
      setStarting(false);
    }
  };

  const hasPrev = offset > 0;
  const hasNext = offset + limit < total;

  // Snapshot of which pair's dialog is open; drives useMeetingLog and the dialog's display props.
  const [activePair, setActivePair] = useState(null);

  const openMeetingsDialog = (row, pair) => {
    setActivePair({
      pairId: pair.pairId,
      roundName: row.roundName,
      subjectName: userDisplayName(row),
      subjectRole: row.participantRole,
      partnerName: userDisplayName(pair.partner),
      partnerRole:
        row.participantRole === MentorshipParticipantRoles.MENTEE
          ? MentorshipParticipantRoles.MENTOR
          : MentorshipParticipantRoles.MENTEE,
    });
  };

  const {
    meetings: activeMeetings,
    roundVersion: activeRoundVersion,
    loading: meetingLoading,
    error: meetingError,
    saveMeetingBatch,
  } = useMeetingLog(activePair?.pairId ?? null, activePair != null);

  const handleMeetingSave = async (batch) => {
    await saveMeetingBatch(batch);
    refetch();
  };

  // Reverse-lookup: find the accessor whose mapped backend field matches sortBy.
  const activeSortAccessor = sortBy
    ? (Object.keys(ACCESSOR_TO_SORT_FIELD).find(
        (acc) => ACCESSOR_TO_SORT_FIELD[acc] === sortBy,
      ) ?? null)
    : null;

  const handleSort = (accessor) => {
    const field = ACCESSOR_TO_SORT_FIELD[accessor];
    if (field) toggleSort(field);
  };

  const accountCell = (row) => (
    <StateChips
      isActive={!row.isDeactivated}
      isBlocked={row.isBlocked}
      hasPendingBlockRequest={false}
    />
  );

  const notRegisteredData = () =>
    rows.map((row) => ({
      name: <NameCell row={row} />,
      admittedAs: row.admittedRoles.join(", "),
      internal: row.isInternal ? "Internal" : "External",
      account: accountCell(row),
      roundsTakenPart: row.roundsTakenPart,
      lastRound: row.lastRoundName ?? "Never",
    }));

  const pageRows = loading ? [] : rows;
  const allOnPagePicked =
    pageRows.length > 0 && pageRows.every((row) => picked.has(row.userId));
  const someOnPagePicked = pageRows.some((row) => picked.has(row.userId));
  const selectColumn = {
    header: (
      <Checkbox
        aria-label="Select all on this page"
        checked={
          allOnPagePicked ? true : someOnPagePicked ? "indeterminate" : false
        }
        disabled={pageRows.length === 0}
        onCheckedChange={(checked) => setPicked(pageRows, checked === true)}
      />
    ),
    accessor: "select",
  };

  const data = loading
    ? []
    : notRegistered
      ? notRegisteredData()
      : rows.map((row) => ({
          select: (
            <Checkbox
              aria-label={`Select ${userDisplayName(row)}`}
              checked={picked.has(row.userId)}
              onCheckedChange={(checked) => setPicked([row], checked === true)}
            />
          ),
          name: <NameCell row={row} />,
          role: row.participantRole ?? "—",
          training: trainingLabel(
            row.participantRole === MentorshipParticipantRoles.MENTEE
              ? row.menteeOnboardingStatus
              : row.mentorOnboardingStatus,
          ),
          internal: row.isInternal ? "Internal" : "External",
          approval: row.approvalStatus ? (
            <Badge variant="secondary">{row.approvalStatus}</Badge>
          ) : (
            "—"
          ),
          account: accountCell(row),
          pair: (
            <PairCell
              row={row}
              onOpenMeetings={(pair) => openMeetingsDialog(row, pair)}
            />
          ),
        }));

  return (
    <Card className="mt-6 border-gray-200">
      <CardHeader className="flex items-center gap-3">
        <CardTitle>Participants</CardTitle>
        <CardAction className="ml-auto flex items-center gap-2">
          {rounds?.length === 0 ? (
            <span className="text-xs text-muted-foreground">
              No mentorship rounds yet.
            </span>
          ) : (
            <Select
              value={roundId}
              onValueChange={setRoundId}
              disabled={rounds == null}
            >
              <SelectTrigger aria-label="Round" className="h-8 w-56 text-xs">
                <SelectValue placeholder="Loading rounds" />
              </SelectTrigger>
              <SelectContent>
                {(rounds ?? []).map((round) => (
                  <SelectItem key={round.id} value={round.id.toString()}>
                    {round.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          {!matchingOn || rounds?.length === 0 ? null : (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-8 text-xs"
              disabled={!shownRun || shownRun.status === RUN_STATUS.NEVER_RUN}
              onClick={() => openMatching(roundId)}
            >
              {shownRun?.status === RUN_STATUS.RUNNING
                ? "Matching running…"
                : "View matching results"}
            </Button>
          )}
        </CardAction>
      </CardHeader>
      <CardContent>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <Input
            className="h-8 w-24 text-sm"
            inputMode="numeric"
            aria-label="User ID"
            placeholder="User ID"
            value={userId}
            onChange={(e) => setUserId(e.target.value.replace(/\D/g, ""))}
          />
          <Input
            className="h-8 w-56 text-sm"
            aria-label="Name / email"
            placeholder="Name / email"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <Select
            value={participantRole || ALL_ROLES}
            onValueChange={(v) => setParticipantRole(v === ALL_ROLES ? "" : v)}
          >
            <SelectTrigger aria-label="Role" className="h-8 w-32 text-xs">
              <SelectValue placeholder="All roles" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_ROLES}>All roles</SelectItem>
              <SelectItem value={MentorshipParticipantRoles.MENTOR}>
                Mentor
              </SelectItem>
              <SelectItem value={MentorshipParticipantRoles.MENTEE}>
                Mentee
              </SelectItem>
            </SelectContent>
          </Select>
          <Select
            value={internal || BOTH_INTERNAL_EXTERNAL}
            onValueChange={(v) =>
              setInternal(v === BOTH_INTERNAL_EXTERNAL ? "" : v)
            }
          >
            <SelectTrigger
              aria-label="Internal or external"
              className="h-8 w-40 text-xs"
            >
              <SelectValue placeholder="Internal & external" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={BOTH_INTERNAL_EXTERNAL}>
                Internal &amp; external
              </SelectItem>
              <SelectItem value="internal">Internal</SelectItem>
              <SelectItem value="external">External</SelectItem>
            </SelectContent>
          </Select>
          <Select
            value={accountStatus || ANY_ACCOUNT}
            onValueChange={(v) => setAccountStatus(v === ANY_ACCOUNT ? "" : v)}
          >
            <SelectTrigger aria-label="Account" className="h-8 w-36 text-xs">
              <SelectValue placeholder="Any account" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY_ACCOUNT}>Any account</SelectItem>
              <SelectItem value="active">Active</SelectItem>
              <SelectItem value="blocked">Blocked</SelectItem>
              <SelectItem value="deactivated">Deactivated</SelectItem>
            </SelectContent>
          </Select>
          <Select
            value={onboardingStatus || ALL_ONBOARDING_STATUSES}
            onValueChange={(v) =>
              setOnboardingStatus(v === ALL_ONBOARDING_STATUSES ? "" : v)
            }
            disabled={listNotRegistered}
          >
            <SelectTrigger
              aria-label="Onboarding status"
              className="h-8 w-40 text-xs"
            >
              <SelectValue placeholder="Any training" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_ONBOARDING_STATUSES}>
                Any training
              </SelectItem>
              <SelectItem value="completed">Training done</SelectItem>
              <SelectItem value="incomplete">Training not done</SelectItem>
            </SelectContent>
          </Select>
          <Select
            value={approvalStatus || ALL_APPROVAL_STATUSES}
            onValueChange={(v) =>
              setApprovalStatus(v === ALL_APPROVAL_STATUSES ? "" : v)
            }
            disabled={listNotRegistered}
          >
            <SelectTrigger
              aria-label="Approval status"
              className="h-8 w-36 text-xs"
            >
              <SelectValue placeholder="All approval" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_APPROVAL_STATUSES}>
                All approval
              </SelectItem>
              <SelectItem value={MentorshipApprovalStatus.SIGNED_UP}>
                Signed Up
              </SelectItem>
              <SelectItem value={MentorshipApprovalStatus.MATCHED}>
                Matched
              </SelectItem>
              <SelectItem value={MentorshipApprovalStatus.UN_MATCHED}>
                Un-Matched
              </SelectItem>
              <SelectItem value={MentorshipApprovalStatus.REJECTED}>
                Rejected
              </SelectItem>
            </SelectContent>
          </Select>
          <Select
            value={
              listNotRegistered
                ? NOT_REGISTERED
                : listEligible
                  ? ELIGIBLE
                  : REGISTERED
            }
            onValueChange={(v) => {
              setListNotRegistered(v === NOT_REGISTERED);
              setListEligible(v === ELIGIBLE);
            }}
          >
            <SelectTrigger aria-label="List" className="h-8 w-44 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={REGISTERED}>Registered</SelectItem>
              <SelectItem value={ELIGIBLE} disabled={!canListEligible}>
                Eligible for matching
              </SelectItem>
              <SelectItem
                value={NOT_REGISTERED}
                disabled={!canListNotRegistered}
              >
                Not registered
              </SelectItem>
            </SelectContent>
          </Select>
          <Button
            type="button"
            size="sm"
            onClick={submitSearch}
            disabled={!canSearch}
          >
            Search
          </Button>
        </div>

        {!hasSearched || !canSearch ? (
          <p className="text-sm text-muted-foreground">
            Set filters and click Search to see participants.
          </p>
        ) : (
          <>
            {showRunUi && (
              <div className="mb-3 flex justify-end">
                <Button
                  type="button"
                  size="sm"
                  disabled={!canRun}
                  onClick={() => setConfirmOpen(true)}
                >
                  Run matching · {picked.size}
                </Button>
              </div>
            )}
            <Table
              columns={
                notRegistered
                  ? NOT_REGISTERED_COLUMNS
                  : showRunUi
                    ? [selectColumn, ...COLUMNS]
                    : COLUMNS
              }
              data={data}
              onSort={handleSort}
              sortColumn={activeSortAccessor}
              sortDirection={order}
            />
            <div className="participant-search-pager mt-3 flex items-center justify-between gap-2 text-sm text-muted-foreground">
              <Button
                variant="outline"
                size="sm"
                onClick={prevPage}
                disabled={!hasPrev}
              >
                Prev
              </Button>
              <span>
                {total === 0 ? 0 : offset + 1}–{Math.min(offset + limit, total)}{" "}
                of {total}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={nextPage}
                disabled={!hasNext}
              >
                Next
              </Button>
            </div>
          </>
        )}

        <Dialog
          open={confirmOpen}
          onOpenChange={(open) => !starting && setConfirmOpen(open)}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Run matching for {committedRoundName}?</DialogTitle>
              <DialogDescription>
                {mentorCount} mentors and {menteeCount} mentees.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                disabled={starting}
                onClick={() => setConfirmOpen(false)}
              >
                Cancel
              </Button>
              <Button type="button" disabled={starting} onClick={runMatching}>
                Run
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        <MeetingLogDialog
          open={activePair != null}
          onOpenChange={(open) => !open && setActivePair(null)}
          roundName={activePair?.roundName ?? ""}
          subjectName={activePair?.subjectName ?? ""}
          subjectRole={
            activePair?.subjectRole ?? MentorshipParticipantRoles.MENTOR
          }
          partnerName={activePair?.partnerName ?? null}
          partnerRole={
            activePair?.partnerRole ?? MentorshipParticipantRoles.MENTEE
          }
          meetings={activeMeetings}
          loading={meetingLoading}
          error={meetingError}
          roundVersion={activeRoundVersion}
          onSave={handleMeetingSave}
        />
      </CardContent>
    </Card>
  );
};

export default ParticipantSearchCard;
