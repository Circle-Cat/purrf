import { Link } from "react-router-dom";
import { Loader2, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { formatInTz } from "@/utils/dateTime";
import { userDisplayName } from "@/utils/userName";
import {
  MEETING_TIMEZONE,
  attendanceIssueLines,
  firstContactOverdueLine,
} from "@/pages/MentorshipManagement/utils/attendanceIssues";
import { participantLink } from "@/pages/MentorshipManagement/utils/participantLink";
import AttendanceMark from "@/pages/MentorshipManagement/components/AttendanceMark";
import MeetingLogTable, {
  MeetingLogConfirm,
  MeetingLogEditButtons,
} from "@/pages/MentorshipManagement/components/MeetingLogTable";
import { useMeetingLog } from "@/pages/MentorshipManagement/hooks/useMeetingLog";
import { useMeetingLogEditor } from "@/pages/MentorshipManagement/hooks/useMeetingLogEditor";

/**
 * One pair on a person's detail page: who the partner is (linked to their
 * own page, opened on this pair), whether the pairing is live, meetings held
 * against the round's requirement, why they were matched (when the pair has
 * a reason), and its meeting log below when open.
 *
 * Only the meeting log lives here. Notes about the pair and status changes
 * are on the person's timeline.
 *
 * First contact is derived, not marked: the earliest meeting booked for the
 * pair, held or not. It is only worth showing while the round runs. A live
 * pair with no meeting held by the round's first-contact date gets the red
 * mark.
 *
 * The log is editable only by a writer, in a round in progress, on a v2 log;
 * the backend refuses edits to an ended round all the same.
 *
 * @param {{
 *   pair: Object,
 *   subject: {userId: number, name: string, role: "mentor"|"mentee"},
 *   round: {roundId: number, inProgress: boolean, requiredMeetings: number|null, firstMeetingDeadlineAt?: string|null},
 *   canWrite: boolean,
 *   open: boolean,
 *   onToggle: () => void,
 *   onMeetingsSaved: () => void,
 * }} props
 */
const PairSection = ({
  pair,
  subject,
  round,
  canWrite,
  open,
  onToggle,
  onMeetingsSaved,
}) => {
  const ended = pair.partner.isActive === false;
  const partnerName = userDisplayName(pair.partner);
  const reason = pair.partner.recommendationReason?.trim();
  const [mentorName, menteeName] =
    subject.role === "mentee"
      ? [partnerName, subject.name]
      : [subject.name, partnerName];
  const overdue = firstContactOverdueLine(
    {
      isActive: pair.partner.isActive,
      completedMeetingCount: pair.completedMeetingCount,
    },
    round,
  );
  const issues = ended
    ? []
    : [
        ...attendanceIssueLines(pair.attendanceIssues ?? [], {
          mentorName,
          menteeName,
        }),
        ...(overdue ? [overdue] : []),
      ];

  const { meetings, roundInProgress, loading, error, saveMeetingBatch } =
    useMeetingLog(pair.pairId, open);
  const editor = useMeetingLogEditor({
    meetings,
    onSave: async (batch) => {
      await saveMeetingBatch(batch);
      onMeetingsSaved();
    },
  });
  const canEdit = canWrite && roundInProgress && meetings.length > 0;

  return (
    <section
      id={`pair-${pair.pairId}`}
      className="mt-3 rounded-md border border-slate-200"
    >
      <header className="flex flex-wrap items-center gap-3 px-4 py-3 text-sm">
        <button
          type="button"
          aria-expanded={open}
          aria-label={`${open ? "Hide" : "Show"} meetings with ${partnerName}`}
          onClick={onToggle}
          className="text-slate-500"
        >
          {open ? "▾" : "▸"}
        </button>
        <span className={ended ? "text-slate-400" : "font-semibold"}>
          with{" "}
          <Link
            to={participantLink(pair.partner.id, round.roundId, pair.pairId)}
            className="underline hover:opacity-80"
          >
            {`${partnerName} · ID ${pair.partner.id}`}
          </Link>
        </span>
        <Badge variant={ended ? "outline" : "secondary"}>
          {ended ? "Ended" : "Active"}
        </Badge>
        <span className="text-xs text-slate-500">
          Meetings {pair.completedMeetingCount}/{round.requiredMeetings ?? "—"}
        </span>
        {issues.length > 0 && <AttendanceMark lines={issues} />}
        {round.inProgress && (
          <span className="text-xs text-slate-500">
            {pair.firstMeetingAt
              ? `First meeting ${formatInTz(pair.firstMeetingAt, MEETING_TIMEZONE, "yyyy-MM-dd")}`
              : "No meeting yet"}
          </span>
        )}
      </header>
      {reason && (
        <p
          className={`flex gap-1.5 px-4 pb-3 text-xs ${ended ? "text-slate-400" : "text-slate-600"}`}
        >
          <Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
          <span>
            <span className="font-medium">Why matched:</span> {reason}
          </span>
        </p>
      )}

      {open && (
        <div className="border-t border-slate-100 px-4 py-3">
          {loading ? (
            <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              Loading meeting log…
            </div>
          ) : error ? (
            <p className="py-4 text-sm font-medium text-destructive">
              Couldn&apos;t load meeting log.
            </p>
          ) : meetings.length === 0 ? (
            <p className="py-4 text-sm text-muted-foreground">
              No meetings recorded yet.
            </p>
          ) : (
            <MeetingLogTable
              meetings={meetings}
              mentorName={mentorName}
              menteeName={menteeName}
              editor={canEdit ? editor : undefined}
            />
          )}
          {canEdit && (
            <div className="mt-3 flex justify-end gap-2">
              <MeetingLogEditButtons editor={editor} />
            </div>
          )}
        </div>
      )}

      <Dialog
        open={editor.confirmAction != null}
        onOpenChange={(next) => !next && editor.setConfirmAction(null)}
      >
        <DialogContent className="sm:max-w-lg">
          {editor.confirmAction != null && (
            <MeetingLogConfirm
              editor={editor}
              mentorName={mentorName}
              menteeName={menteeName}
            />
          )}
        </DialogContent>
      </Dialog>
    </section>
  );
};

export default PairSection;
