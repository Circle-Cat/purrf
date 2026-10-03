import { formatInTz } from "@/utils/dateTime";
import { noteTagLabel } from "@/pages/MentorshipManagement/utils/meetingNoteTags";

/** Meeting times are shown in this zone across the mentorship admin pages. */
export const MEETING_TIMEZONE = "America/Los_Angeles";

/**
 * One line per flagged meeting, in the order given (the API sends them
 * oldest first): "2026-08-30: Erin Ma absent; Erin Ma late arrival".
 *
 * @param {Array<{startDatetime: string, note: string[]}>} issues - A pair's
 *   meetings that carry note tags.
 * @param {{mentorName: string, menteeName: string}} names - Who the
 *   role-specific tags refer to.
 * @returns {string[]}
 */
export const attendanceIssueLines = (issues, names) =>
  issues.map(
    ({ startDatetime, note }) =>
      `${formatInTz(startDatetime, MEETING_TIMEZONE, "yyyy-MM-dd")}: ${note
        .map((tag) => noteTagLabel(tag, names))
        .join("; ")}`,
  );
