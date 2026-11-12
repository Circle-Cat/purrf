import { useEffect, useState } from "react";

import { getMyProfile } from "@/api/profileApi";
import { ProfileFields } from "@/constants/ApiEndpoints";

/**
 * Loads the viewer's training rows, for telling whether their mentorship
 * onboarding course is done.
 *
 * A failed fetch settles with an empty list, which reads as not done: the
 * banner then points at the training page, where the real status shows.
 *
 * @param {{enabled: boolean}} params - Fetch only once the viewer is a hired
 *   mentorship participant.
 * @returns {{training: Array<Object>, isLoading: boolean}}
 */
export const useOnboardingTraining = ({ enabled }) => {
  const [state, setState] = useState({ training: [], settled: false });

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;

    getMyProfile({ fields: [ProfileFields.TRAINING] })
      .then(({ data }) => {
        if (cancelled) return;
        setState({ training: data?.profile?.training ?? [], settled: true });
      })
      .catch((err) => {
        console.error("Failed to load onboarding training status", err);
        if (!cancelled) setState({ training: [], settled: true });
      });

    return () => {
      cancelled = true;
    };
  }, [enabled]);

  return { training: state.training, isLoading: enabled && !state.settled };
};
