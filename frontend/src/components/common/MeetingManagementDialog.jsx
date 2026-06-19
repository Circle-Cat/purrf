import { useState } from "react";
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
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";

import TimezoneSelector from "@/components/common/TimezoneSelector";
import { useMeetingManagement } from "@/pages/PersonalDashboard/hooks/useMeetingManagement";

const DURATION_OPTIONS = [
  { value: "30", label: "30 minutes" },
  { value: "45", label: "45 minutes" },
  { value: "60", label: "1 hour" },
  { value: "90", label: "1.5 hours" },
];

const TIME_SLOTS = Array.from({ length: 48 }, (_, i) => {
  const hour = String(Math.floor(i / 2)).padStart(2, "0");
  const min = i % 2 === 0 ? "00" : "30";
  return `${hour}:${min}`;
});

function toUTCISOString(localDatetimeStr, timezone, durationMinutes = 0) {
  if (!localDatetimeStr) return "";

  // Concatenate the input YYYY-MM-DDTHH:mm with the target timezone, and let Intl handle the parsing
  const [datePart, timePart] = localDatetimeStr.split("T");
  const [year, month, day] = datePart.split("-").map(Number);
  const [hours, minutes] = timePart.split(":").map(Number);

  // Leverage Intl to find the actual absolute time difference between the target timezone and UTC
  const formatter = new Intl.DateTimeFormat("en-US", {
    timeZone: timezone,
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "numeric",
    minute: "numeric",
    second: "numeric",
    hour12: false,
  });

  // Construct a baseline UTC timestamp and calculate the literal difference in that timezone
  const utcUtc = Date.UTC(year, month - 1, day, hours, minutes);
  const parts = formatter.formatToParts(new Date(utcUtc));

  const p = Object.fromEntries(parts.map((part) => [part.type, part.value]));

  const hourNum = Number(p.hour);
  const d = Date.UTC(
    Number(p.year),
    Number(p.month) - 1,
    Number(p.day),
    hourNum === 24 ? 0 : hourNum,
    Number(p.minute),
  );

  // Actual offset in milliseconds
  const offsetAir = utcUtc - d;
  const targetDate = new Date(utcUtc + offsetAir);

  // Add the meeting duration
  const extraMinutes = Number(durationMinutes);
  if (extraMinutes > 0) {
    targetDate.setMinutes(targetDate.getMinutes() + extraMinutes);
  }

  return targetDate.toISOString(); // Returns a standard ISO UTC string ending in 'Z'
}

/* eslint-disable no-unused-vars */
function getTodayInTimezone(timezone) {
  const [year, month, day] = new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  })
    .format(new Date())
    .split("-")
    .map(Number);
  return { year, month, day };
}

function formatMeetingDate(dateStr) {
  const [year, month, day] = dateStr.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

function formatDuration(value) {
  const mins = Number(value);
  if (mins >= 60) {
    const hrs = mins / 60;
    return hrs === 1 ? "1 hour" : `${hrs} hours`;
  }
  return `${mins} min`;
}
/* eslint-disable no-unused-vars */

export default function MeetingManagementDialog({ roundId }) {
  const { partners, bookMeeting, isLoading } = useMeetingManagement(roundId);
  const [isOpen, setIsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("schedule");

  const [selectedDate, setSelectedDate] = useState(null);
  const [selectedTime, setSelectedTime] = useState("09:00");

  const initialFormState = {
    partnerId: "",
    duration: "30",
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
  };
  const [formData, setFormData] = useState(initialFormState);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleTimezoneChange = (timezoneOption) => {
    const tzValue =
      typeof timezoneOption === "string"
        ? timezoneOption
        : timezoneOption?.value || "";
    setFormData((prev) => ({ ...prev, timezone: tzValue }));
  };

  const isDisabled = roundId === null || roundId === undefined;
  const tooltipText = isDisabled ? "No active mentorship round" : undefined;

  const handleOpenChange = (open) => {
    setIsOpen(open);
    if (!open) {
      // Delay resetting to prevent content flickering during the dialog closing animation
      setTimeout(() => {
        setFormData(initialFormState);
        setSelectedDate(null);
        setSelectedTime("09:00");
        setActiveTab("schedule");
      }, 200);
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
      const localDatetimeStr = `${format(selectedDate, "yyyy-MM-dd")}T${selectedTime}`;

      const startUtc = toUTCISOString(localDatetimeStr, formData.timezone, 0);
      const endUtc = toUTCISOString(
        localDatetimeStr,
        formData.timezone,
        formData.duration,
      );

      const cleanedPayload = {
        round_id: Number(roundId),
        partner_id: Number(formData.partnerId),
        start_datetime: startUtc,
        end_datetime: endUtc,
      };

      await bookMeeting(cleanedPayload);

      if (isOpen) {
        toast.success("Meeting booked successfully!");
        setFormData(initialFormState);
        setSelectedDate(null);
        setIsOpen(false);
      }
    } catch (error) {
      toast.error("Failed to book meeting. Please try again.");
    }
  };

  const partnerList = partners ? Array.from(partners.values()) : [];

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <div key={roundId} title={tooltipText} className="inline-block">
        <DialogTrigger asChild>
          <Button variant="default" disabled={isDisabled}>
            <CalendarIcon className="w-4 h-4 mr-2" />
            Manage Meetings
          </Button>
        </DialogTrigger>
      </div>

      <DialogContent className="w-full max-w-2xl rounded-xl bg-white shadow-2xl p-0 overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="flex items-center justify-between bg-gray-50/50 px-6 py-4 border-b">
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
                      <option value="">Choose a mentor or mentee</option>
                      {partnerList.map((partner) => (
                        <option key={partner.id} value={partner.id}>
                          {partner.preferredName || partner.name} (
                          {partner.email})
                        </option>
                      ))}
                    </select>
                    <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-3 text-gray-400">
                      <ChevronDown className="w-4 h-4" />
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  {/* Date Picker (Popover + Calendar) */}
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium text-gray-700">
                      Start Date *
                    </label>
                    <Popover>
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
                          onSelect={setSelectedDate}
                          initialFocus
                        />
                      </PopoverContent>
                    </Popover>
                  </div>

                  {/* Time Picker (Pure text/numeric dropdown to prevent mixed-language locale formatting bugs) */}
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium text-gray-700">
                      Start Time *
                    </label>
                    <div className="relative">
                      <Clock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                      <select
                        aria-label="Start Time"
                        value={selectedTime}
                        onChange={(e) => setSelectedTime(e.target.value)}
                        className="w-full appearance-none rounded-lg border border-gray-300 bg-white pl-10 pr-4 py-2.5 text-gray-900 focus:border-[#6035F3] focus:ring-2 focus:ring-[#6035F3]/20 outline-none transition-all"
                        required
                      >
                        {TIME_SLOTS.map((slot) => (
                          <option key={slot} value={slot}>
                            {slot}
                          </option>
                        ))}
                      </select>
                      <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-3 text-gray-400">
                        <ChevronDown className="w-4 h-4" />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Meeting Duration and Timezone */}
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
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

                  <div className="space-y-1.5">
                    <label className="text-sm font-medium text-gray-700">
                      Timezone
                    </label>
                    <TimezoneSelector
                      value={formData.timezone}
                      onChange={handleTimezoneChange}
                      labelSource="value"
                    />
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
              <div className="flex flex-col items-center justify-center h-64 border-2 border-dashed border-gray-100 rounded-xl bg-gray-50/50">
                <CalendarDays className="w-12 h-12 text-gray-200 mb-2" />
                <p className="text-gray-400 font-medium">
                  No upcoming meetings found
                </p>
              </div>
            </TabsContent>
          </div>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
