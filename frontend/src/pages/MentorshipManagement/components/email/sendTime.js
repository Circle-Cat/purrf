import { localToUtcIso } from "@/utils/dateTime";
import { MEETING_TIMEZONE } from "../../utils/attendanceIssues";

// The admin types a date and time in Pacific Time (the Mentorship Management
// timezone), whatever the browser's own zone is.
export const pacificToUtcIso = (date, time) => {
  const [y, m, d] = date.split("-").map(Number);
  return localToUtcIso(new Date(y, m - 1, d), time, MEETING_TIMEZONE);
};
