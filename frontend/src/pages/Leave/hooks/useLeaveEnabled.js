import { FEATURE_FLAGS } from "@/constants/FeatureFlags";
import { useFeatureFlags } from "@/hooks/useFeatureFlags";
import { useFeatureFlagsReady } from "@/hooks/useFeatureFlagsReady";

/**
 * Whether the leave feature is switched on for this viewer.
 *
 * One flag for the whole feature, not one per screen: leave is being built as
 * several screens that only make sense together -- approvals, a balance, the
 * company calendar, the data-health view -- and a flag per screen would let
 * half of it reach people while the other half is hidden.
 *
 * Everything the feature puts on screen asks here, entry points and pages
 * alike, so it cannot end up hiding a way in while leaving the page reachable
 * by typing its address.
 *
 * Off until LaunchDarkly answers -- flag values start as an empty map, so an
 * unresolved flag reads as false. That is the safe direction for something not
 * yet released: the cost is a card appearing a moment late, against the whole
 * feature appearing to everybody if the SDK never answers. Pages that redirect
 * when the feature is off wait for `isReady` first, so a direct link is not
 * bounced before LaunchDarkly has answered.
 *
 * @returns {{ isEnabled: boolean, isReady: boolean }}
 */
export const useLeaveEnabled = () => {
  const { [FEATURE_FLAGS.LEAVE_MANAGEMENT]: isEnabled } = useFeatureFlags();
  const isReady = useFeatureFlagsReady();
  return { isEnabled: !!isEnabled, isReady };
};
