import { Calendar } from "lucide-react";

/**
 * Format a UTC datetime range into a human-readable date and time range
 * string, converted into the user's profile timezone.
 *
 * @param {string} startUtc - Start datetime in UTC ISO format.
 * @param {string} endUtc - End datetime in UTC ISO format.
 * @param {string} timezone - IANA timezone string (e.g. "Asia/Shanghai").
 *   Falls back to browser local timezone if null or undefined.
 * @returns {{ date: string, timeRange: string }}
 */
function formatMeetingTime(startUtc, endUtc, timezone) {
  const options = timezone ? { timeZone: timezone } : {};

  const date = new Date(startUtc).toLocaleDateString("en-CA", options);
  const startTime = new Date(startUtc).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    ...options,
  });
  const endTime = new Date(endUtc).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    ...options,
  });

  return { date, timeRange: `${startTime} - ${endTime}` };
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
 * @param {{ overview: {
 *   requiredMeetings: number,
 *   completedCount: number,
 *   completedRate: number,
 *   meetingTimeList: Array,
 * } userTimezone: string | null}} props
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
                          {timeRange}
                          {userTimezone ? ` (${userTimezone})` : ""}
                        </div>
                      </div>
                    </div>
                    <span
                      className={`text-xs font-bold px-2 py-1 rounded ${m.isCompleted ? "text-green-700" : "text-amber-700"}`}
                    >
                      {m.isCompleted ? "DONE" : "SCHEDULED"}
                    </span>
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
