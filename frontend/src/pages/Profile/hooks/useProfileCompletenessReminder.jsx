import { useEffect } from "react";
import { toast } from "sonner";

import ReminderToastBody from "@/pages/Profile/components/ReminderToastBody";
import { isIncompleteOnboarding } from "@/pages/Profile/utils";

const PROFILE_SESSION_KEY = "profile-completeness-toast-shown";
const TRAINING_SESSION_KEY = "training-completeness-toast-shown";

const PROFILE_TOAST_ID = "profile-completeness-toast";
const TRAINING_TOAST_ID = "training-completeness-toast";

const PROFILE_TOAST_TITLE = "Complete your profile";
const PROFILE_TOAST_PREFIX =
  "We use this info to match you with the right partner when you register for upcoming mentorship rounds. Please fill in: ";

const TRAINING_TOAST_TITLE = "Complete onboarding training";
const TRAINING_TOAST_BODY =
  "To help you get started smoothly, please complete onboarding training in the Training section below.";

/**
 * Surfaces up to two one-time-per-session reminders when the signed-in
 * user is missing data we use for mentorship matching:
 *
 * - Profile reminder: any of Personal Information / Experience /
 *   Education is empty. Lists exactly the missing sections.
 *
 * - Training reminder: only fires once Personal Information is filled,
 *   so we don't nag about onboarding training before the user has even
 *   entered their name. Triggers when a mentor or mentee onboarding
 *   row exists and has not been completed.
 *
 * Each reminder has its own sessionStorage key so dismissing one does
 * not suppress the other, and so navigating in and out of /profile
 * does not re-nag the same one.
 */
export const useProfileCompletenessReminder = ({
  isLoading,
  personalInfo,
  experienceList,
  educationList,
}) => {
  useEffect(() => {
    if (isLoading) return;

    // Fire training first, then profile, so the profile toast — which
    // is more often actionable for new users — ends up on top of the
    // sonner stack (newest toast renders closest to the screen edge).
    if (!sessionStorage.getItem(TRAINING_SESSION_KEY)) {
      const personalInfoComplete =
        !!personalInfo.firstName && !!personalInfo.lastName;
      const trainings = personalInfo.completedTraining || [];
      const onboardingIncomplete = trainings.some(isIncompleteOnboarding);

      if (personalInfoComplete && onboardingIncomplete) {
        toast.info(TRAINING_TOAST_TITLE, {
          id: TRAINING_TOAST_ID,
          className: "items-start!",
          description: (
            <ReminderToastBody
              toastId={TRAINING_TOAST_ID}
              message={TRAINING_TOAST_BODY}
            />
          ),
          duration: Infinity,
          closeButton: false,
        });
        sessionStorage.setItem(TRAINING_SESSION_KEY, "1");
      }
    }

    if (!sessionStorage.getItem(PROFILE_SESSION_KEY)) {
      const profileMissing = [];
      if (!personalInfo.firstName || !personalInfo.lastName) {
        profileMissing.push("Personal Information");
      }
      if (experienceList.length === 0) profileMissing.push("Experience");
      if (educationList.length === 0) profileMissing.push("Education");

      if (profileMissing.length > 0) {
        toast.info(PROFILE_TOAST_TITLE, {
          id: PROFILE_TOAST_ID,
          // Override sonner's default `align-items: center` so the icon
          // sits at the top-left next to the title rather than floating
          // vertically centered against a multi-line description.
          className: "items-start!",
          description: (
            <ReminderToastBody
              toastId={PROFILE_TOAST_ID}
              message={`${PROFILE_TOAST_PREFIX}${profileMissing.join(", ")}.`}
            />
          ),
          duration: Infinity,
          closeButton: false,
        });
        sessionStorage.setItem(PROFILE_SESSION_KEY, "1");
      }
    }
  }, [
    isLoading,
    personalInfo.firstName,
    personalInfo.lastName,
    experienceList.length,
    educationList.length,
    personalInfo.completedTraining,
  ]);
};
