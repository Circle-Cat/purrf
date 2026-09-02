import { useState, useMemo, useEffect } from "react";
import Select from "react-select";
import {
  CalendarIcon,
  Clock,
  Plus,
  CalendarDays,
  ChevronDown,
} from "lucide-react";
import { toast } from "sonner";
import { format } from "date-fns";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Calendar } from "@/components/ui/calendar";
import { userDisplayName } from "@/utils/userName";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";

import TimezoneSelector from "@/components/common/TimezoneSelector";
import MeetingLogForm from "@/pages/PersonalDashboard/components/MeetingLogForm";
import { useMeetingManagement } from "@/pages/PersonalDashboard/hooks/useMeetingManagement";
import {
  HALF_HOUR_SLOTS,
  formatLocalYmd,
  hhMmToMinutes,
  isSameLocalDay,
  localToUtcIso,
  minutesIntoLocalDay,
  nowInTz,
  todayInTz,
} from "@/utils/dateTime";

const DURATION_OPTIONS = [
  { value: "30", label: "30 minutes" },
  { value: "45", label: "45 minutes" },
  { value: "60", label: "1 hour" },
  { value: "90", label: "1.5 hours" },
];

const INTERVAL_OPTIONS = [
  { value: "1", label: "1 week" },
  { value: "2", label: "2 weeks" },
];

const SESSION_COUNT_OPTIONS = Array.from({ length: 12 }, (_, i) => ({
  value: String(i + 1),
  label: String(i + 1),
}));

const TIME_SLOTS = HALF_HOUR_SLOTS.map((timeStr) => ({
  value: timeStr,
  label: timeStr,
}));

/**
 * Placeholder shown inside a tab that exists for this viewer but cannot be
 * used right now, in place of the form it would otherwise hold.
 */
function UnavailableNotice({ reason }) {
  return (
    <div className="flex flex-col items-center justify-center h-64 border-2 border-dashed border-gray-100 rounded-xl bg-gray-50/50">
      <CalendarDays className="w-12 h-12 text-gray-200 mb-2" />
      <p className="text-gray-400 font-medium">{reason}</p>
    </div>
  );
}

export default function MeetingManagementDialog({
  roundId,
  canSchedule = true,
  scheduleUnavailableReason = null,
  canLogPast = false,
  logPartnerId = null,
  logUnavailableReason = null,
  onBooked,
  onLogged,
  userTimezone,
}) {
  // Booking a meeting needs a round that is open for scheduling; logging a
  // meeting already held does not, which is why it reads `roundId` directly.
  // Passing null here also keeps the hook from fetching for a round nothing on
  // this side can act on.
  const scheduleRoundId =
    canSchedule && !scheduleUnavailableReason ? roundId : null;

  const { partners, bookMeeting, isLoading } =
    useMeetingManagement(scheduleRoundId);

  // Which tabs this viewer is offered at all, and which of those can be acted
  // on right now. Both the trigger button and the tab the dialog opens on are
  // read off this one list, so they cannot disagree.
  const tabs = [];
  if (canSchedule) {
    tabs.push({
      value: "schedule",
      label: "Schedule Meeting",
      unavailableReason: scheduleUnavailableReason,
    });
  }
  if (canLogPast) {
    tabs.push({
      value: "log",
      label: "Log Past Meeting",
      unavailableReason: logUnavailableReason,
    });
  }
  const usableTabs = tabs.filter((tab) => !tab.unavailableReason);
  const defaultTab = usableTabs[0]?.value;

  const [isOpen, setIsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState(defaultTab);

  const [selectedDate, setSelectedDate] = useState(null);
  const [selectedTime, setSelectedTime] = useState("");
  const [calendarOpen, setCalendarOpen] = useState(false);

  const initialFormState = {
    partnerId: "",
    duration: "30",
    intervalWeeks: "1",
    count: "1",
    timezone: userTimezone,
  };
  const [formData, setFormData] = useState(initialFormState);

  useEffect(() => {
    setFormData((prev) => ({ ...prev, timezone: userTimezone }));
  }, [userTimezone]);

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

  const tzNow = nowInTz(formData.timezone);
  const isPastDate =
    !!selectedDate &&
    formatLocalYmd(selectedDate) < formatLocalYmd(disableBeforeDate);
  const isTodayInTz = !!selectedDate && isSameLocalDay(selectedDate, tzNow);
  const currentMinutesInTz = minutesIntoLocalDay(tzNow);

  const isPastTime = (timeStr) => {
    if (isPastDate) return true;
    if (!isTodayInTz) return false;
    return hhMmToMinutes(timeStr) < currentMinutesInTz;
  };

  const handleTimezoneChange = (timezoneOption) => {
    const tzValue =
      typeof timezoneOption === "string"
        ? timezoneOption
        : timezoneOption?.value || "";
    setFormData((prev) => ({ ...prev, timezone: tzValue }));
  };

  // Nothing behind the button can be acted on, so it opens onto a wall of
  // placeholders -- say why on the button instead of letting it be clicked.
  const isDisabled = usableTabs.length === 0;
  const tooltipText = isDisabled ? tabs[0]?.unavailableReason : undefined;

  const closeAndResetDialog = () => {
    setIsOpen(false);

    setTimeout(() => {
      setFormData(initialFormState);
      setSelectedDate(null);
      setSelectedTime("");
      setActiveTab(defaultTab);
      setCalendarOpen(false);
    }, 200);
  };

  const handleOpenChange = (open) => {
    if (!open) {
      closeAndResetDialog();
    } else {
      setActiveTab(defaultTab);
      setIsOpen(true);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (scheduleRoundId == null) {
      toast.error("Current round is inactive.");
      return;
    }

    if (!formData.partnerId || !selectedDate || !selectedTime) {
      toast.error("Please fill in all required fields.");
      return;
    }

    try {
      const startInstant = localToUtcIso(
        selectedDate,
        selectedTime,
        formData.timezone,
      );
      if (new Date(startInstant) < new Date()) {
        toast.error("Start time must be now or in the future.");
        return;
      }

      const cleanedPayload = {
        round_id: Number(scheduleRoundId),
        partner_id: Number(formData.partnerId),
        timezone: formData.timezone,
        start_date: formatLocalYmd(selectedDate),
        start_time: selectedTime,
        duration_minutes: Number(formData.duration),
        interval_weeks: Number(formData.intervalWeeks),
        count: Number(formData.count),
      };

      const result = await bookMeeting(cleanedPayload);
      await onBooked?.();

      const created = result?.created ?? [];
      const failed = result?.failed ?? [];
      if (failed.length === 0) {
        toast.success("Meeting booked successfully!");
      } else if (created.length > 0) {
        toast.error(
          `Created ${created.length} of ${created.length + failed.length} sessions (${failed.length} failed)`,
        );
      } else {
        toast.error("Failed to book meeting. Please try again.");
      }

      if (isOpen && created.length > 0) {
        setFormData(initialFormState);
        setSelectedDate(null);
        setIsOpen(false);
      }
    } catch {
      toast.error("Failed to book meeting. Please try again.");
    }
  };

  // The map carries every pairing of the round, ended ones included. Those are
  // not somewhere a new meeting can be booked -- the backend refuses one
  // without a live pair -- so only current partners are offered.
  const partnerList = partners
    ? Array.from(partners.values()).filter(
        (partner) => partner.isActive !== false,
      )
    : [];

  if (tabs.length === 0) return null;

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <div key={roundId} title={tooltipText} className="inline-block">
        <DialogTrigger asChild>
          <Button variant="default" size="sm" disabled={isDisabled}>
            <CalendarIcon className="w-4 h-4 mr-2" />
            Manage Meetings
          </Button>
        </DialogTrigger>
      </div>

      <DialogContent className="w-full max-w-2xl rounded-xl bg-white shadow-2xl p-0 animate-in fade-in zoom-in-95 duration-200 overflow-visible">
        {/* Header */}
        <div className="flex items-center justify-between bg-gray-50/50 px-5 py-3 border-b rounded-t-xl">
          <DialogTitle className="text-xl font-semibold text-gray-900 flex items-center gap-2">
            <CalendarIcon className="w-5 h-5 text-[#6035F3]" />
            Meeting Management
          </DialogTitle>
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <div className="px-6 mt-4">
            <TabsList
              className="grid w-full p-1.5 h-12 bg-gray-100 rounded-lg"
              style={{
                gridTemplateColumns: `repeat(${tabs.length}, minmax(0, 1fr))`,
              }}
            >
              {tabs.map((tab) => (
                <TabsTrigger
                  key={tab.value}
                  value={tab.value}
                  className="h-full text-sm font-medium rounded-md text-gray-500 transition-all data-[state=active]:bg-white data-[state=active]:text-[#6035F3] data-[state=active]:shadow-sm"
                >
                  {tab.label}
                </TabsTrigger>
              ))}
            </TabsList>
          </div>

          {/* Content Area */}
          <div className="p-4 sm:p-5">
            {canSchedule && (
              /* Schedule Meeting Form */
              <TabsContent
                value="schedule"
                className="mt-0 focus-visible:outline-none"
              >
                {scheduleUnavailableReason ? (
                  <UnavailableNotice reason={scheduleUnavailableReason} />
                ) : (
                  <form onSubmit={handleSubmit} className="space-y-3.5">
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
                              {userDisplayName(partner)}
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
                        <Popover
                          open={calendarOpen}
                          onOpenChange={setCalendarOpen}
                        >
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
                            aria-label="Start Time"
                            options={TIME_SLOTS}
                            value={
                              selectedTime && !isPastTime(selectedTime)
                                ? TIME_SLOTS.find(
                                    (opt) => opt.value === selectedTime,
                                  )
                                : null
                            }
                            onChange={(opt) => setSelectedTime(opt.value)}
                            isOptionDisabled={(opt) => isPastTime(opt.value)}
                            placeholder="Pick a start time"
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

                    {/* Recurrence: interval + number of sessions */}
                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                      <div className="space-y-1.5">
                        <label className="text-sm font-medium text-gray-700">
                          Repeat every
                        </label>
                        <div className="relative">
                          <select
                            name="intervalWeeks"
                            aria-label="Repeat every"
                            value={formData.intervalWeeks}
                            onChange={handleInputChange}
                            className="w-full appearance-none rounded-lg border border-gray-300 bg-white px-4 py-2.5 text-gray-900 focus:border-[#6035F3] focus:ring-2 focus:ring-[#6035F3]/20 outline-none transition-all"
                          >
                            {INTERVAL_OPTIONS.map((opt) => (
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

                      <div className="space-y-1.5">
                        <label className="text-sm font-medium text-gray-700">
                          Number of sessions
                        </label>
                        <div className="relative">
                          <select
                            name="count"
                            aria-label="Number of sessions"
                            value={formData.count}
                            onChange={handleInputChange}
                            className="w-full appearance-none rounded-lg border border-gray-300 bg-white px-4 py-2.5 text-gray-900 focus:border-[#6035F3] focus:ring-2 focus:ring-[#6035F3]/20 outline-none transition-all"
                          >
                            {SESSION_COUNT_OPTIONS.map((opt) => (
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
                )}
              </TabsContent>
            )}

            {canLogPast && (
              <TabsContent
                value="log"
                className="mt-0 focus-visible:outline-none"
              >
                {logUnavailableReason ? (
                  <UnavailableNotice reason={logUnavailableReason} />
                ) : (
                  <MeetingLogForm
                    roundId={roundId}
                    partnerId={logPartnerId}
                    userTimezone={userTimezone}
                    onSuccess={async () => {
                      await onLogged?.();
                      closeAndResetDialog();
                    }}
                  />
                )}
              </TabsContent>
            )}
          </div>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
