import { useState } from "react";
import TimezoneSelector from "@/components/common/TimezoneSelector";
import { Calendar as CalendarIcon } from "lucide-react";
import { format } from "date-fns";
import {
  HALF_HOUR_SLOTS,
  hhMmToMinutes,
  isSameLocalDay,
  localToUtcIso,
  minutesIntoLocalDay,
  nowInTz,
  todayInTz,
} from "@/utils/dateTime";
import { Calendar } from "@/components/ui/calendar";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
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
import { cn } from "@/lib/utils";

import { postMyMentorshipMeetingLog } from "@/api/mentorshipApi";

/**
 * Form for logging a single mentorship meeting that has already been held.
 *
 * Allows the user to select a timezone (defaults to the user's profile
 * timezone), and fills in a date, start time, and end time. On submit, the
 * selected datetime is converted to UTC via
 * {@link https://github.com/date-fns/tz @date-fns/tz} and posted to the backend.
 *
 * Only future times are disabled in the time picker; past times remain
 * selectable. When the timezone is changed, the selected date resets to today
 * in the new timezone and both time fields are cleared.
 *
 * The form holds no reset logic of its own: it is rendered inside a tab panel
 * that unmounts when the tab or the surrounding dialog closes, so every visit
 * starts from a fresh mount.
 *
 * @param {object} props
 * @param {number | string} props.roundId - The mentorship round to log the meeting under.
 * @param {number} props.partnerId - The partner the meeting was held with. Required: a
 *   participant may hold more than one pair in a round, so the round alone does not
 *   identify which pair the meeting belongs to.
 * @param {string} props.userTimezone - IANA timezone string from the user's profile (e.g. "Asia/Shanghai").
 *   Must be non-null; the parent component is responsible for not mounting this form until the timezone is loaded.
 * @param {() => void} [props.onSuccess] - Called after the meeting is successfully logged.
 * @returns {JSX.Element}
 */
export default function MeetingLogForm({
  roundId,
  partnerId,
  userTimezone,
  onSuccess,
}) {
  // Initialize timezone with the user's profile timezone.
  const [timezone, setTimezone] = useState(userTimezone);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Default to today in the user's profile timezone.
  const [selectedDate, setSelectedDate] = useState(() =>
    todayInTz(userTimezone),
  );
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [slotError, setSlotError] = useState(null);

  const tzIana = typeof timezone === "string" ? timezone : timezone.value;

  const toUtcIso = (dateObj, timeStr, addDays = 0) =>
    localToUtcIso(dateObj, timeStr, tzIana, addDays);

  const startMinutes = hhMmToMinutes(startTime || "0:0");
  const endMinutes = hhMmToMinutes(endTime || "0:0");

  const validateTimesNotEqual = () => startMinutes !== endMinutes;

  // Current date/time in the selected timezone.
  const tzNow = nowInTz(tzIana);

  const isTodayInTz = isSameLocalDay(selectedDate, tzNow);

  const currentMinutesInTz = minutesIntoLocalDay(tzNow);

  const isFutureTime = (timeStr, bufferMinutes = 0) => {
    if (!isTodayInTz) return false;
    return hhMmToMinutes(timeStr) + bufferMinutes >= currentMinutesInTz;
  };

  const maxSelectableDate = new Date(
    tzNow.getFullYear(),
    tzNow.getMonth(),
    tzNow.getDate(),
    23,
    59,
    59,
  );

  const handleTimezoneChange = (newTz) => {
    setTimezone(newTz);
    const newIana = typeof newTz === "string" ? newTz : newTz.value;
    setSelectedDate(todayInTz(newIana));
    setStartTime("");
    setEndTime("");
  };

  const onSubmit = async () => {
    setSlotError(null);

    if (!startTime || !endTime) {
      setSlotError("Please select both start time and end time.");
      return;
    }

    if (!validateTimesNotEqual()) {
      setSlotError("Start time and end time cannot be the same.");
      return;
    }

    setIsSubmitting(true);
    const isOvernight = endMinutes < startMinutes;
    try {
      await postMyMentorshipMeetingLog({
        roundId: Number(roundId),
        partnerId: Number(partnerId),
        startDatetime: toUtcIso(selectedDate, startTime),
        endDatetime: toUtcIso(selectedDate, endTime, isOvernight ? 1 : 0),
        isCompleted: true,
      });
      onSuccess?.();
    } catch (error) {
      const errorMsg = error.response?.data?.message || error.message;
      if (errorMsg) {
        setSlotError(errorMsg);
      } else {
        console.error("Mentorship meeting submission failed", error);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Label>Meeting Instructions</Label>
        <div className="text-sm text-muted-foreground p-3 bg-muted rounded-md border">
          Please record your mentorship meetings here. Ensure the date, start
          time, and end time are correct.
        </div>
      </div>

      <div className="space-y-2" onWheel={(e) => e.stopPropagation()}>
        <Label>Timezone</Label>
        <TimezoneSelector
          value={timezone}
          onChange={handleTimezoneChange}
          currentDatetime={selectedDate}
          menuPortalTarget={
            typeof window !== "undefined" ? document.body : null
          }
          captureMenuScroll={true}
        />
      </div>

      <div className="space-y-4">
        <Label>Meeting Slot</Label>
        <div
          className={cn(
            "relative p-4 border rounded-lg bg-card text-card-foreground shadow-sm space-y-4",
            slotError ? "border-destructive" : "border-border",
          )}
        >
          <div className="grid gap-2">
            <Label>Date</Label>
            <Popover>
              <PopoverTrigger asChild>
                <Button
                  variant="outline"
                  className={cn(
                    "w-full justify-start text-left font-normal",
                    !selectedDate && "text-muted-foreground",
                  )}
                >
                  <CalendarIcon className="mr-2 h-4 w-4" />
                  {selectedDate ? (
                    format(selectedDate, "PPP")
                  ) : (
                    <span>Pick a date</span>
                  )}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0" side="top">
                <Calendar
                  mode="single"
                  selected={selectedDate}
                  onSelect={setSelectedDate}
                  disabled={{ after: maxSelectableDate }}
                  initialFocus
                />
              </PopoverContent>
            </Popover>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="grid gap-2">
              <Label className="text-xs">Start Time</Label>
              <Select value={startTime} onValueChange={setStartTime}>
                <SelectTrigger className="w-full bg-gray-50 border-none">
                  <SelectValue placeholder="Pick a start time" />
                </SelectTrigger>
                <SelectContent>
                  {HALF_HOUR_SLOTS.map((t) => (
                    <SelectItem
                      key={t}
                      value={t}
                      disabled={isFutureTime(t, 30)}
                    >
                      {t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-2">
              <Label className="text-xs">End Time</Label>
              <Select value={endTime} onValueChange={setEndTime}>
                <SelectTrigger className="w-full bg-gray-50 border-none">
                  <SelectValue placeholder="Pick an end time" />
                </SelectTrigger>
                <SelectContent>
                  {HALF_HOUR_SLOTS.map((t) => (
                    <SelectItem key={t} value={t} disabled={isFutureTime(t)}>
                      {t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {slotError && (
            <div className="text-sm font-medium text-destructive mt-2 animate-in fade-in">
              {slotError}
            </div>
          )}
        </div>
      </div>

      <div className="flex justify-end">
        <Button onClick={onSubmit} disabled={isSubmitting}>
          Log Meeting
        </Button>
      </div>
    </div>
  );
}
