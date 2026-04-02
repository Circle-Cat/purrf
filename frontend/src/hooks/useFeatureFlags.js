import { useContext } from "react";
import { FlagsContext } from "@/context/flags";

/**
 * Custom hook to access the current LaunchDarkly feature flag values.
 * Returns a map of flag keys (kebab-case) to their evaluated values.
 * Use {@link FEATURE_FLAGS} constants as keys to avoid hardcoded strings.
 *
 * @returns {Record<string, any>} Current feature flag values from {@link FlagsContext}.
 *
 * @example
 * const flags = useFeatureFlags();
 * const canSubmit = flags[FEATURE_FLAGS.MANUAL_SUBMIT_MEETING];
 */
export function useFeatureFlags() {
  const { flags } = useContext(FlagsContext);
  return flags;
}
