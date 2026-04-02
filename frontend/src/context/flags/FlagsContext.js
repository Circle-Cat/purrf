import { createContext } from "react";

/**
 * Feature Flags Context.
 * Holds the current feature flag values synced from LaunchDarkly after user identification.
 * Consumed via {@link useFeatureFlags} or directly via `useContext(FlagsContext)`.
 *
 * @type {React.Context<{ flags: Record<string, any>, setFlags: (flags: Record<string, any>) => void }>}
 */
export const FlagsContext = createContext({ flags: {}, setFlags: () => {} });
