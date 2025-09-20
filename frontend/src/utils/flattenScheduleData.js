/**
 * Flattens the nested schedule data from the backend into a flat array suitable for table display.
 *
 * @param {Record<string, any>} data - The schedule data keyed by LDAP with nested events and attendance.
 * @returns {Array<Object>} Array of flattened event entries with fields:
 *   - ldap: string
 *   - calendarName: string
 *   - summary: string
 *   - date: string (local date)
 *   - joinTime: string (local time)
 *   - leaveTime: string (local time)
 *   - key: string (unique key for React rendering)
 * @example
 * Input Data Structure (Example backend response)
 * const inputData = {
 *   "ldapA": [
 *     {
 *       calendar_name: "Team Sync Calendar",
 *       summary: "Weekly Standup",
 *       event_id: "event-101",
 *       attendance: [
 *         {
 *           join_time: "2025-09-20T09:00:00Z", // UTC time
 *           leave_time: "2025-09-20T09:30:00Z" // UTC time
 *         }
 *       ]
 *     },
 *   "ldapB": [] // LDAP with no events
 * };
 *
 * Expected Output (assuming 'en-US' locale and UTC timezone for formatting)
 * const outputArray = [
 *   {
 *     ldap: "ldapA",
 *     calendarName: "Team Sync Calendar",
 *     summary: "Weekly Standup",
 *     date: "9/20/2025",
 *     joinTime: "09:00 AM",
 *     leaveTime: "09:30 AM",
 *     key: "ldapA-event-101-0",
 *   }
 * ];
 *
 */
export const flattenGoogleCalendarScheduleData = (data) => {
  if (!data || typeof data !== "object") {
    return [];
  }
  return Object.entries(data).flatMap(([ldap, events]) => {
    if (!Array.isArray(events)) {
      return [];
    }
    return events.flatMap((event) => {
      if (!Array.isArray(event.attendance)) {
        return [];
      }
      return event.attendance.map((attendanceEntry, index) => {
        const joinDate = new Date(attendanceEntry.join_time);

        return {
          ldap: ldap,
          calendarName: event.calendar_name,
          summary: event.summary,
          date: joinDate.toLocaleDateString(),
          joinTime: joinDate.toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          }),
          leaveTime: new Date(attendanceEntry.leave_time).toLocaleTimeString(
            [],
            { hour: "2-digit", minute: "2-digit" },
          ),
          key: `${ldap}-${event.event_id}-${index}`,
        };
      });
    });
  });
};
