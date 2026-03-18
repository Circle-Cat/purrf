import { useState } from "react";
import TimezoneSelect from "react-timezone-select";
import { Calendar as CalendarIcon, Check } from "lucide-react";
import { format, endOfToday } from "date-fns";
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
 * datetime is converted to UTC and posted to the backend.
 *
 * @param {{
 *   open: boolean,
 *   onOpenChange: (open: boolean) => void,
 *   roundId: number | string,
 *   userTimezone: string | null,
 *   onSuccess: () => void
 * }} props
 */
export default function MeetingSubmissionModal({
  open,
  onOpenChange,
  roundId,
  userTimezone,
  onSuccess,
}) {
  // Initialize timezone with the user's profile timezone, fallback to browser timezone
  const [timezone, setTimezone] = useState(
    userTimezone ?? Intl.DateTimeFormat().resolvedOptions().timeZone,
  );
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [selectedDate, setSelectedDate] = useState(new Date());
  const [startTime, setStartTime] = useState("10:00");
  const [endTime, setEndTime] = useState("11:00");
  const [slotError, setSlotError] = useState(null);

  /**
   * Constructs an ISO-8601 string containing an explicit timezone offset.
   *
   * Combines the selected calendar date, time string, and timezone offset
   * into a formatted value such as "2026-03-13T10:00:00-05:00".
   *
   * @param {Date} dateObj - The calendar date picked by the user.
   * @param {string} timeStr - The time string (e.g., "10:30").
   * @param {object|string} tzState - The timezone object from react-timezone-select.
   * @returns {string} - Formatted datetime string with timezone offset.
   */
  const formatOffset = (offsetHours) => {
    const sign = offsetHours >= 0 ? "+" : "-";
    const absHours = Math.floor(Math.abs(offsetHours));
    const absMins = Math.round((Math.abs(offsetHours) % 1) * 60);
    return `${sign}${String(absHours).padStart(2, "0")}:${String(absMins).padStart(2, "0")}`;
  };

  const formatTimezoneAwareISO = (dateObj, timeStr, tzState) => {
    // Extract calendar date
    const year = dateObj.getFullYear();
    const month = String(dateObj.getMonth() + 1).padStart(2, "0");
    const day = String(dateObj.getDate()).padStart(2, "0");

    // Determine timezone offset in hours (defaults to browser local offset)
    const offsetHours =
      tzState?.offset ?? -(new Date().getTimezoneOffset() / 60);
    const offsetStr = formatOffset(offsetHours);

    return `${year}-${month}-${day}T${timeStr}:00${offsetStr}`;
  };

  const [startH, startM] = startTime.split(":").map(Number);
  const [endH, endM] = endTime.split(":").map(Number);

  const validateTimesNotEqual = () => startH !== endH || startM !== endM;

  const onSubmit = async () => {
    setIsSubmitting(true);
    setSlotError(null);

    if (!validateTimesNotEqual()) {
      setSlotError("Start time and end time cannot be the same.");
      setIsSubmitting(false);
      return;
    }

    try {
      const startObj = new Date(selectedDate);
      const endObj = new Date(selectedDate);
      if (endH < startH || (endH === startH && endM < startM)) {
        endObj.setDate(endObj.getDate() + 1);
      }

      await postMyMentorshipMeetingLog({
        roundId: Number(roundId),
        startDatetime: new Date(
          formatTimezoneAwareISO(startObj, startTime, timezone),
        ).toISOString(),
        endDatetime: new Date(
          formatTimezoneAwareISO(endObj, endTime, timezone),
        ).toISOString(),
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
              onChange={setTimezone}
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
                      disabled={{ after: endOfToday() }}
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
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="z-[201]">
                      {timeOptions.map((t) => (
                        <SelectItem key={t} value={t}>
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
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="z-[201]">
                      {timeOptions.map((t) => (
                        <SelectItem key={t} value={t}>
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
