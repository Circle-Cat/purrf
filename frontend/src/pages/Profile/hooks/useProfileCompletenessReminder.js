import { useEffect } from "react";
import { toast } from "sonner";

const SESSION_KEY = "profile-completeness-toast-shown";

/**
 * Surfaces a one-time-per-session reminder when the signed-in user has not
 * filled out the parts of their profile we use for mentorship matching.
 *
 * Empty rules:
 * - Personal Information: firstName or lastName is empty
 * - Experience: experienceList is empty
 * - Education: educationList is empty
 *
 * The toast is fired at most once per browser session (sessionStorage marker
 * cleared on tab close), so navigating in and out of /profile does not re-nag.
 */
export const useProfileCompletenessReminder = ({
  isLoading,
  personalInfo,
  experienceList,
  educationList,
}) => {
  useEffect(() => {
    if (isLoading) return;
    if (sessionStorage.getItem(SESSION_KEY)) return;

    const missing = [];
    if (!personalInfo.firstName || !personalInfo.lastName) {
      missing.push("Personal Information");
    }
    if (experienceList.length === 0) missing.push("Experience");
    if (educationList.length === 0) missing.push("Education");

    if (missing.length === 0) return;

    toast.info("Complete your profile", {
      description: `We use this info to match you with the right partner when you register for upcoming mentorship rounds. Please fill in: ${missing.join(", ")}.`,
      duration: Infinity,
    });
    sessionStorage.setItem(SESSION_KEY, "1");
  }, [
    isLoading,
    personalInfo.firstName,
    personalInfo.lastName,
    experienceList.length,
    educationList.length,
  ]);
};
