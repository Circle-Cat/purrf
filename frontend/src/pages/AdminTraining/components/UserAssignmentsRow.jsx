import { courseStatusLabel, timeSpentLabel } from "@/pages/AdminTraining/utils";
import {
  formatDateTimeWithZone,
  formatDateWithZone,
  resolveViewerTimezone,
} from "@/utils/dateTime";

const EM_DASH = "—";

const CELL = "border-b border-slate-200 px-3 py-2";
const HEAD = `${CELL} text-left font-semibold`;

/**
 * The sub-row under one person: every course they hold.
 *
 * Only rows that exist in `training` are listed. The catalogue is never
 * padded with courses nobody assigned them -- it grows with every new course
 * and would bury the two or three that matter. Somebody holding nothing still
 * appears in the search above; here they read as holding nothing.
 *
 * No percentage anywhere: `training` and `training_progress` carry a status,
 * the dates and the SCORM values, and nothing that says how far through a
 * learner is. The course's own completion rule is about the package, not the
 * person, so it is not shown here either.
 *
 * @param {Object} props
 * @param {number} props.userId whose courses these are.
 * @param {number} props.columnCount how many columns the parent row spans.
 * @param {boolean} props.loading whether the read is still in flight.
 * @param {Array<Object>|undefined} props.rows `TrainingUserAssignmentDto`
 *   rows, or undefined while they have not arrived.
 */
export default function UserAssignmentsRow({
  userId,
  columnCount,
  loading,
  rows,
}) {
  const timezone = resolveViewerTimezone();

  return (
    <tr>
      <td
        className="border-b border-slate-200 bg-slate-50 px-4 py-3"
        colSpan={columnCount}
        data-testid={`user-assignments-${userId}`}
      >
        {loading || rows === undefined ? (
          <p className="text-sm text-muted-foreground">Loading...</p>
        ) : rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">No courses assigned.</p>
        ) : (
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr>
                <th className={HEAD}>Course</th>
                <th className={HEAD}>Status</th>
                <th className={HEAD}>Score</th>
                <th className={HEAD}>Time spent</th>
                <th className={HEAD}>Last opened</th>
                <th className={HEAD}>Due</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((assignment) => (
                <tr key={assignment.trainingId}>
                  <td className={CELL}>{assignment.courseName ?? EM_DASH}</td>
                  <td className={CELL}>
                    {courseStatusLabel(assignment.status)}
                  </td>
                  <td className={CELL}>{assignment.scoreRaw ?? EM_DASH}</td>
                  <td className={CELL}>
                    {timeSpentLabel(assignment.sessionTimeSeconds)}
                  </td>
                  <td className={CELL}>
                    {formatDateTimeWithZone(
                      assignment.lastAccessedAt,
                      timezone,
                    ) ?? EM_DASH}
                  </td>
                  <td className={CELL}>
                    {formatDateWithZone(assignment.deadline, timezone) ??
                      EM_DASH}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </td>
    </tr>
  );
}
