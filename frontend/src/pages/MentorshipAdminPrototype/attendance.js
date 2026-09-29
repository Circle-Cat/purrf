import { formatInTz } from "@/utils/dateTime";
import { noteTagLabel } from "@/pages/MentorshipManagement/utils/meetingNoteTags";

/**
 * A pair's meetings that the attendance sync flagged, one line each, oldest
 * first: "2026-08-30: Erin Ma absent".
 *
 * Only synced meetings ever carry note tags — a manual entry has none — so
 * any tag at all is an anomaly. An admin who clears the tags in the meeting
 * log clears the warning with them.
 *
 * @param {object} pair
 * @param {object[]} meetings - all meetings; filtered to this pair here.
 * @returns {string[]}
 */
export const attendanceIssuesOf = (pair, meetings) =>
  meetings
    .filter((m) => m.pairId === pair.pairId && m.note.length > 0)
    .sort((a, b) => a.startDatetime.localeCompare(b.startDatetime))
    .map((m) => {
      const date = formatInTz(
        m.startDatetime,
        "America/Los_Angeles",
        "yyyy-MM-dd",
      );
      const tags = m.note
        .map((tag) =>
          noteTagLabel(tag, {
            mentorName: pair.mentorName,
            menteeName: pair.menteeName,
          }),
        )
        .join("; ");
      return `${date}: ${tags}`;
    });
