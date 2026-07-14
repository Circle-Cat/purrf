import { Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { formatInTz } from "@/utils/dateTime";
import { getMeetingStatus } from "@/utils/meetingStatusCalculator";
import { MeetingStatus } from "@/constants/MeetingStatus";

const ROLE_LABELS = { mentor: "Mentor", mentee: "Mentee" };
const MEETING_TIMEZONE = "America/Los_Angeles";

/**
 * Formats a UTC meeting start/end datetime as a Pacific Time date + time range
 * string, e.g. "2026-04-06 · 15:30 – 16:30".
 */
function formatMeetingTimeRange(startDatetime, endDatetime) {
  const date = formatInTz(startDatetime, MEETING_TIMEZONE, "yyyy-MM-dd");
  const start = formatInTz(startDatetime, MEETING_TIMEZONE, "HH:mm");
  const end = formatInTz(endDatetime, MEETING_TIMEZONE, "HH:mm");
  return `${date} · ${start} – ${end}`;
}

/**
 * Maps a MeetingNoteTag to display text, substituting mentor/mentee names
 * for role-specific tags (absent/late).
 */
function noteTagLabel(tag, { mentorName, menteeName }) {
  switch (tag) {
    case "mentor_absent":
      return `${mentorName} absent`;
    case "mentee_absent":
      return `${menteeName} absent`;
    case "mentor_late":
      return `${mentorName} late arrival`;
    case "mentee_late":
      return `${menteeName} late arrival`;
    case "unknown_absent":
      return "Unknown absence";
    case "unknown_late":
      return "Unknown late arrival";
    case "insufficient_duration":
      return "Insufficient duration";
    default:
      return tag;
  }
}

/**
 * Renders a meeting's completion status. A not-yet-completed meeting whose
 * start time is still in the future is unambiguously "Scheduled" rather than
 * "Incomplete".
 *
 * @param {{isCompleted: boolean, startDatetime: string}} props
 */
function MeetingStatusCell({ isCompleted, startDatetime }) {
  switch (getMeetingStatus(isCompleted, startDatetime)) {
    case MeetingStatus.COMPLETED:
      return (
        <Badge
          variant="outline"
          className="border-green-200 bg-green-50 text-green-700"
        >
          Completed
        </Badge>
      );
    case MeetingStatus.PAST_INCOMPLETE:
      return (
        <Badge
          variant="outline"
          className="border-gray-300 bg-gray-100 text-gray-700"
        >
          Incomplete
        </Badge>
      );
    case MeetingStatus.SCHEDULED:
      return (
        <Badge
          variant="outline"
          className="border-amber-200 bg-amber-50 text-amber-700"
        >
          Scheduled
        </Badge>
      );
    default:
      return null;
  }
}

/**
 * Renders a meeting's note tags as semicolon-separated plain text. When a
 * past, not-completed meeting has no note tags, shows a plain-text placeholder
 * instead of leaving the cell blank.
 *
 * @param {{note: string[], mentorName: string, menteeName: string, isCompleted: boolean, startDatetime: string}} props
 */
function MeetingNoteCell({
  note,
  mentorName,
  menteeName,
  isCompleted,
  startDatetime,
}) {
  if (note.length === 0) {
    if (
      getMeetingStatus(isCompleted, startDatetime) ===
      MeetingStatus.PAST_INCOMPLETE
    ) {
      return <span className="text-sm italic">No attendance data</span>;
    }
    return null;
  }
  return (
    <span className="text-sm">
      {note
        .map((tag) => noteTagLabel(tag, { mentorName, menteeName }))
        .join("; ")}
    </span>
  );
}

/**
 * Read-only dialog showing a pair's full meeting log for a round.
 *
 * The header renders immediately from the row data already available to
 * the caller; it never waits for the fetch. Only the body switches between
 * loading, error, empty, and table states based on `loading`, `error`, and
 * `meetings`.
 *
 * @param {{
 *   open: boolean,
 *   onOpenChange: (open: boolean) => void,
 *   roundName: string,
 *   subjectName: string,
 *   subjectRole: "mentor" | "mentee",
 *   partnerName: string,
 *   partnerRole: "mentor" | "mentee",
 *   meetings: Array<{meetingId: string, startDatetime: string, endDatetime: string, isCompleted: boolean, note: string[], createDatetime: string}>,
 *   loading: boolean,
 *   error: boolean,
 * }} props
 */
const MeetingLogDialog = ({
  open,
  onOpenChange,
  roundName,
  subjectName,
  subjectRole,
  partnerName,
  partnerRole,
  meetings,
  loading,
  error,
}) => {
  const mentorName = subjectRole === "mentor" ? subjectName : partnerName;
  const menteeName = subjectRole === "mentee" ? subjectName : partnerName;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-5xl z-[200]"
        onPointerDownOutside={(e) => e.preventDefault()}
      >
        <DialogHeader>
          <DialogTitle>
            Meeting Log — {subjectName} ({ROLE_LABELS[subjectRole]}) with{" "}
            {partnerName} ({ROLE_LABELS[partnerRole]}) · {roundName}
          </DialogTitle>
          <DialogDescription className="sr-only">
            Each meeting's datetime, status, and notes for this pair.
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            Loading meeting log…
          </div>
        ) : error ? (
          <p className="py-8 text-center text-sm font-medium text-destructive">
            Couldn't load meeting log. Close and reopen to try again.
          </p>
        ) : meetings.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No meetings recorded yet.
          </p>
        ) : (
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full text-sm border-collapse table-fixed">
              <thead>
                <tr className="bg-accent text-left text-xs font-semibold text-accent-foreground uppercase tracking-wide">
                  <th className="px-3 py-2 border-b border-border w-24">
                    Meeting
                  </th>
                  <th className="px-3 py-2 border-b border-l border-border w-52">
                    Datetime
                  </th>
                  <th className="px-3 py-2 border-b border-l border-border w-28">
                    Status
                  </th>
                  <th className="px-3 py-2 border-b border-l border-border">
                    Note
                  </th>
                </tr>
              </thead>
              <tbody>
                {meetings.map((meeting, index) => (
                  <tr
                    key={meeting.meetingId}
                    className="border-b border-border last:border-b-0"
                  >
                    <td className="px-3 py-3 align-top">{index + 1}</td>
                    <td className="px-3 py-3 border-l border-border align-top">
                      {formatMeetingTimeRange(
                        meeting.startDatetime,
                        meeting.endDatetime,
                      )}
                    </td>
                    <td className="px-3 py-3 border-l border-border align-top">
                      <MeetingStatusCell
                        isCompleted={meeting.isCompleted}
                        startDatetime={meeting.startDatetime}
                      />
                    </td>
                    <td className="px-3 py-3 border-l border-border align-top">
                      <MeetingNoteCell
                        note={meeting.note}
                        mentorName={mentorName}
                        menteeName={menteeName}
                        isCompleted={meeting.isCompleted}
                        startDatetime={meeting.startDatetime}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default MeetingLogDialog;
