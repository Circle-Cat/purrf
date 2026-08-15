import { useEffect } from "react";

import { showReminderToast } from "@/components/common/showReminderToast";
import { formatInTz } from "@/utils/dateTime";

const SESSION_KEY = "mentorship-registration-toast-shown";
const TOAST_ID = "mentorship-registration-toast";

// The program runs on Pacific time, and the label is spelled out so the
// date means one thing wherever it is read. Deliberately "PT" rather than
// a formatted zone token, which would alternate PDT/PST across the year
// and read as two different deadlines.
const DEADLINE_ZONE = "America/Los_Angeles";
const DEADLINE_PATTERN = "MMM d, h:mm a '(PT)'";

const CLOSED_TITLE = "Mentorship registration";
const CLOSED_MESSAGE =
  "Registration hasn't opened yet—we'll reach out soon with the next steps!";

const UNNAMED_ROUND_TITLE = "Register for the mentorship round";

/**
 * Reminds an admitted mentor or mentee, once per session, that filling in
 * the mentorship registration form is what stands between them and being
 * matched.
 *
 * Admission on its own puts nobody in a round. The registration form is
 * the actual participation trigger, and when no round is taking sign-ups
 * the dashboard renders nothing about mentorship at all, so without this
 * a newly admitted participant is left with no idea a further step
 * exists. It splits on the same condition as the admission email
 * (`backend/mentorship/notification_email_copy.py`) -- a round is taking
 * sign-ups, or none is -- so the two never contradict each other, though
 * the wording is its own.
 *
 * The deadline is stated in Pacific time rather than the reader's own.
 * The only zone the dashboard knows is the one the meeting log happens to
 * carry, which arrives from a later request and only once a round is
 * selected -- fetching the profile instead would buy a per-reader zone at
 * the cost of a query, and one named zone everybody reads the same way
 * was judged the better trade.
 *
 * @param {{
 *   enabled: boolean,
 *   isLoading: boolean,
 *   isRegistered: boolean,
 *   isRegistrationOpen: boolean,
 *   registrationDeadlineAt: string|null,
 *   roundName: string,
 * }} params - `enabled` should be true only once the caller has confirmed
 *   the user is a hired mentorship participant.
 * @returns {void}
 */
export const useRegistrationReminder = ({
  enabled,
  isLoading,
  isRegistered,
  isRegistrationOpen,
  registrationDeadlineAt,
  roundName,
}) => {
  useEffect(() => {
    if (!enabled) return;
    // Mid-load a round that is open looks closed and a registered user
    // looks unregistered, so every branch below would announce the wrong
    // thing -- and burn the session marker doing it.
    if (isLoading) return;
    if (isRegistered) return;
    if (sessionStorage.getItem(SESSION_KEY)) return;

    const deadline = isRegistrationOpen
      ? formatInTz(registrationDeadlineAt, DEADLINE_ZONE, DEADLINE_PATTERN)
      : null;

    const trimmedName = roundName?.trim();
    showReminderToast(
      deadline
        ? {
            id: TOAST_ID,
            title: trimmedName
              ? `Register for ${trimmedName}`
              : UNNAMED_ROUND_TITLE,
            message: `Please complete your registration by ${deadline} to get matched with a partner.`,
          }
        : { id: TOAST_ID, title: CLOSED_TITLE, message: CLOSED_MESSAGE },
    );
    sessionStorage.setItem(SESSION_KEY, "1");
  }, [
    enabled,
    isLoading,
    isRegistered,
    isRegistrationOpen,
    registrationDeadlineAt,
    roundName,
  ]);
};
