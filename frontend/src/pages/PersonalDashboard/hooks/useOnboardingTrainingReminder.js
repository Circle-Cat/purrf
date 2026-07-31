import { useEffect } from "react";

import { getMyProfile } from "@/api/profileApi";
import { showReminderToast } from "@/components/common/showReminderToast";
import { ProfileFields } from "@/constants/ApiEndpoints";
import { isIncompleteOnboarding } from "@/utils/training";

const SESSION_KEY = "onboarding-training-toast-shown";
const TOAST_ID = "onboarding-training-toast";
const TOAST_TITLE = "Complete onboarding training";
const TOAST_MESSAGE =
  "You have been admitted to the mentorship program. Complete the onboarding training in your Profile page to get started.";

/**
 * Reminds a mentorship participant, once per session, that their
 * onboarding training is still outstanding.
 *
 * The training task is assigned the moment someone is admitted to a
 * mentor/mentee activity posting, well before any round opens, so the
 * reminder lives here on the dashboard rather than on the Profile page
 * the user may never visit. Unlike the profile-completeness reminder it
 * has no "fill in your name first" gate: this is an assigned task, and
 * newly admitted people are exactly its audience.
 *
 * Fetches only the training section of the profile. A failed fetch stays
 * silent — an unreachable API must not be reported as an unfinished task.
 *
 * @param {{enabled: boolean}} params - `enabled` should be true only once
 *   the caller has confirmed the user is a hired mentorship participant.
 * @returns {void}
 */
export const useOnboardingTrainingReminder = ({ enabled }) => {
  useEffect(() => {
    if (!enabled) return;
    if (sessionStorage.getItem(SESSION_KEY)) return;

    let cancelled = false;

    getMyProfile({ fields: [ProfileFields.TRAINING] })
      .then(({ data }) => {
        if (cancelled) return;
        const training = data?.profile?.training || [];
        sessionStorage.setItem(SESSION_KEY, "1");
        if (!training.some(isIncompleteOnboarding)) return;

        showReminderToast({
          id: TOAST_ID,
          title: TOAST_TITLE,
          message: TOAST_MESSAGE,
        });
      })
      .catch((err) => {
        console.error("Failed to check onboarding training status", err);
      });

    return () => {
      cancelled = true;
    };
  }, [enabled]);
};
