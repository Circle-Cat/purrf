import { createContext } from "react";

/**
 * Feature Flags Context.
 * Holds the current feature flag values synced from LaunchDarkly after user identification.
 * Consumed via {@link useFeatureFlags} or directly via `useContext(FlagsContext)`.
 *
 * `ready` turns true once LaunchDarkly has answered (or failed to). It defaults to true
 * outside a {@link FlagsProvider}, where no answer will ever arrive to wait for.
 *
 * @type {React.Context<{ flags: Record<string, any>, setFlags: (flags: Record<string, any>) => void, ready: boolean, setReady: (ready: boolean) => void }>}
 */
export const FlagsContext = createContext({
  flags: {},
  setFlags: () => {},
  ready: true,
  setReady: () => {},
});
