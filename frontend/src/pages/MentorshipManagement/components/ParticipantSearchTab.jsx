import { useState } from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import Table from "@/components/common/Table";
import { useParticipantSearch } from "@/pages/MentorshipManagement/hooks/useParticipantSearch";
import { MentorshipParticipantRoles } from "@/constants/MentorshipParticipantRoles";
import { MentorshipApprovalStatus } from "@/constants/MentorshipApprovalStatus";
import { partnerDisplayName } from "@/utils/partnerName";
import MeetingLogDialog from "@/pages/MentorshipManagement/components/MeetingLogDialog";
import { useMeetingLog } from "@/pages/MentorshipManagement/hooks/useMeetingLog";

const ALL_ROUNDS = "__all__";
const ALL_ROLES = "__all__";
const ALL_APPROVAL_STATUSES = "__all__";
const ALL_ONBOARDING_STATUSES = "__all__";

/**
 * Maps table column accessors to backend sort_by field names. Only columns
 * backed by a whitelisted sort field belong here — every other column is
 * unsortable.
 * @type {Record<string, string>}
 */
const ACCESSOR_TO_SORT_FIELD = {
  userId: "user_id",
};

const BASE_COLUMNS = [
  { header: "User ID", accessor: "userId", sortable: true },
  { header: "First Name", accessor: "firstName" },
  { header: "Last Name", accessor: "lastName" },
  { header: "Preferred Name", accessor: "preferredName" },
  { header: "Primary Email", accessor: "primaryEmail" },
  { header: "Alternative Email(s)", accessor: "alternativeEmails" },
];

const PARTICIPANT_EXTRA_COLUMNS = [
  { header: "Round", accessor: "round" },
  { header: "Role", accessor: "role" },
  { header: "Approval Status", accessor: "approvalStatus" },
  { header: "Onboarding Status", accessor: "onboardingStatus" },
  { header: "Matched User", accessor: "matchedUser" },
  { header: "Meetings", accessor: "meetings" },
];

const NON_PARTICIPANT_EXTRA_COLUMNS = [
  { header: "Mentor Onboarding", accessor: "mentorOnboardingStatus" },
  { header: "Mentee Onboarding", accessor: "menteeOnboardingStatus" },
];

/**
 * Renders the first alternative email inline; any remaining ones collapse
 * behind a "+N more" trigger so the column doesn't grow with the list length.
 * All emails (inline or in the popover) are plain selectable text, so they
 * can be copied by dragging like any other cell.
 *
 * @param {{ emails: string[] }} props
 */
const AlternativeEmailsCell = ({ emails }) => {
  if (!emails?.length) return "—";

  const [first, ...rest] = emails;
  if (rest.length === 0) return first;

  return (
    <span className="flex items-center gap-1.5">
      {first}
      <Popover>
        <PopoverTrigger asChild>
          <button
            type="button"
            className="text-muted-foreground underline decoration-dotted underline-offset-2 hover:text-foreground"
          >
            +{rest.length} more
          </button>
        </PopoverTrigger>
        <PopoverContent className="w-auto">
          <div className="flex flex-col gap-1 text-sm">
            {rest.map((email) => (
              <div key={email}>{email}</div>
            ))}
          </div>
        </PopoverContent>
      </Popover>
    </span>
  );
};

/**
 * Resolves the display name for the row's subject.
 * Separate from `partnerDisplayName`, which only applies to the partner.
 */
function subjectDisplayName(row) {
  return (
    row.preferredName?.trim() ||
    `${row.firstName ?? ""} ${row.lastName ?? ""}`.trim()
  );
}

/**
 * Self-contained trigger and dialog for a matched participant's meeting log.
 * Owns its open state and only fetches meeting data once the dialog is opened.
 *
 * @param {{
 *   pairId: number|null,
 *   completedMeetingCount: number|null,
 *   requiredMeetings: number|null,
 *   roundName: string,
 *   subjectName: string,
 *   subjectRole: string,
 *   partnerName: string|null,
 *   partnerRole: string,
 * }} props
 */
function MeetingsCell({
  pairId,
  completedMeetingCount,
  requiredMeetings,
  roundName,
  subjectName,
  subjectRole,
  partnerName,
  partnerRole,
}) {
  const [open, setOpen] = useState(false);
  const { meetings, loading, error } = useMeetingLog(pairId, open);

  if (
    pairId == null ||
    completedMeetingCount == null ||
    requiredMeetings == null
  ) {
    return "—";
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="text-primary underline hover:opacity-80"
      >
        {completedMeetingCount}/{requiredMeetings}
      </button>
      <MeetingLogDialog
        open={open}
        onOpenChange={setOpen}
        roundName={roundName}
        subjectName={subjectName}
        subjectRole={subjectRole}
        partnerName={partnerName}
        partnerRole={partnerRole}
        meetings={meetings}
        loading={loading}
        error={error}
      />
    </>
  );
}

/**
 * Shared tab for participant and non-participant searches, switched by
 * `participationStatus`.
 *
 * Participants additionally get round-specific filters and columns (round,
 * role, approval status, matched user, meetings), plus a single onboarding
 * column resolved from their role in that round.
 *
 * Non-participants only get the shared user ID/name/email/onboarding status
 * filters, and display separate mentor and mentee onboarding columns because
 * they have no round role from which to resolve a single onboarding status.
 *
 * The round filter is a dropdown of `rounds`, so admins pick a round by name
 * instead of typing its numeric ID.
 *
 * @param {{
 *   participationStatus: "participant" | "non_participant",
 *   rounds?: Array<{id: number, name: string}>,
 * }} props
 */
const ParticipantSearchTab = ({ participationStatus, rounds }) => {
  const isParticipant = participationStatus === "participant";

  const {
    rows,
    total,
    loading,
    hasSearched,
    userId,
    setUserId,
    name,
    setName,
    email,
    setEmail,
    matchedUser,
    setMatchedUser,
    roundId,
    setRoundId,
    participantRole,
    setParticipantRole,
    approvalStatus,
    setApprovalStatus,
    onboardingStatus,
    setOnboardingStatus,
    submitSearch,
    offset,
    limit,
    nextPage,
    prevPage,
    sortBy,
    order,
    toggleSort,
  } = useParticipantSearch(participationStatus);

  const hasPrev = offset > 0;
  const hasNext = offset + limit < total;

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

  const columns = isParticipant
    ? [...BASE_COLUMNS, ...PARTICIPANT_EXTRA_COLUMNS]
    : [...BASE_COLUMNS, ...NON_PARTICIPANT_EXTRA_COLUMNS];

  const data = loading
    ? []
    : rows.map((row) => ({
        userId: row.userId,
        firstName: row.firstName ?? "—",
        lastName: row.lastName ?? "—",
        preferredName: row.preferredName ?? "—",
        primaryEmail: row.primaryEmail ?? "—",
        alternativeEmails: (
          <AlternativeEmailsCell emails={row.alternativeEmails} />
        ),
        ...(isParticipant && {
          round: row.roundName ?? "—",
          role: row.participantRole ?? "—",
          approvalStatus: row.approvalStatus ?? "—",
          onboardingStatus:
            (row.participantRole === MentorshipParticipantRoles.MENTEE
              ? row.menteeOnboardingStatus
              : row.mentorOnboardingStatus) ?? "—",
          matchedUser: row.matchedUser
            ? partnerDisplayName(row.matchedUser)
            : "—",
          meetings: (
            <MeetingsCell
              pairId={row.pairId}
              completedMeetingCount={row.completedMeetingCount}
              requiredMeetings={row.requiredMeetings}
              roundName={row.roundName}
              subjectName={subjectDisplayName(row)}
              subjectRole={row.participantRole}
              partnerName={
                row.matchedUser ? partnerDisplayName(row.matchedUser) : null
              }
              partnerRole={
                row.participantRole === MentorshipParticipantRoles.MENTEE
                  ? MentorshipParticipantRoles.MENTOR
                  : MentorshipParticipantRoles.MENTEE
              }
            />
          ),
        }),
        ...(!isParticipant && {
          mentorOnboardingStatus: row.mentorOnboardingStatus ?? "—",
          menteeOnboardingStatus: row.menteeOnboardingStatus ?? "—",
        }),
      }));

  return (
    <div className="participant-search-tab flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <Input
          className="w-20"
          inputMode="numeric"
          placeholder="User ID"
          value={userId}
          onChange={(e) => setUserId(e.target.value.replace(/\D/g, ""))}
          onKeyDown={(e) => e.key === "Enter" && submitSearch()}
        />
        <Input
          className="w-40"
          placeholder="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submitSearch()}
        />
        <Input
          className="w-48"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submitSearch()}
        />
        {isParticipant && (
          <>
            <Input
              className="w-40"
              placeholder="Matched User Name"
              value={matchedUser}
              onChange={(e) => setMatchedUser(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submitSearch()}
            />
            <Select
              value={roundId || ALL_ROUNDS}
              onValueChange={(v) => setRoundId(v === ALL_ROUNDS ? "" : v)}
            >
              <SelectTrigger aria-label="Round" className="w-52">
                <SelectValue placeholder="All Rounds" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL_ROUNDS}>All Rounds</SelectItem>
                {rounds.map((round) => (
                  <SelectItem key={round.id} value={round.id.toString()}>
                    {round.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select
              value={participantRole || ALL_ROLES}
              onValueChange={(v) =>
                setParticipantRole(v === ALL_ROLES ? "" : v)
              }
            >
              <SelectTrigger aria-label="Role" className="w-24">
                <SelectValue placeholder="All Roles" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL_ROLES}>All Roles</SelectItem>
                <SelectItem value={MentorshipParticipantRoles.MENTOR}>
                  Mentor
                </SelectItem>
                <SelectItem value={MentorshipParticipantRoles.MENTEE}>
                  Mentee
                </SelectItem>
              </SelectContent>
            </Select>

            <Select
              value={approvalStatus || ALL_APPROVAL_STATUSES}
              onValueChange={(v) =>
                setApprovalStatus(v === ALL_APPROVAL_STATUSES ? "" : v)
              }
            >
              <SelectTrigger aria-label="Approval status" className="w-32">
                <SelectValue placeholder="All Approval" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL_APPROVAL_STATUSES}>
                  All Approval
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
          </>
        )}

        <Select
          value={onboardingStatus || ALL_ONBOARDING_STATUSES}
          onValueChange={(v) =>
            setOnboardingStatus(v === ALL_ONBOARDING_STATUSES ? "" : v)
          }
        >
          <SelectTrigger aria-label="Onboarding status" className="w-36">
            <SelectValue placeholder="All Onboarding" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_ONBOARDING_STATUSES}>
              All Onboarding
            </SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
            <SelectItem value="incomplete">Incomplete</SelectItem>
          </SelectContent>
        </Select>

        <Button type="button" onClick={submitSearch}>
          Search
        </Button>
      </div>

      {!hasSearched ? (
        <p className="text-sm text-muted-foreground">
          Enter search criteria and click Search.
        </p>
      ) : (
        <>
          <Table
            columns={columns}
            data={data}
            onSort={handleSort}
            sortColumn={activeSortAccessor}
            sortDirection={order}
          />
          <div className="participant-search-pager flex items-center justify-between gap-2 text-sm text-muted-foreground">
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
    </div>
  );
};

export default ParticipantSearchTab;
