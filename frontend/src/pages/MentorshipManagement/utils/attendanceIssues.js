import { formatInTz } from "@/utils/dateTime";
import { noteTagLabel } from "@/pages/MentorshipManagement/utils/meetingNoteTags";

/** Meeting times are shown in this zone across the mentorship admin pages. */
export const MEETING_TIMEZONE = "America/Los_Angeles";

/**
 * A time as the mentorship admin pages show it, in MEETING_TIMEZONE:
 * "2026-10-02 10:30".
 *
 * @param {string} iso
 * @returns {string}
 */
export const formatPacific = (iso) =>
  formatInTz(iso, MEETING_TIMEZONE, "yyyy-MM-dd HH:mm");

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

/**
 * The line flagging a live pair that has not held a meeting by the round's
 * "First contact with mentor" date, or null. Only while the round is in
 * progress; ended pairs and past rounds are never flagged.
 *
 * @param {{isActive?: boolean, completedMeetingCount?: number}} pair -
 *   Whether the pairing is live (the partner's `isActive`) and how many of
 *   its meetings were held.
 * @param {{inProgress: boolean, firstMeetingDeadlineAt?: string|null}} round
 * @param {Date} [now]
 * @returns {string|null}
 */
export const firstContactOverdueLine = (
  { isActive, completedMeetingCount },
  { inProgress, firstMeetingDeadlineAt },
  now = new Date(),
) => {
  if (!inProgress || !firstMeetingDeadlineAt) return null;
  if (isActive === false || completedMeetingCount > 0) return null;
  if (new Date(firstMeetingDeadlineAt) > now) return null;
  return `No meeting held yet. First contact was due ${formatInTz(
    firstMeetingDeadlineAt,
    MEETING_TIMEZONE,
    "yyyy-MM-dd",
  )}.`;
};
