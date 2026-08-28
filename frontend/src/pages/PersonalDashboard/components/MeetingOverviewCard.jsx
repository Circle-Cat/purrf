import { Calendar, Video } from "lucide-react";
import { formatInTz } from "@/utils/dateTime";
import {
  getMeetingStatus,
  isWithinJoinWindow,
} from "@/utils/meetingStatusCalculator";
import { MeetingStatus } from "@/constants/MeetingStatus";

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
 * @param {{ overview: {
 *   requiredMeetings: number,
 *   completedCount: number,
 *   completedRate: number,
 *   meetingTimeList: Array<{ meetLink?: string }>,
 * } userTimezone: string}} props
 */
export default function MeetingOverviewCard({
  overview,
  userTimezone,
  showMeetingList = true,
}) {
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
              overview.meetingTimeList.map((m) => {
                const { date, timeRange } = formatMeetingTime(
                  m.startDatetime,
                  m.endDatetime,
                  userTimezone,
                );
                const status = getMeetingStatus(m.isCompleted, m.startDatetime);
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
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
