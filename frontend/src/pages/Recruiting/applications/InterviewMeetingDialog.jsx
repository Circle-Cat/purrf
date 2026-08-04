import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import TimezoneSelector from "@/components/common/TimezoneSelector";
import PeoplePicker from "@/pages/Recruiting/components/PeoplePicker";
import { formatInTz } from "@/utils/dateTime";

/**
 * Default zone/duration for a fresh "schedule" booking with nothing else to
 * derive a default from -- deliberately a fixed constant rather than the
 * browser's local zone, so the initial state is deterministic regardless of
 * the machine running the app (or the test).
 */
const DEFAULT_DURATION_MINUTES = 45;

const DURATION_OPTIONS = [
  { value: "30", label: "30 minutes" },
  { value: "45", label: "45 minutes" },
  { value: "60", label: "1 hour" },
  { value: "90", label: "1.5 hours" },
];

/**
 * Book or edit an application's current stage+round interview meeting, in
 * the recruiter's own wall-clock terms (date + HH:mm + IANA zone) -- the
 * backend converts and stores the zone itself (see
 * InterviewScheduleRequestDto), so nothing here converts to UTC before
 * calling `onSubmit`.
 *
 * In "schedule" mode the interviewer field starts from `defaultAssigneeId`
 * (the caller already resolved this to the round's current assignee, or the
 * stage's configured default when the round is unassigned -- this component
 * doesn't distinguish the two, it just prefills from whichever one value it
 * gets). In "edit" mode every field prefills from the existing `interview`
 * instead, and a notice warns that attendees will be notified, listing every
 * invitee: the candidate (`candidateName`, passed in separately -- the
 * candidate isn't part of `InterviewDto`), the interviewer, and the
 * organizer.
 *
 * @param {{open: boolean, onOpenChange: (open: boolean) => void,
 *          mode: "schedule"|"edit", interview: object|null,
 *          defaultAssigneeId: number|null,
 *          interviewPool: {userId: number, name: string, email: string}[],
 *          candidateName?: string|null, viewerTimezone: string,
 *          onSubmit: (body: {assigneeId: number, date: string,
 *            startTime: string, durationMinutes: number,
 *            timezone: string}) => void,
 *          submitting?: boolean}} props
 */
const InterviewMeetingDialog = ({
  open,
  onOpenChange,
  mode,
  interview,
  defaultAssigneeId,
  interviewPool,
  candidateName,
  viewerTimezone,
  onSubmit,
  submitting = false,
}) => {
  const [assigneeId, setAssigneeId] = useState(undefined);
  const [date, setDate] = useState("");
  const [startTime, setStartTime] = useState("");
  const [durationMinutes, setDurationMinutes] = useState(
    DEFAULT_DURATION_MINUTES,
  );
  const [timezone, setTimezone] = useState(viewerTimezone);

  // Re-derive every field whenever the dialog opens (Radix unmounts
  // DialogContent while closed, but this component itself stays mounted, so
  // its state would otherwise leak from one open to the next).
  useEffect(() => {
    if (!open) return;
    if (mode === "edit" && interview) {
      setAssigneeId(interview.assigneeId ?? undefined);
      // Converted into the VIEWER's zone, not the booker's: nothing stores
      // the zone it was booked in, and an editor should see the slot in the
      // same terms the card just showed them.
      setDate(
        formatInTz(interview.startAt, viewerTimezone, "yyyy-MM-dd") ?? "",
      );
      setStartTime(
        formatInTz(interview.startAt, viewerTimezone, "HH:mm") ?? "",
      );
      setDurationMinutes(
        Math.round(
          (new Date(interview.endAt).getTime() -
            new Date(interview.startAt).getTime()) /
            60000,
        ),
      );
      setTimezone(viewerTimezone);
    } else {
      setAssigneeId(defaultAssigneeId ?? undefined);
      setDate("");
      setStartTime("");
      setDurationMinutes(DEFAULT_DURATION_MINUTES);
      setTimezone(viewerTimezone);
    }
  }, [open, mode, interview, defaultAssigneeId, viewerTimezone]);

  const handleTimezoneChange = (option) => {
    setTimezone(
      typeof option === "string" ? option : (option?.value ?? viewerTimezone),
    );
  };

  const canSubmit = assigneeId != null && date !== "" && startTime !== "";

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!canSubmit || submitting) return;
    onSubmit({
      assigneeId: Number(assigneeId),
      date,
      startTime,
      durationMinutes: Number(durationMinutes),
      timezone,
    });
  };

  const isEdit = mode === "edit" && interview != null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {isEdit ? "Edit interview meeting" : "Schedule interview meeting"}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* PeoplePicker's default "select" variant always renders its
              "— none —" placeholder regardless of `allowNone` (that prop
              only takes effect on the "list"/radio variant) -- omitted here
              rather than passed misleadingly. Submission is still hard-
              gated on a real pick via `canSubmit` below. */}
          <PeoplePicker
            label="Interviewer"
            pool={interviewPool}
            value={assigneeId}
            onChange={(v) => setAssigneeId(v)}
          />
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="interview-date">Date</Label>
              <Input
                id="interview-date"
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="interview-start-time">Start time</Label>
              <Input
                id="interview-start-time"
                type="time"
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="interview-duration">Duration</Label>
              <Select
                value={String(durationMinutes)}
                onValueChange={(v) => setDurationMinutes(Number(v))}
              >
                <SelectTrigger
                  id="interview-duration"
                  aria-label="Duration"
                  className="w-full"
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DURATION_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="min-w-0 space-y-1.5">
              <Label>Timezone</Label>
              <TimezoneSelector
                value={timezone}
                onChange={handleTimezoneChange}
              />
            </div>
          </div>

          {isEdit && (
            <div className="space-y-1 rounded border bg-slate-50 p-3 text-sm text-slate-600">
              <p>Attendees will be notified of this change.</p>
              <p>Candidate: {candidateName ?? "Unknown"}</p>
              <p>Interviewer: {interview.assigneeName}</p>
              <p>Organizer: {interview.scheduledByName}</p>
            </div>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              disabled={submitting}
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={!canSubmit || submitting}>
              {isEdit ? "Save changes" : "Schedule"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};

export default InterviewMeetingDialog;
