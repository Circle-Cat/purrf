import { useState, useMemo, useEffect } from "react";
import Select from "react-select";
import {
  CalendarIcon,
  Clock,
  Plus,
  CalendarDays,
  ChevronDown,
  Trash2 as TrashIcon,
} from "lucide-react";
import { toast } from "sonner";
import { format } from "date-fns";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Calendar } from "@/components/ui/calendar";
import { partnerDisplayName } from "@/utils/partnerName";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";

import TimezoneSelector from "@/components/common/TimezoneSelector";
import { useMeetingManagement } from "@/pages/PersonalDashboard/hooks/useMeetingManagement";
import { localToUtcIso, todayInTz, formatInTz } from "@/utils/dateTime";

const DURATION_OPTIONS = [
  { value: "30", label: "30 minutes" },
  { value: "45", label: "45 minutes" },
  { value: "60", label: "1 hour" },
  { value: "90", label: "1.5 hours" },
];

const TIME_SLOTS = Array.from({ length: 48 }, (_, i) => {
  const hour = String(Math.floor(i / 2)).padStart(2, "0");
  const min = i % 2 === 0 ? "00" : "30";
  const timeStr = `${hour}:${min}`;
  return { value: timeStr, label: timeStr };
});

export default function MeetingManagementDialog({
  roundId,
  onBooked,
  userTimezone,
}) {
  const {
    partners,
    bookMeeting,
    upcomingMeetings = [],
    cancelMeetings,
    isLoading,
  } = useMeetingManagement(roundId);
  const [isOpen, setIsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("schedule");

  const [selectedDate, setSelectedDate] = useState(null);
  const [selectedTime, setSelectedTime] = useState("09:00");
  const [calendarOpen, setCalendarOpen] = useState(false);

  const [selectedIds, setSelectedIds] = useState(new Set());

  const initialFormState = {
    partnerId: "",
    duration: "30",
    timezone:
      userTimezone || Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
  };
  const [formData, setFormData] = useState(initialFormState);

  const upcomingLength = upcomingMeetings.length;
  useEffect(() => {
    setSelectedIds(new Set());
  }, [isOpen, activeTab, upcomingMeetings.length]);

  const isAllChecked = useMemo(() => {
    return upcomingLength > 0 && selectedIds.size === upcomingLength;
  }, [selectedIds, upcomingLength]);

  const handleToggleAll = () => {
    if (isAllChecked) {
      setSelectedIds(new Set());
    } else {
      const allIds = upcomingMeetings.map((m) => m.meetingId);
      setSelectedIds(new Set(allIds));
    }
  };

  // Toggle single item selection
  const handleToggleItem = (meetingId) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(meetingId)) {
        next.delete(meetingId);
      } else {
        next.add(meetingId);
      }
      return next;
    });
  };

  // Trigger batch deletion
  const handleDeleteSelected = async () => {
    if (selectedIds.size === 0) return;

    // Construct the full selected meeting objects for processing in cancelMeetings
    const selectedMeetings = upcomingMeetings.filter((m) =>
      selectedIds.has(m.meetingId),
    );

    try {
      await cancelMeetings(selectedMeetings);
      toast.success("Meetings cancelled successfully!");
      setSelectedIds(new Set()); // Clear checked states upon success

      await onBooked?.();
    } catch (error) {
      console.error("Failed to delete meetings in UI:", error);
      toast.error("Failed to cancel selected meetings.");
    }
  };

  // Helper function: Format meeting card details based on user's local timezone
  const formatCardDetails = (startStr, endStr, userTimezone) => {
    const durationMin = Math.round(
      (new Date(endStr) - new Date(startStr)) / 1000 / 60,
    );
    return {
      dateStr: formatInTz(startStr, userTimezone, "EEE, MMM d, yyyy"),
      timeStr: `${formatInTz(startStr, userTimezone, "HH:mm")} - ${formatInTz(endStr, userTimezone, "HH:mm")}`,
      durationStr: `${durationMin} mins`,
      timezoneStr: userTimezone,
    };
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const disableBeforeDate = useMemo(() => {
    try {
      return todayInTz(formData.timezone);
    } catch {
      return new Date();
    }
  }, [formData.timezone]);

  const handleTimezoneChange = (timezoneOption) => {
    const tzValue =
      typeof timezoneOption === "string"
        ? timezoneOption
        : timezoneOption?.value || "";
    setFormData((prev) => ({ ...prev, timezone: tzValue }));
  };

  const isDisabled = roundId === null || roundId === undefined;
  const tooltipText = isDisabled ? "No active mentorship round" : undefined;

  const closeAndResetDialog = () => {
    setIsOpen(false);

    setTimeout(() => {
      setFormData(initialFormState);
      setSelectedDate(null);
      setSelectedTime("09:00");
      setActiveTab("schedule");
      setCalendarOpen(false);
    }, 200);
  };

  const handleOpenChange = (open) => {
    if (!open) {
      closeAndResetDialog();
    } else {
      setIsOpen(true);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (isDisabled) {
      toast.error("Current round is inactive.");
      return;
    }

    if (!formData.partnerId || !selectedDate || !selectedTime) {
      toast.error("Please fill in all required fields.");
      return;
    }

    try {
      const startUtc = localToUtcIso(
        selectedDate,
        selectedTime,
        formData.timezone,
      );
      const startDateObj = new Date(startUtc);
      const endDateObj = new Date(
        startDateObj.getTime() + Number(formData.duration) * 60 * 1000,
      );
      const endUtc = endDateObj.toISOString();

      const cleanedPayload = {
        round_id: Number(roundId),
        partner_id: Number(formData.partnerId),
        start_datetime: startUtc,
        end_datetime: endUtc,
      };

      await bookMeeting(cleanedPayload);
      await onBooked?.();

      if (isOpen) {
        toast.success("Meeting booked successfully!");
        setFormData(initialFormState);
        setSelectedDate(null);
        setIsOpen(false);
      }
    } catch {
      toast.error("Failed to book meeting. Please try again.");
    }
  };

  const partnerList = partners ? Array.from(partners.values()) : [];

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <div key={roundId} title={tooltipText} className="inline-block">
        <DialogTrigger asChild>
          <Button
            variant="default"
            disabled={isDisabled}
            onClick={() => console.log("Current meetingRoundId:", roundId)}
          >
            <CalendarIcon className="w-4 h-4 mr-2" />
            Manage Meetings
          </Button>
        </DialogTrigger>
      </div>

      <DialogContent className="w-full max-w-2xl !h-auto max-h-[80vh] rounded-xl bg-white shadow-2xl p-0 animate-in fade-in zoom-in-95 duration-200 overflow-visible">
        {/* Header */}
        <div className="flex items-center justify-between bg-gray-50/50 px-6 py-4 border-b rounded-t-xl">
          <DialogTitle className="text-xl font-semibold text-gray-900 flex items-center gap-2">
            <CalendarIcon className="w-5 h-5 text-[#6035F3]" />
            Meeting Management
          </DialogTitle>
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <div className="px-6 mt-4">
            <TabsList className="grid w-full grid-cols-2 p-1.5 h-12 bg-gray-100 rounded-lg">
              <TabsTrigger
                value="schedule"
                className="h-full text-sm font-medium rounded-md text-gray-500 transition-all data-[state=active]:bg-white data-[state=active]:text-[#6035F3] data-[state=active]:shadow-sm"
              >
                Schedule Meeting
              </TabsTrigger>
              <TabsTrigger
                value="upcoming"
                className="h-full text-sm font-medium rounded-md text-gray-500 transition-all data-[state=active]:bg-white data-[state=active]:text-[#6035F3] data-[state=active]:shadow-sm"
              >
                Upcoming
              </TabsTrigger>
            </TabsList>
          </div>

          {/* Content Area */}
          <div className="p-6">
            {/* Schedule Meeting Form */}
            <TabsContent
              value="schedule"
              className="mt-0 focus-visible:outline-none"
            >
              <form onSubmit={handleSubmit} className="space-y-5">
                {/* Mentor / Mentee Selection Dropdown */}
                <div className="space-y-1.5">
                  <label className="text-sm font-medium text-gray-700">
                    Select Partner *
                  </label>
                  <div className="relative">
                    <select
                      name="partnerId"
                      aria-label="Select Partner"
                      value={formData.partnerId}
                      onChange={handleInputChange}
                      className="w-full appearance-none rounded-lg border border-gray-300 bg-white px-4 py-2.5 text-gray-900 focus:border-[#6035F3] focus:ring-2 focus:ring-[#6035F3]/20 outline-none transition-all"
                      required
                    >
                      <option value="">Choose a partner</option>
                      {partnerList.map((partner) => (
                        <option key={partner.id} value={partner.id}>
                          {partnerDisplayName(partner)}
                        </option>
                      ))}
                    </select>
                    <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-3 text-gray-400">
                      <ChevronDown className="w-4 h-4" />
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  {/* Timezone */}
                  <div className="space-y-1.5 min-w-0">
                    <label className="text-sm font-medium text-gray-700">
                      Timezone
                    </label>
                    <div className="w-full">
                      <TimezoneSelector
                        value={formData.timezone}
                        onChange={handleTimezoneChange}
                        labelSource="value"
                        menuPlacement="auto"
                      />
                    </div>
                  </div>

                  {/* Date Picker (Popover + Calendar) */}
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium text-gray-700">
                      Start Date *
                    </label>
                    <Popover open={calendarOpen} onOpenChange={setCalendarOpen}>
                      <PopoverTrigger asChild>
                        <Button
                          variant="outline"
                          className={cn(
                            "w-full justify-start text-left font-normal h-[42px] rounded-lg border-gray-300 px-4",
                            !selectedDate && "text-gray-400",
                          )}
                        >
                          <CalendarIcon className="mr-2 h-4 w-4 text-gray-400" />
                          {selectedDate ? (
                            format(selectedDate, "PPP")
                          ) : (
                            <span>Pick a date</span>
                          )}
                        </Button>
                      </PopoverTrigger>
                      <PopoverContent className="w-auto p-0" align="start">
                        <Calendar
                          mode="single"
                          selected={selectedDate}
                          onSelect={(date) => {
                            if (date) {
                              setSelectedDate(date);
                              setCalendarOpen(false);
                            }
                          }}
                          disabled={{ before: disableBeforeDate }}
                          initialFocus
                        />
                      </PopoverContent>
                    </Popover>
                  </div>
                </div>

                {/* Time Picker and Meeting Duration*/}
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium text-gray-700">
                      Start Time *
                    </label>
                    <div className="w-full min-w-0 relative">
                      <Clock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 z-10 pointer-events-none" />
                      <Select
                        options={TIME_SLOTS}
                        value={TIME_SLOTS.find(
                          (opt) => opt.value === selectedTime,
                        )}
                        onChange={(opt) => setSelectedTime(opt.value)}
                        menuPlacement="auto"
                        styles={{
                          control: (provided) => ({
                            ...provided,
                            height: "42px",
                            borderRadius: "8px",
                            borderColor: "#d1d5db",
                            boxShadow: "none",
                            paddingLeft: "26px",
                            "&:hover": { borderColor: "#d1d5db" },
                          }),
                          menu: (provided) => ({
                            ...provided,
                            zIndex: 50,
                          }),
                          menuList: (provided) => ({
                            ...provided,
                            maxHeight: "180px",
                          }),
                        }}
                      />
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-sm font-medium text-gray-700">
                      Duration *
                    </label>
                    <div className="relative">
                      <select
                        name="duration"
                        aria-label="Duration"
                        value={formData.duration}
                        onChange={handleInputChange}
                        className="w-full appearance-none rounded-lg border border-gray-300 bg-white px-4 py-2.5 text-gray-900 focus:border-[#6035F3] focus:ring-2 focus:ring-[#6035F3]/20 outline-none transition-all"
                        required
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
                </div>

                {/* Confirm Booking Button */}
                <div className="flex justify-end pt-4 border-t">
                  <button
                    type="submit"
                    disabled={isLoading}
                    className="flex items-center gap-2 rounded-lg bg-[#6035F3] hover:bg-[#4d2ac2] px-6 py-2.5 font-medium text-white shadow-md transition-all active:scale-95 disabled:bg-gray-400 disabled:active:scale-100"
                  >
                    {isLoading ? (
                      <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    ) : (
                      <Plus className="w-5 h-5" />
                    )}
                    Confirm Booking
                  </button>
                </div>
              </form>
            </TabsContent>

            {/* Upcoming Tab */}
            <TabsContent
              value="upcoming"
              className="mt-0 focus-visible:outline-none"
            >
              {upcomingLength === 0 ? (
                /* Empty state placeholder text preserved */
                <div className="flex flex-col items-center justify-center h-64 border-2 border-dashed border-gray-100 rounded-xl bg-gray-50/50 my-auto">
                  <CalendarDays className="w-12 h-12 text-gray-200 mb-2" />
                  <p className="text-gray-400 font-medium">
                    No upcoming meetings found
                  </p>
                </div>
              ) : (
                <div className="flex flex-col min-h-0 justify-between flex-1 overflow-hidden">
                  <div className="overflow-hidden">
                    {/* Top Control Bar: Select All Checkbox */}
                    <div className="flex items-center space-x-3 pb-3 mb-4 border-b border-gray-100 flex-shrink-0">
                      <Checkbox
                        id="select-all-upcoming"
                        checked={isAllChecked}
                        onCheckedChange={handleToggleAll}
                        disabled={isLoading}
                      />
                      <label
                        htmlFor="select-all-upcoming"
                        className="text-sm font-semibold text-gray-700 cursor-pointer select-none"
                      >
                        Select All
                      </label>
                    </div>

                    {/* Card List */}
                    <div className="space-y-3 max-h-[300px] overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-gray-200">
                      {upcomingMeetings.map((meeting) => {
                        const isChecked = selectedIds.has(meeting.meetingId);
                        const { dateStr, timeStr, durationStr, timezoneStr } =
                          formatCardDetails(
                            meeting.startDatetime,
                            meeting.endDatetime,
                            userTimezone ||
                              Intl.DateTimeFormat().resolvedOptions()
                                .timeZone ||
                              "UTC",
                          );

                        return (
                          <div
                            key={meeting.meetingId}
                            className={cn(
                              "flex items-center p-4 border rounded-xl transition-all duration-200",
                              isChecked
                                ? "border-[#6035F3] bg-[#6035F3]/5 shadow-sm"
                                : "border-gray-200 bg-white hover:border-gray-300",
                            )}
                          >
                            {/* Single Selection Checkbox */}
                            <div className="mr-4 flex items-center">
                              <Checkbox
                                id={`check-${meeting.meetingId}`}
                                checked={isChecked}
                                onCheckedChange={() =>
                                  handleToggleItem(meeting.meetingId)
                                }
                                disabled={isLoading}
                              />
                            </div>

                            {/* Core Card Content Display */}
                            <div className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                              {/* Left Side: Partner Info */}
                              <div className="flex flex-col justify-center">
                                <h4 className="font-semibold text-gray-900 flex items-center gap-2 flex-wrap">
                                  {meeting.partnerName}
                                </h4>
                              </div>

                              {/* Right Side: Formatted Date/Time & Duration in User's Timezone */}
                              <div className="sm:text-right flex flex-col justify-center space-y-0.5">
                                <p className="font-medium text-gray-800">
                                  {dateStr}
                                </p>
                                <p className="text-xs font-mono text-[#6035F3] font-semibold">
                                  {timeStr}
                                </p>
                                <p className="text-[11px] text-gray-400">
                                  Duration:{" "}
                                  <span className="text-gray-700 font-medium">
                                    {durationStr}
                                  </span>
                                  <span className="mx-1.5 text-gray-300">
                                    |
                                  </span>
                                  TZ:{" "}
                                  <span
                                    className="text-gray-700"
                                    title={timezoneStr}
                                  >
                                    {timezoneStr
                                      .split("/")
                                      .pop()
                                      .replace("_", " ")}
                                  </span>
                                </p>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Delete Button */}
                  <div className="flex justify-end mt-2 pt-2 border-t border-gray-50 bg-white flex-shrink-0">
                    <Button
                      variant="destructive"
                      size="lg"
                      className="px-6 font-medium text-white shadow-md transition-all active:scale-95 disabled:bg-gray-200 disabled:text-gray-400 disabled:shadow-none disabled:active:scale-100"
                      disabled={selectedIds.size === 0 || isLoading}
                      onClick={handleDeleteSelected}
                    >
                      <TrashIcon className="w-4 h-4" />
                      Delete ({selectedIds.size})
                    </Button>
                  </div>
                </div>
              )}
            </TabsContent>
          </div>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
