import { LEAVE_REQUEST_TYPE } from "@/constants/LeaveRequest";
import {
  formatBusinessRange,
  formatDaysNotCounted,
  formatTimeSpan,
  formatWorkdays,
} from "@/pages/Leave/utils/leaveDates";

/**
 * RequestSpan
 *
 * The dates a request covers and the hours they come to, with what explains
 * the hours: how many working days a range counts, and the weekend days and
 * company holidays inside it that it skips. Both come from the server, which
 * computes the hours; nothing here works them out again.
 *
 * The working-day count is left off a single day, where it would only repeat
 * the date, and off an exchange, whose days are holidays worked rather than
 * working days.
 *
 * @param {{ row: object, className?: string }} props
 */
const RequestSpan = ({ row, className = "text-sm" }) => {
  const timeSpan = formatTimeSpan(row.startTime, row.endTime);
  const workdays =
    row.startDate !== row.endDate && row.type !== LEAVE_REQUEST_TYPE.EXCHANGE
      ? formatWorkdays(row.workdays)
      : "";
  const notCounted = formatDaysNotCounted(row.daysNotCounted);

  return (
    <>
      <p className={className}>
        {formatBusinessRange(row.startDate, row.endDate)}
        {timeSpan && ` · ${timeSpan}`}
        {workdays && ` · ${workdays}`}
        {` · ${row.hours} h`}
      </p>
      {notCounted && (
        <p className="text-sm text-muted-foreground">
          {`Not counted: ${notCounted}`}
        </p>
      )}
    </>
  );
};

export default RequestSpan;
