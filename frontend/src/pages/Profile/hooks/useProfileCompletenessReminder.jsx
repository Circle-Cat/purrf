import { useEffect } from "react";

import { showReminderToast } from "@/components/common/showReminderToast";

const PROFILE_SESSION_KEY = "profile-completeness-toast-shown";

const PROFILE_TOAST_ID = "profile-completeness-toast";

const PROFILE_TOAST_TITLE = "Complete your profile";
const PROFILE_TOAST_PREFIX =
  "We use this info to match you with the right partner when you register for upcoming mentorship rounds. Please fill in: ";

/**
 * Surfaces a one-time-per-session reminder when the signed-in user is
 * missing profile data we use for mentorship matching: any of Personal
 * Information / Experience / Education is empty. Lists exactly the
 * missing sections.
 *
 * `enabled` has no default: the message is written entirely around
 * mentorship partner matching, so it is only meaningful to an admitted
 * mentor or mentee. Everyone else — including someone who applied to a
 * different kind of activity — reads it as a demand to fill in a profile
 * for a program they are not in. It is also false while the caller is
 * still finding out, which is why a disabled run leaves the session
 * marker untouched rather than writing it: the reminder still has to be
 * able to fire once the answer arrives.
 *
 * The sessionStorage key keeps navigating in and out of /profile from
 * re-nagging. The mentorship onboarding training reminder is a separate
 * concern and lives on the Personal Dashboard
 * (`useOnboardingTrainingReminder`), where a newly admitted participant
 * sees it without having to visit their profile first.
 */
export const useProfileCompletenessReminder = ({
  enabled,
  isLoading,
  loadError,
  personalInfo,
  experienceList,
  educationList,
}) => {
  useEffect(() => {
    if (!enabled) return;

    // Don't nag while loading, or when the data failed to load — empty state
    // from a fetch failure must not be mistaken for a genuinely empty profile.
    if (isLoading || loadError) return;

    if (!sessionStorage.getItem(PROFILE_SESSION_KEY)) {
      const profileMissing = [];
      if (!personalInfo.firstName || !personalInfo.lastName) {
        profileMissing.push("Personal Information");
      }
      if (experienceList.length === 0) profileMissing.push("Experience");
      if (educationList.length === 0) profileMissing.push("Education");

      if (profileMissing.length > 0) {
        showReminderToast({
          id: PROFILE_TOAST_ID,
          title: PROFILE_TOAST_TITLE,
          message: `${PROFILE_TOAST_PREFIX}${profileMissing.join(", ")}.`,
        });
        sessionStorage.setItem(PROFILE_SESSION_KEY, "1");
      }
    }
  }, [
    enabled,
    isLoading,
    loadError,
    personalInfo.firstName,
    personalInfo.lastName,
    experienceList.length,
    educationList.length,
  ]);
};
