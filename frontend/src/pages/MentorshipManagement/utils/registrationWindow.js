import { formatInTz } from "@/utils/dateTime";
import { MEETING_TIMEZONE } from "@/pages/MentorshipManagement/utils/attendanceIssues";

/**
 * The round's registration window as dates, e.g.
 * "Registration: 2026-09-01 to 2026-09-20", or a note that it has none.
 *
 * @param {{timeline?: {promotionStartAt?: string|null,
 *   onboardingDeadlineAt?: string|null}}|null|undefined} round
 * @returns {string}
 */
export const registrationWindowLabel = (round) => {
  const { promotionStartAt, onboardingDeadlineAt } = round?.timeline ?? {};
  if (!promotionStartAt || !onboardingDeadlineAt) {
    return "This round has no registration period set.";
  }
  const day = (iso) => formatInTz(iso, MEETING_TIMEZONE, "yyyy-MM-dd");
  return `Registration: ${day(promotionStartAt)} to ${day(onboardingDeadlineAt)}`;
};
