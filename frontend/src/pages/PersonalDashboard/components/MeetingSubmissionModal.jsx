import { useState } from "react";
import TimezoneSelect from "react-timezone-select";
import { Calendar as CalendarIcon, Check } from "lucide-react";
import { format } from "date-fns";
import { TZDate } from "@date-fns/tz";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
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
import meetingTimezones from "@/constants/MeetingTimezones";

// Generate time options in 30-minute increments (e.g., "00:00", "00:30", ..., "23:30")
const timeOptions = Array.from({ length: 48 }, (_, i) => {
  const hour = Math.floor(i / 2)
    .toString()
    .padStart(2, "0");
  const minute = i % 2 === 0 ? "00" : "30";
  return `${hour}:${minute}`;
});

const tzSelectStyles = {
  menuPortal: (base) => ({ ...base, zIndex: 202, pointerEvents: "auto" }),
  menu: (base) => ({
    ...base,
    zIndex: 202,
    backgroundColor: "var(--popover)",
    borderRadius: "var(--radius)",
    border: "1px solid var(--border)",
    padding: "0.25rem",
    overflow: "hidden",
  }),
  menuList: (base) => ({ ...base, padding: 0 }),
  control: (base) => ({
    ...base,
    border: "none",
    backgroundColor: "var(--color-gray-50)",
    borderRadius: "0.5rem",
    boxShadow: "none",
    cursor: "pointer",
  }),
  indicatorSeparator: () => ({ display: "none" }),
  dropdownIndicator: (base) => ({
    ...base,
    padding: "0 8px",
    color: "var(--muted-foreground)",
  }),
  option: (base, state) => ({
    ...base,
    fontSize: "0.875rem",
    backgroundColor: state.isFocused ? "var(--accent)" : "transparent",
    color: state.isFocused ? "var(--accent-foreground)" : "inherit",
    borderRadius: "calc(var(--radius) - 2px)",
    padding: "0.25rem 0.375rem",
    cursor: "default",
  }),
};

const formatTimezoneLabel = (option, { context, selectValue } = {}) => {
  if (typeof option === "string") return option;
  if (context === "value") return option.label;
  const isSelected = selectValue?.some((v) => v.value === option.value);
  return (
    <div className="flex w-full items-center justify-between gap-2">
      <span>{option.label}</span>
      <span className="flex size-4 shrink-0 items-center justify-center">
        {isSelected && <Check className="size-4 pointer-events-none" />}
      </span>
    </div>
  );
};
/**
 * Modal for submitting a single mentorship meeting log entry.
 *
 * Allows the user to select a timezone (defaults to the user's profile timezone),
 * and fills in a date, start time, and end time. On submit, the selected
 * datetime is converted to UTC via {@link https://github.com/date-fns/tz @date-fns/tz}
 * and posted to the backend.
 *
 * Only future times are disabled in the time picker; past times remain selectable.
 * When the timezone is changed, the selected date resets to today in the new timezone
 * and both time fields are cleared.
 *
 * @param {object} props
 * @param {boolean} props.open - Whether the modal is visible.
 * @param {(open: boolean) => void} props.onOpenChange - Called when the modal open state should change.
 * @param {number | string} props.roundId - The mentorship round to log the meeting under.
 * @param {string} props.userTimezone - IANA timezone string from the user's profile (e.g. "Asia/Shanghai").
 *   Must be non-null; the parent component is responsible for not mounting this modal until the timezone is loaded.
 * @param {() => void} [props.onSuccess] - Called after the meeting is successfully submitted.
 * @returns {JSX.Element}
 */
export default function MeetingSubmissionModal({
  open,
  onOpenChange,
  roundId,
  userTimezone,
  onSuccess,
}) {
  // Initialize timezone with the user's profile timezone.
  const [timezone, setTimezone] = useState(userTimezone);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Default to today in the user's profile timezone.
  const [selectedDate, setSelectedDate] = useState(() => {
    const now = new TZDate(new Date(), userTimezone);
    return new Date(now.getFullYear(), now.getMonth(), now.getDate());
  });
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [slotError, setSlotError] = useState(null);

  const tzIana = typeof timezone === "string" ? timezone : timezone.value;

  const toUtcIso = (dateObj, timeStr, addDays = 0) => {
    const [h, m] = timeStr.split(":").map(Number);
    const d = new TZDate(
      dateObj.getFullYear(),
      dateObj.getMonth(),
      dateObj.getDate() + addDays,
      h,
      m,
      0,
      tzIana,
    );
    return new Date(+d).toISOString().split(".")[0] + "Z";
  };

  const [startH, startM] = (startTime || "0:0").split(":").map(Number);
  const [endH, endM] = (endTime || "0:0").split(":").map(Number);

  const validateTimesNotEqual = () => startH !== endH || startM !== endM;

  // Current date/time in the selected timezone.
  const nowInTz = new TZDate(new Date(), tzIana);

  const isTodayInTz =
    format(selectedDate, "yyyy-MM-dd") === format(nowInTz, "yyyy-MM-dd");

  const currentMinutesInTz = nowInTz.getHours() * 60 + nowInTz.getMinutes();

  const isFutureTime = (timeStr, bufferMinutes = 0) => {
    if (!isTodayInTz) return false;
    const [h, m] = timeStr.split(":").map(Number);
    return h * 60 + m + bufferMinutes >= currentMinutesInTz;
  };

  const maxSelectableDate = new Date(
    nowInTz.getFullYear(),
    nowInTz.getMonth(),
    nowInTz.getDate(),
    23,
    59,
    59,
  );

  const handleTimezoneChange = (newTz) => {
    setTimezone(newTz);
    const newIana = typeof newTz === "string" ? newTz : newTz.value;
    const now = new TZDate(new Date(), newIana);
    setSelectedDate(new Date(now.getFullYear(), now.getMonth(), now.getDate()));
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
    const isOvernight = endH < startH || (endH === startH && endM < startM);
    try {
      await postMyMentorshipMeetingLog({
        roundId: Number(roundId),
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
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] max-h-[90vh] flex flex-col z-[200]">
        <DialogHeader>
          <DialogTitle>Submit Meeting Info</DialogTitle>
          <DialogDescription>
            Please fill in the meeting information.
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto pr-2 py-4 space-y-6">
          <div className="space-y-2">
            <Label>Meeting Instructions</Label>
            <div className="text-sm text-muted-foreground p-3 bg-muted rounded-md border">
              Please record your mentorship meetings here. Ensure the date,
              start time, and end time are correct.
            </div>
          </div>

          <div className="space-y-2" onWheel={(e) => e.stopPropagation()}>
            <Label>Timezone</Label>
            <TimezoneSelect
              value={timezone}
              onChange={handleTimezoneChange}
              timezones={meetingTimezones}
              currentDatetime={selectedDate}
              menuPortalTarget={
                typeof window !== "undefined" ? document.body : null
              }
              captureMenuScroll={true}
              formatOptionLabel={formatTimezoneLabel}
              styles={tzSelectStyles}
              theme={(theme) => ({
                ...theme,
                colors: { ...theme.colors, primary50: "var(--accent)" },
              })}
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
                  <PopoverContent className="w-auto p-0 z-[201]" side="top">
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
                    <SelectContent className="z-[201]">
                      {timeOptions.map((t) => (
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
                    <SelectContent className="z-[201]">
                      {timeOptions.map((t) => (
                        <SelectItem
                          key={t}
                          value={t}
                          disabled={isFutureTime(t)}
                        >
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
        </div>

        <DialogFooter className="pt-4">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isSubmitting}
          >
            Cancel
          </Button>
          <Button onClick={onSubmit} disabled={isSubmitting}>
            Submit
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
