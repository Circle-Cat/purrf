import { useEffect, useState } from "react";
import { ChevronDown } from "lucide-react";
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
import TimezoneSelector from "@/components/common/TimezoneSelector";
import { formatInTz } from "@/utils/dateTime";
import {
  DEFAULT_DURATION_MINUTES,
  DURATION_OPTIONS,
  durationFromRange,
} from "@/utils/meetingSlot";

/**
 * Move an already-booked mentorship meeting to a new slot, in the viewer's
 * own wall-clock terms (date + HH:mm + IANA zone). `onSubmit` receives those
 * values as-is -- the backend owns converting them to UTC, so this component
 * performs no UTC conversion itself.
 *
 * @param {{open: boolean, onOpenChange: (open: boolean) => void,
 *          meeting: {meetingId: string, startDatetime: string|null,
 *            endDatetime: string|null}|null, userTimezone: string,
 *          onSubmit: (body: {date: string, startTime: string,
 *            durationMinutes: number, timezone: string}) => void,
 *          submitting?: boolean}} props
 */
export default function MeetingRescheduleDialog({
  open,
  onOpenChange,
  meeting,
  userTimezone,
  onSubmit,
  submitting = false,
}) {
  const [date, setDate] = useState("");
  const [startTime, setStartTime] = useState("");
  const [durationMinutes, setDurationMinutes] = useState(
    DEFAULT_DURATION_MINUTES,
  );
  const [timezone, setTimezone] = useState(userTimezone);

  // Radix unmounts DialogContent while the dialog is closed, but this
  // component stays mounted the whole time, so its state would otherwise
  // carry over from whichever meeting was open last. Re-derive every field
  // from the meeting each time the dialog opens.
  useEffect(() => {
    if (!open) return;
    if (meeting?.startDatetime) {
      setDate(
        formatInTz(meeting.startDatetime, userTimezone, "yyyy-MM-dd") ?? "",
      );
      setStartTime(
        formatInTz(meeting.startDatetime, userTimezone, "HH:mm") ?? "",
      );
      setDurationMinutes(
        durationFromRange(meeting.startDatetime, meeting.endDatetime),
      );
    } else {
      setDate("");
      setStartTime("");
      setDurationMinutes(DEFAULT_DURATION_MINUTES);
    }
    setTimezone(userTimezone);
  }, [open, meeting?.startDatetime, meeting?.endDatetime, userTimezone]);

  const handleTimezoneChange = (option) => {
    setTimezone(
      typeof option === "string" ? option : (option?.value ?? userTimezone),
    );
  };

  const canSubmit = date !== "" && startTime !== "";

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!canSubmit || submitting) return;
    onSubmit({ date, startTime, durationMinutes, timezone });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Reschedule meeting</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="reschedule-date">Date</Label>
              <Input
                id="reschedule-date"
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="reschedule-start-time">Start time</Label>
              <Input
                id="reschedule-start-time"
                type="time"
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="reschedule-duration">Duration</Label>
              <div className="relative">
                <select
                  id="reschedule-duration"
                  name="duration"
                  aria-label="Duration"
                  value={String(durationMinutes)}
                  onChange={(e) => setDurationMinutes(Number(e.target.value))}
                  className="w-full appearance-none rounded-lg border border-gray-300 bg-white px-4 py-2.5 text-gray-900 focus:border-[#6035F3] focus:ring-2 focus:ring-[#6035F3]/20 outline-none transition-all"
                >
                  {DURATION_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
                <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-3 text-gray-400">
                  <ChevronDown className="w-4 h-4" />
                </div>
              </div>
            </div>
            <div className="min-w-0 space-y-1.5">
              <Label>Timezone</Label>
              <TimezoneSelector
                value={timezone}
                onChange={handleTimezoneChange}
              />
            </div>
          </div>

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
              Save
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
