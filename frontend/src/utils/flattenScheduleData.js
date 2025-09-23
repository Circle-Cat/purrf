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

/**
 * Flattens Microsoft chat message count data into a table-friendly format.
 * Assumes a flat data structure where keys are LDAP and values are counts.
 *
 * @param {Object} params
 * @param {Object} params.data - Microsoft chat data, keys are LDAP, values are message counts
 * @param {string} params.defaultChatSpace - Default chat space name to use for all entries
 * @returns {Array<Object>} An array of objects with fields: ldap, chatSpace, counts
 *
 * @example
 * * Input:
 * {
 * "alice": 15,
 * "bob": 10
 * }
 * * Output:
 * [
 * { "ldap": "alice", "chatSpace": "default chat space", "counts": 15 },
 * { "ldap": "bob", "chatSpace": "default chat space", "counts": 10 }
 * ]
 */
export const flattenMicrosoftChatData = ({ data, defaultChatSpace }) => {
  if (!data) {
    return [];
  }
  return Object.entries(data).map(([ldap, counts]) => ({
    ldap,
    chatSpace: defaultChatSpace,
    counts,
  }));
};

/**
 * Flattens Google chat message count data into a table-friendly format.
 * This function handles a nested data structure.
 *
 * @param {Object} params
 * @param {Object} params.data - Google chat data, keys are LDAP, values are objects mapping space IDs to counts
 * @param {Object} params.spaceMap - Map of space IDs to space names for display
 * @returns {Array<Object>} An array of objects with fields: ldap, chatSpace, counts
 *
 * @example
 * * Input:
 * {
 * "alice": { "space1": 25, "space2": 5 },
 * "bob": { "space1": 11, "space2": 0 }
 * }
 * * Output:
 * [
 * { "ldap": "alice", "chatSpace": "space1 name", "counts": 25 },
 * { "ldap": "alice", "chatSpace": "space2 name", "counts": 5 },
 * { "ldap": "bob", "chatSpace": "space1 name", "counts": 11 },
 * { "ldap": "bob", "chatSpace": "space2 name", "counts": 0 }
 * ]
 */
export const flattenGoogleChatData = ({ data, spaceMap }) => {
  if (!data) {
    return [];
  }
  const flattenedList = [];
  for (const ldap in data) {
    for (const spaceId in data[ldap]) {
      const spaceName = spaceMap[spaceId] || spaceId;
      flattenedList.push({
        ldap,
        chatSpace: spaceName,
        counts: data[ldap][spaceId],
      });
    }
  }
  return flattenedList;
};
