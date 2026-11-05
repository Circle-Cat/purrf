import { useState } from "react";
import { Calendar, CalendarClock, Trash2, Video } from "lucide-react";
import { formatInTz } from "@/utils/dateTime";
import {
  getMeetingStatus,
  isWithinJoinWindow,
} from "@/utils/meetingStatusCalculator";
import { MeetingStatus } from "@/constants/MeetingStatus";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

/**
 * Format a UTC datetime range into a human-readable date and time range
 * string, converted into the user's profile timezone.
 *
 * @param {string} startUtc - Start datetime in UTC ISO format.
 * @param {string} endUtc - End datetime in UTC ISO format.
 * @param {string} timezone - IANA timezone string (e.g. "Asia/Shanghai").
 * @returns {{ date: string, timeRange: string }}
 */
function formatMeetingTime(startUtc, endUtc, timezone) {
  return {
    date: formatInTz(startUtc, timezone, "yyyy-MM-dd"),
    timeRange: `${formatInTz(startUtc, timezone, "HH:mm")} - ${formatInTz(endUtc, timezone, "HH:mm")}`,
  };
}

/**
 * Order two meetings newest start time first. A meeting whose start time is
 * missing or unparsable sorts to the end instead of turning the comparison
 * into NaN, which would leave the whole list in an arbitrary order.
 *
 * @param {{startDatetime?: string}} a
 * @param {{startDatetime?: string}} b
 * @returns {number}
 */
function compareByStartDatetimeDesc(a, b) {
  const aStart = new Date(a?.startDatetime).getTime();
  const bStart = new Date(b?.startDatetime).getTime();
  const aRank = Number.isNaN(aStart) ? -Infinity : aStart;
  const bRank = Number.isNaN(bStart) ? -Infinity : bStart;
  if (aRank === bRank) return 0;
  return aRank > bRank ? -1 : 1;
}

/**
 * Displays a summary card for one partner's meeting history in a mentorship round.
 *
 * Shows:
 * - Meeting statistics (required, completed, completion rate)
 * - A scrollable list of individual meeting slots with status badges
 *
 * All datetimes are displayed in the user's profile timezone (`userTimezone`).
 *
 * A meeting created through Google carries a `meetLink`, which is rendered as
 * a Join entry point; a manually logged meeting has none and shows no button.
 *
 * Only a `SCHEDULED` meeting can be called off or moved, and only when the
 * viewer is offered managing meetings at all: a completed meeting is a record
 * of something that happened, and a past uncompleted one is history the
 * attendance sweep never closed out. Neither is something there is still any
 * point in cancelling or rescheduling.
 *
 * Rescheduling itself is not handled here -- the reschedule control just
 * hands the meeting to `onRescheduleMeeting`, and the parent owns the dialog
 * that collects the new slot.
 *
 * @param {{ overview: {
 *   requiredMeetings: number,
 *   completedCount: number,
 *   completedRate: number,
 *   meetingTimeList: Array<{ meetLink?: string }>,
 * } userTimezone: string,
 *   showMeetingList?: boolean,
 *   canManageMeetings?: boolean,
 *   onDeleteMeeting?: (meeting: Object) => Promise<void>,
 *   onRescheduleMeeting?: (meeting: Object) => void}} props
 */
export default function MeetingOverviewCard({
  overview,
  userTimezone,
  showMeetingList = true,
  canManageMeetings = false,
  onDeleteMeeting,
  onRescheduleMeeting,
}) {
  // The meeting awaiting confirmation, or null while nothing is pending.
  const [meetingToCancel, setMeetingToCancel] = useState(null);
  const [isCancelling, setIsCancelling] = useState(false);

  const cancelPrompt = meetingToCancel
    ? formatMeetingTime(
        meetingToCancel.startDatetime,
        meetingToCancel.endDatetime,
        userTimezone,
      )
    : null;

  const handleConfirmCancel = async () => {
    if (!meetingToCancel) return;
    setIsCancelling(true);
    try {
      await onDeleteMeeting?.(meetingToCancel);
      setMeetingToCancel(null);
    } finally {
      setIsCancelling(false);
    }
  };

  return (
    <div>
      {/* Meeting Statistics */}
      <div className="grid grid-cols-3 gap-4 mb-6 p-4 bg-gray-50 rounded-lg">
        <div className="text-center">
          <div className="text-sm text-gray-600 mb-1">Required Meetings</div>
          <div className="text-2xl">{overview.requiredMeetings}</div>
        </div>
        <div className="text-center">
          <div className="text-sm text-gray-600 mb-1">Completed</div>
          <div className="text-2xl text-green-600">
            {overview.completedCount}
          </div>
        </div>
        <div className="text-center">
          <div className="text-sm text-gray-600 mb-1">Completion Rate</div>
          <div className="text-2xl text-[#6035F3]">
            {overview.completedRate}%
          </div>
        </div>
      </div>

      {/* Meeting List */}
      {showMeetingList && (
        <div className="space-y-2">
          <h5 className="text-sm text-gray-600 mb-2">Meeting List</h5>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {!overview.meetingTimeList?.length ? (
              <p className="text-sm text-gray-400 italic py-2">
                No meetings scheduled.
              </p>
            ) : (
              [...overview.meetingTimeList]
                .sort(compareByStartDatetimeDesc)
                .map((m) => {
                  const { date, timeRange } = formatMeetingTime(
                    m.startDatetime,
                    m.endDatetime,
                    userTimezone,
                  );
                  const status = getMeetingStatus(
                    m.isCompleted,
                    m.startDatetime,
                  );
                  return (
                    <div
                      key={m.meetingId}
                      className={`flex items-center justify-between p-3 rounded-lg border ${m.isCompleted ? "bg-green-50 border-green-200" : "bg-gray-50 border-gray-200"}`}
                    >
                      <div className="flex items-center gap-3">
                        <Calendar className="h-4 w-4 text-gray-500" />
                        <div>
                          <div className="text-sm font-medium">{date}</div>
                          <div className="text-xs text-gray-600">
                            {timeRange} ({userTimezone})
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {/* Google-created meetings carry a Meet link; manually
                          logged ones never do. Completion alone cannot bound
                          this: a meeting nobody attended is never marked
                          completed, so the join window is what stops a
                          months-old slot from still offering a way in. */}
                        {m.meetLink &&
                          status !== MeetingStatus.COMPLETED &&
                          isWithinJoinWindow(m.endDatetime) && (
                            <a
                              href={m.meetLink}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 rounded border border-[#6035F3] px-2 py-1 text-xs font-medium text-[#6035F3] transition-colors hover:bg-[#6035F3] hover:text-white"
                            >
                              <Video className="h-3.5 w-3.5" />
                              Join
                            </a>
                          )}
                        {status === MeetingStatus.COMPLETED && (
                          <span className="text-xs font-bold px-2 py-1 rounded text-green-700">
                            DONE
                          </span>
                        )}
                        {status === MeetingStatus.PAST_INCOMPLETE && (
                          <span className="text-xs font-bold px-2 py-1 rounded text-gray-700">
                            INCOMPLETE
                          </span>
                        )}
                        {status === MeetingStatus.SCHEDULED && (
                          <span className="text-xs font-bold px-2 py-1 rounded text-amber-700">
                            SCHEDULED
                          </span>
                        )}
                        {canManageMeetings &&
                          status === MeetingStatus.SCHEDULED && (
                            <button
                              type="button"
                              aria-label={`Reschedule meeting on ${date}`}
                              onClick={() => onRescheduleMeeting?.(m)}
                              className="rounded p-1 text-gray-400 transition-colors hover:bg-blue-50 hover:text-blue-600"
                            >
                              <CalendarClock className="h-4 w-4" />
                            </button>
                          )}
                        {canManageMeetings &&
                          status === MeetingStatus.SCHEDULED && (
                            <button
                              type="button"
                              aria-label={`Cancel meeting on ${date}`}
                              onClick={() => setMeetingToCancel(m)}
                              className="rounded p-1 text-gray-400 transition-colors hover:bg-red-50 hover:text-red-600"
                            >
                              <Trash2 className="h-4 w-4" />
                            </button>
                          )}
                      </div>
                    </div>
                  );
                })
            )}
          </div>
        </div>
      )}

      {/* Cancelling takes the meeting off both sides' calendars and cannot be
          undone, so it goes through a confirmation naming the slot. */}
      <Dialog
        open={Boolean(meetingToCancel)}
        onOpenChange={(open) => {
          if (!open) setMeetingToCancel(null);
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Cancel this meeting?</DialogTitle>
            <DialogDescription>
              {cancelPrompt
                ? `${cancelPrompt.date}, ${cancelPrompt.timeRange} (${userTimezone}). This cannot be undone.`
                : null}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setMeetingToCancel(null)}
              disabled={isCancelling}
            >
              Keep it
            </Button>
            <Button
              variant="destructive"
              onClick={handleConfirmCancel}
              disabled={isCancelling}
            >
              Cancel meeting
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
